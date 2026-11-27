"""The ingest job against a real Postgres: done, skipped, failed, retried, never lost or doubled."""

from typing import Literal

import pytest
from arq import Retry
from pydantic import BaseModel
from sqlalchemy import func, select

from rti_mate.config import Settings
from rti_mate.db.ingest_jobs import IngestRepository
from rti_mate.db.models import Document, IngestItem, IngestJob, ParseFailure
from rti_mate.db.session import make_engine, make_sessionmaker
from rti_mate.llm.gateway import FakeLLM, LLMError, LLMGateway
from rti_mate.workers.ingest import Pace, ingest_document

GOOD = '{"kind": "circular", "topics": ["fees"]}'


class Notice(BaseModel):
    kind: Literal["circular", "guideline"]
    topics: list[str]


async def no_sleep(seconds: float) -> None:
    pass


@pytest.fixture
async def world(database_url, tmp_path):
    """A clean database, three files on disk, and everything a job finds in its ctx."""
    settings = Settings(app_env="ci", database_url=database_url, _env_file=None)
    engine = make_engine(settings)
    sessionmaker = make_sessionmaker(engine)
    async with sessionmaker() as session:
        for table in (Document, ParseFailure, IngestJob):
            await session.execute(table.__table__.delete())
        await session.commit()
    (tmp_path / "fees.md").write_text("# Fee rules\n\nFees change in 2024.", encoding="utf-8")
    (tmp_path / "broken.pdf").write_bytes(b"this is not a pdf")

    def record(name: str, **changes) -> dict:
        base = {
            "url": f"https://x.test/{name}",
            "source": "x",
            "licence": "CC BY 4.0",
            "via": "http",
            "path": str(tmp_path / name),
            "sha256": "0" * 64,  # the job computes the real one from the file
            "status": "downloaded",
        }
        return base | changes

    llm = FakeLLM()
    ctx = {
        "settings": settings,
        "sessionmaker": sessionmaker,
        "http": None,  # every file is on disk: nothing is downloaded in these tests
        "pace": Pace(6000, sleep=no_sleep),
        "gateway": LLMGateway([llm], sleep=no_sleep),
        "extract": {"schema": Notice, "prompt": "Fill.", "version": "extract_v1", "chars": 2000},
    }

    async def queue(*records: dict) -> tuple[str, list[int]]:
        async with sessionmaker() as session:
            return await IngestRepository(session).create(list(records))

    async def item(item_id: int) -> IngestItem:
        async with sessionmaker() as session:
            return await session.get(IngestItem, item_id)

    async def count(table) -> int:
        async with sessionmaker() as session:
            return await session.scalar(select(func.count()).select_from(table))

    yield {"ctx": ctx, "llm": llm, "record": record, "queue": queue, "item": item, "count": count}
    await engine.dispose()


async def test_a_document_is_ingested_once_however_often_its_job_runs(world):
    ctx, llm = world["ctx"], world["llm"]
    job_id, (first,) = await world["queue"](world["record"]("fees.md"))
    llm.script = [GOOD]
    assert await ingest_document(ctx, first) == "done"
    done = await world["item"](first)
    assert (done.status, done.attempts, done.pages, done.error) == ("done", 1, 1, "")
    assert await ingest_document(ctx, first) == "ignored"  # the same job, delivered twice

    _, (again,) = await world["queue"](world["record"]("fees.md"))  # queued a second time
    assert await ingest_document(ctx, again) == "skipped"
    assert await world["count"](Document) == 1 and llm.calls == 1  # no copy, no second bill

    async with ctx["sessionmaker"]() as session:
        document = await session.scalar(select(Document))
        progress = await IngestRepository(session).progress(job_id)
    assert document.metadata_["kind"] == "circular" and document.title == "Fee rules"
    assert progress["status"] == "finished" and progress["counts"]["done"] == 1
    assert progress["pages"] == 1 and progress["dead_letter"] == []


async def test_a_poison_message_goes_to_the_dead_letter_list_without_retries(world):
    ctx = world["ctx"]
    by_hand = world["record"]("not-on-this-machine.pdf", via="manual")
    job_id, (broken, missing) = await world["queue"](world["record"]("broken.pdf"), by_hand)
    assert await ingest_document(ctx, broken) == "failed"
    assert await ingest_document(ctx, missing) == "failed"
    assert (await world["item"](broken)).error.startswith("parse: ")
    assert "by hand" in (await world["item"](missing)).error
    assert await world["count"](ParseFailure) == 1 and await world["count"](Document) == 0
    async with ctx["sessionmaker"]() as session:
        repo = IngestRepository(session)
        progress = await repo.progress(job_id)
        assert progress["status"] == "finished" and progress["counts"]["failed"] == 2
        assert {entry["attempts"] for entry in progress["dead_letter"]} == {1}
        assert len(await repo.known_ids()) == 1  # the unreadable file will not be queued again
        assert len(await repo.failed_records()) == 2


async def test_a_temporary_failure_is_retried_and_only_then_given_up(world):
    ctx, llm = world["ctx"], world["llm"]
    _, (item_id,) = await world["queue"](world["record"]("fees.md"))
    llm.script = [LLMError("HTTP 429: slow down", retryable=False)] * 3
    with pytest.raises(Retry):  # arq will run the job again later
        await ingest_document(ctx, item_id)
    waiting = await world["item"](item_id)
    assert (waiting.status, waiting.attempts) == ("queued", 1) and "429" in waiting.error
    assert await world["count"](Document) == 1  # the parsing is kept: only the model is missing
    async with ctx["sessionmaker"]() as session:
        assert await IngestRepository(session).open_item_ids() == [item_id]

    with pytest.raises(Retry):
        await ingest_document(ctx, item_id)
    assert await ingest_document(ctx, item_id) == "failed"  # the third and last try
    assert "gave up after 3 tries" in (await world["item"](item_id)).error

    # Later the model is back. (A new gateway stands in for the circuit breaker's cooldown.)
    _, (later,) = await world["queue"](world["record"]("fees.md"))
    llm.script = [GOOD]
    ctx["gateway"] = LLMGateway([llm], sleep=no_sleep)
    assert await ingest_document(ctx, later) == "done"
    assert await world["count"](Document) == 1


async def test_a_document_that_keeps_killing_the_worker_is_given_up(world):
    ctx = world["ctx"]
    _, (item_id,) = await world["queue"](world["record"]("fees.md"))
    async with ctx["sessionmaker"]() as session:  # as if three workers started it and died
        item = await session.get(IngestItem, item_id)
        item.status, item.attempts = "running", 3
        await session.commit()
    assert await ingest_document(ctx, item_id) == "failed"
    assert "never finished" in (await world["item"](item_id)).error
    assert await world["count"](Document) == 0  # it was not touched a fourth time

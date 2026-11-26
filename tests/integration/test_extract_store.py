"""Extraction against a real Postgres: merged into metadata, resumable, versioned."""

from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select

from rti_mate.config import Settings
from rti_mate.db.models import Document, Page
from rti_mate.db.session import make_engine, make_sessionmaker
from rti_mate.llm.extract import run
from rti_mate.llm.gateway import FakeLLM, LLMError, LLMGateway


class Notice(BaseModel):
    kind: Literal["circular", "guideline"]
    topics: list[str]


GOOD = '{"kind": "circular", "topics": ["fees"]}'


async def no_sleep(seconds: float) -> None:
    pass


def document(number: int, doc_type: str = "pdf") -> Document:
    return Document(
        external_id=f"f-{number}",
        title=f"Document {number}",
        doc_type=doc_type,
        sha256=str(number) * 64,
        metadata_={"parser": "pymupdf", "pages": 1},
        pages=[Page(page_no=1, text=f"Text of document {number}.", headings=[])],
    )


async def test_extraction_is_stored_resumable_and_versioned(database_url):
    engine = make_engine(Settings(app_env="ci", database_url=database_url, _env_file=None))
    sessionmaker = make_sessionmaker(engine)
    async with sessionmaker() as session:
        await session.execute(Document.__table__.delete())
        session.add_all([document(1), document(2), document(3), document(4, "record")])
        await session.commit()

    async def extract_all(llm: FakeLLM, version: str = "extract_v1", **options):
        said: list[str] = []
        gateway = LLMGateway([llm], sleep=no_sleep)
        options |= {"sleep": no_sleep, "echo": said.append}
        return await run(sessionmaker, gateway, Notice, "Fill.", version, **options), said

    async def stored() -> dict[str, dict]:
        async with sessionmaker() as session:
            rows = await session.scalars(select(Document).order_by(Document.external_id))
            return {row.external_id: row.metadata_ for row in rows}

    # 1 is fine, 2 is wrong three times, 3 needs one repair. The data record (4) is never sent.
    llm = FakeLLM(script=[GOOD, "no", "no", "no", '{"kind": "poem", "topics": []}', GOOD])
    counts, said = await extract_all(llm)
    assert (counts["ok"], counts["repaired"], counts["failed"]) == (2, 1, 1) and llm.calls == 6
    meta = await stored()
    assert meta["f-1"]["kind"] == "circular" and meta["f-1"]["parser"] == "pymupdf"  # merged
    assert meta["f-1"]["extract"] == {"prompt": "extract_v1", "model": "fake-1", "attempts": 1}
    assert "kind" not in meta["f-2"] and "no JSON object" in meta["f-2"]["extract"]["error"]
    assert meta["f-3"]["extract"]["attempts"] == 2 and "extract" not in meta["f-4"]
    assert any(line.startswith("FAILED") for line in said)

    again = FakeLLM()
    counts, _ = await extract_all(again)  # nothing new: no model call, no cost
    assert counts["pending"] == 0 and again.calls == 0

    retry = FakeLLM(script=[GOOD])
    counts, _ = await extract_all(retry, retry_failed=True)  # only the failed one
    assert (
        counts["ok"] == 1 and retry.calls == 1 and "error" not in (await stored())["f-2"]["extract"]
    )

    counts, _ = await extract_all(FakeLLM(script=[GOOD] * 3), version="extract_v2")
    assert counts["pending"] == 3  # a new prompt version: every document is done again

    down = FakeLLM(script=[LLMError("HTTP 429", retryable=False)] * 2)
    counts, said = await extract_all(down, version="extract_v3")
    assert counts["stopped"] == 1 and counts["ok"] == 0 and "stopped" in said[-1]
    await engine.dispose()

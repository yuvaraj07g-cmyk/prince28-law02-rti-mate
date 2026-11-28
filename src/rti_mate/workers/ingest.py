"""One job = one document: get the file, parse it, extract its record, store everything.

A job can run twice (the worker died, or a retry). That is safe, because every step first
checks what is already in the database: a document is identified by its content hash.
"""

import asyncio
import hashlib
import logging
import re
import tempfile
import time
from pathlib import Path

import httpx
from arq import Retry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rti_mate.db.models import Document, IngestItem
from rti_mate.ingest.fetch import RETRYABLE, HostGate, Robots, Source, fetch_one
from rti_mate.ingest.parse import ParseError, parse_file
from rti_mate.ingest.store import document_id, save_document, save_failure
from rti_mate.llm.extract import document_text, extract, save

logger = logging.getLogger("rti_mate.worker")
GITHUB_BLOB = re.compile(r"^https://github\.com/([^/]+/[^/]+)/blob/[^/]+/(.+)$")


class Permanent(Exception):
    """This document will never work, however often we try: no retry, straight to the list."""


def plan(
    records: list[dict], done_ids: set[str], *, source: str = "", limit: int = 0
) -> list[dict]:
    """Which manifest records need a job: downloaded, wanted, and not in the database yet."""
    todo, seen = [], set(done_ids)
    for record in records:
        if record.get("status") != "downloaded" or (source and record.get("source") != source):
            continue
        doc_id = document_id(record["sha256"])
        if doc_id in seen:  # already ingested, or the same bytes under a second URL
            continue
        seen.add(doc_id)
        todo.append(record)
    return todo[:limit] if limit else todo


def raw_url(record: dict) -> str:
    """Where a worker without your laptop's files can download this document."""
    match = GITHUB_BLOB.match(record["url"])
    if record.get("via") == "git" and match and record.get("commit"):
        return f"https://raw.githubusercontent.com/{match[1]}/{record['commit']}/{match[2]}"
    return record["url"]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Pace:
    """At most `per_minute` passes a minute, shared by all jobs of this worker (backpressure)."""

    def __init__(self, per_minute: float, clock=time.monotonic, sleep=asyncio.sleep) -> None:
        self._gap, self._clock, self._sleep = 60 / per_minute, clock, sleep
        self._next = 0.0

    async def wait(self) -> None:
        now = self._clock()
        delay = max(0.0, self._next - now)
        self._next = max(now, self._next) + self._gap
        if delay:
            await self._sleep(delay)


async def get_file(
    record: dict, folder: Path, client: httpx.AsyncClient, sleep=asyncio.sleep
) -> Path:
    """The file from disk if it is there; otherwise download it into `folder`."""
    path = Path(record["path"])
    if path.is_file():
        return path
    if record.get("via") == "manual":
        raise Permanent("downloaded by hand: this file exists only on the laptop that has it")
    source = Source(raw_url(record), record["source"], record.get("licence") or "unknown")
    result = await fetch_one(
        client,
        source,
        root=folder,
        raw_dir=folder / "raw",
        robots=Robots(client),
        gate=HostGate(0.5, sleep),
        slots=asyncio.Semaphore(1),
        max_attempts=2,
        sleep=sleep,
    )
    if result["status"] == "downloaded":
        return folder / result["path"]
    problem = f"download {result['status']}: {result.get('error', '')}"
    if result["status"] == "blocked" or result.get("http_status") not in {None, *RETRYABLE}:
        raise Permanent(problem)  # robots.txt, 403, 404: asking again changes nothing
    raise RuntimeError(problem)  # 5xx, timeout: worth another try later


async def process(ctx: dict, session: AsyncSession, item: IngestItem) -> tuple[str, int]:
    """Do the work for one item. Returns (status, pages). Raises to ask for a retry."""
    record = dict(item.record)
    with tempfile.TemporaryDirectory() as folder:
        path = await get_file(record, Path(folder), ctx["http"])
        record["sha256"] = await asyncio.to_thread(sha256_of, path)  # what we really have
        doc_id = document_id(record["sha256"])
        document = await session.scalar(select(Document).where(Document.external_id == doc_id))
        status = "skipped"  # until this run adds something new
        if document is None:
            try:
                parsed = await asyncio.to_thread(parse_file, path)
            except ParseError as error:
                await save_failure(session, record, error)
                raise Permanent(f"parse: {error.reason}") from error
            await save_document(session, record, parsed)
            document = await session.scalar(select(Document).where(Document.external_id == doc_id))
            status = "done"
    pages = int(document.metadata_.get("pages", 0))
    task = ctx.get("extract")  # None when there is no extract prompt or no model key
    note = document.metadata_.get("extract") or {}
    if task and (note.get("prompt") != task["version"] or "error" in note):
        await ctx["pace"].wait()
        text = await document_text(session, document, task["chars"])
        result = await extract(
            ctx["gateway"], task["schema"], task["prompt"], task["version"], document.title, text
        )
        await save(session, document, result, task["version"])
        if result.record is None:
            raise Permanent(f"extract: {result.errors[-1][:200]}")
        status = "done"
    return status, pages


async def ingest_document(ctx: dict, item_id: int) -> str:
    """The function the worker runs for every queued item. It never loses an item silently."""
    max_tries = ctx["settings"].ingest_max_tries
    async with ctx["sessionmaker"]() as session:
        item = await session.get(IngestItem, item_id)
        if item is None or item.status not in ("queued", "running"):
            return "ignored"  # unknown, or finished by an earlier delivery of this same job
        if item.attempts >= max_tries:  # started that often and never finished: the worker died
            item.status = "failed"
            item.error = f"gave up: started {item.attempts} times and never finished"
            await session.commit()
            return "failed"
        item.status, item.attempts = "running", item.attempts + 1
        attempt = item.attempts  # counted in Postgres, so it survives a dead worker
        await session.commit()
        try:
            item.status, item.pages = await process(ctx, session, item)
            item.error = ""
        except Permanent as error:  # a poison message: retrying would only waste the queue
            await session.rollback()
            item.status, item.error = "failed", str(error)[:500]
        except Exception as error:
            await session.rollback()
            reason = f"{type(error).__name__}: {error}"[:500]
            if attempt >= max_tries:
                item.status, item.error = "failed", f"gave up after {attempt} tries: {reason}"
            else:
                item.status, item.error = "queued", f"try {attempt} failed: {reason}"
                await session.commit()
                logger.warning("item %s will be retried: %s", item_id, reason)
                raise Retry(defer=attempt * 30) from error  # in 30 s, then 60 s, then give up
        await session.commit()
        logger.info("item %s %s", item_id, item.status)
        return item.status

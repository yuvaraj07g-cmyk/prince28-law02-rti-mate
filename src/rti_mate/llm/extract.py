"""Structured output: turn a document into a small record that is checked before it is stored.

The model is asked for JSON. Its reply is parsed and validated against a Pydantic class.
If the reply is rejected, the model is told exactly what was wrong and asked again (the
validation-retry loop). After `max_attempts` rejections nothing is stored: the document is
marked as failed, with the reason, and a person looks at it.
"""

import asyncio
import json
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rti_mate.db.models import Document, Page
from rti_mate.llm.gateway import LLMGateway, LLMUnavailable

# Keys the parser already wrote into documents.metadata: an extracted field must not replace them.
RESERVED = {"source", "path", "parser", "pages", "tables", "chars", "extract"}


def parse_json(reply: str) -> dict:
    """Models like to wrap JSON in ```json fences or add a sentence. Take the outermost {...}."""
    start, end = reply.find("{"), reply.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("the reply contains no JSON object")
    value = json.loads(reply[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("the JSON is not an object")
    return value


def explain(error: Exception) -> str:
    """What was wrong, short enough to send back to the model."""
    if isinstance(error, ValidationError):
        problems = error.errors()[:6]
        return "; ".join(
            f"{'.'.join(map(str, p['loc'])) or 'object'}: {p['msg']}" for p in problems
        )
    return str(error)


@dataclass
class Extraction:
    record: BaseModel | None  # None = still invalid after every attempt
    attempts: int = 0
    errors: list[str] = field(default_factory=list)  # why each rejected reply was rejected
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_inr: float = 0.0


async def extract(
    gateway: LLMGateway,
    schema: type[BaseModel],
    prompt: str,
    version: str,
    title: str,
    text: str,
    *,
    max_attempts: int = 3,
    native_schema: bool = False,
) -> Extraction:
    json_schema = schema.model_json_schema()
    system = f"{prompt}\n\nThe JSON object must match this JSON schema:\n{json.dumps(json_schema)}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Title: {title}\n<document>\n{text}\n</document>"},
    ]
    options: dict = {"temperature": 0}
    if native_schema:  # let the provider enforce the schema while it writes
        spec = {"name": schema.__name__, "schema": json_schema}
        options["response_format"] = {"type": "json_schema", "json_schema": spec}
    out = Extraction(record=None)
    for attempt in range(1, max_attempts + 1):
        result = await gateway.generate(
            messages, purpose="extract", prompt_version=version, **options
        )
        out.attempts, out.model = attempt, result.model
        out.tokens_in += result.tokens_in
        out.tokens_out += result.tokens_out
        out.cost_inr += result.cost_inr
        try:
            out.record = schema.model_validate(parse_json(result.text))
            return out
        except ValueError as error:  # bad JSON, or JSON that breaks the contract
            out.errors.append(explain(error))
            repair = f"That reply was rejected: {out.errors[-1]}. "
            repair += "Reply again with only the corrected JSON object."
            messages = [
                *messages,
                {"role": "assistant", "content": result.text},
                {"role": "user", "content": repair},
            ]
    return out


async def pending(
    session: AsyncSession, version: str, *, limit: int = 0, retry_failed: bool = False
) -> list[Document]:
    """Parsed documents this prompt version has not handled yet (failed ones only on request)."""
    note = Document.metadata_["extract"]
    not_done = note["prompt"].astext.is_distinct_from(version)
    failed = note["error"].astext.is_not(None)
    stmt = select(Document).where(Document.doc_type != "record")
    stmt = stmt.where(or_(not_done, failed) if retry_failed else not_done).order_by(Document.id)
    return list(await session.scalars(stmt.limit(limit) if limit else stmt))


async def document_text(session: AsyncSession, document: Document, chars: int) -> str:
    """The start of the document: its first pages, cut to `chars` characters (cost control)."""
    stmt = select(Page.text).where(Page.document_id == document.id).order_by(Page.page_no).limit(3)
    return "\n\n".join(await session.scalars(stmt))[:chars]


async def save(session: AsyncSession, document: Document, result: Extraction, version: str) -> None:
    """Merge the record into documents.metadata. A failure stores the reason and no fields."""
    note = {"prompt": version, "model": result.model, "attempts": result.attempts}
    fields = {}
    if result.record is None:
        note["error"] = result.errors[-1][:300]
    else:
        fields = result.record.model_dump(mode="json")
    document.metadata_ = {**document.metadata_, **fields, "extract": note}
    await session.commit()  # one transaction per document: a crash loses at most one


async def run(
    sessionmaker: async_sessionmaker,
    gateway: LLMGateway,
    schema: type[BaseModel],
    prompt: str,
    version: str,
    *,
    limit: int = 0,
    rpm: float = 12,
    chars: int = 6000,
    retry_failed: bool = False,
    native: bool = False,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    echo: Callable[[str], None] = print,
) -> Counter:
    """Extract every pending document, at most `rpm` documents a minute. Safe to run again."""
    clash = RESERVED & set(schema.model_fields)
    if clash:
        raise ValueError(f"rename these fields, the parser already uses them: {sorted(clash)}")
    counts: Counter = Counter()
    async with sessionmaker() as session:
        todo = await pending(session, version, limit=limit, retry_failed=retry_failed)
        counts["pending"] = len(todo)
        for number, document in enumerate(todo, start=1):
            text = await document_text(session, document, chars)
            label = f"{document.external_id}  {document.title[:50]}"
            for waited in (False, True):
                try:
                    result = await extract(
                        gateway, schema, prompt, version, document.title, text, native_schema=native
                    )
                    break
                except LLMUnavailable as error:
                    if waited:  # twice in a row: stop politely, the next run continues here
                        echo(f"stopped: no model can answer ({str(error)[:160]})")
                        counts["stopped"] = 1
                        return counts
                    echo("no model can answer right now (rate limit?): waiting 60 s")
                    await sleep(60)
            await save(session, document, result, version)
            counts["tokens_in"] += result.tokens_in
            counts["tokens_out"] += result.tokens_out
            counts["micro_inr"] += round(result.cost_inr * 1_000_000)
            if result.record is None:
                counts["failed"] += 1
                echo(f"FAILED   {label}  {result.errors[-1][:90]}")
            else:
                counts["ok"] += 1
                if result.attempts > 1:
                    counts["repaired"] += 1
                    echo(f"repaired {label}  after: {result.errors[0][:90]}")
            if number % 10 == 0:
                echo(f"... {number} of {len(todo)} documents")
            if number < len(todo):
                await sleep(60 / rpm)
    return counts

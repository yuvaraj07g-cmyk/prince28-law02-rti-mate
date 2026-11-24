"""Save what the parser produced: a document with its pages, or a row in parse_failures."""

from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rti_mate.db.models import Document, Page, ParseFailure
from rti_mate.ingest.parse import ParsedDoc, ParseError


def document_id(sha256: str) -> str:
    """Files are identified by their content: the same bytes are the same document."""
    return f"f-{sha256[:20]}"


async def parsed_ids(session: AsyncSession) -> set[str]:
    rows = await session.scalars(select(Document.external_id).where(Document.doc_type != "record"))
    return set(rows)


async def failed_paths(session: AsyncSession) -> set[str]:
    return set(await session.scalars(select(ParseFailure.path)))


async def save_document(session: AsyncSession, record: dict, parsed: ParsedDoc) -> None:
    """One manifest record + its parsed pages -> documents and pages. Clears an old failure."""
    title = parsed.title or record.get("title") or Path(record["path"]).stem
    document = Document(
        external_id=document_id(record["sha256"]),
        title=title[:500],
        source_url=record["url"],
        licence=(record.get("licence") or "")[:200],
        doc_type=parsed.kind,
        sha256=record["sha256"],
        metadata_={
            "source": record["source"],
            "path": record["path"],
            "parser": parsed.parser,
            "pages": len(parsed.pages),
            "tables": sum(p.tables for p in parsed.pages),
            "chars": sum(len(p.text) for p in parsed.pages),
        },
        pages=[Page(page_no=p.page_no, text=p.text, headings=p.headings) for p in parsed.pages],
    )
    session.add(document)
    await session.execute(delete(ParseFailure).where(ParseFailure.path == record["path"]))
    await session.commit()  # one transaction per file: a crash never leaves half a document


async def save_failure(session: AsyncSession, record: dict, error: ParseError) -> None:
    """Insert the failure, or count one more attempt if this file failed before."""
    row = {
        "path": record["path"],
        "sha256": record["sha256"],
        "source_url": record["url"],
        "reason": error.reason,
        "detail": error.detail,
    }
    stmt = insert(ParseFailure).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ParseFailure.path],
        set_={
            "reason": error.reason,
            "detail": error.detail,
            "attempts": ParseFailure.attempts + 1,
        },
    )
    await session.execute(stmt)
    await session.commit()

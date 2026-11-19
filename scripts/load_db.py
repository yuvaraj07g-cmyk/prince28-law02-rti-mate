"""Load data/sample_records.json into Postgres.

Safe to run again and again: new records are inserted, changed ones updated,
unchanged ones skipped (we compare a sha256 fingerprint of each record).
Run:  uv run python scripts/load_db.py
"""

import asyncio
import hashlib
import json
from datetime import date

from sqlalchemy import select, update

from rti_mate.config import get_settings
from rti_mate.db.models import Document
from rti_mate.db.session import make_engine, make_sessionmaker

TITLE_FIELD = "decision_no"  # the record field that best names a record
KNOWN = {"id", "title", "source_url", "licence", "doc_type", "published_on"}


def fingerprint(record: dict) -> str:
    canonical = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def to_row(record: dict) -> dict:
    published = record.get("published_on")
    return {
        "external_id": str(record["id"]),
        "title": str(record.get("title") or record.get(TITLE_FIELD) or record["id"]),
        "source_url": record.get("source_url"),
        "licence": record.get("licence"),
        "doc_type": record.get("doc_type") or "record",
        "published_on": date.fromisoformat(published) if published else None,
        "sha256": fingerprint(record),
        "metadata_": {k: v for k, v in record.items() if k not in KNOWN},
    }


async def main() -> None:
    settings = get_settings()
    records = json.loads(settings.data_file.read_text(encoding="utf-8"))
    engine = make_engine(settings)
    session_factory = make_sessionmaker(engine)
    inserted = updated = unchanged = 0
    async with session_factory() as session, session.begin():  # one transaction
        rows = await session.execute(select(Document.external_id, Document.sha256))
        existing = dict(rows.all())
        for record in records:
            row = to_row(record)
            old = existing.get(row["external_id"])
            if old is None:
                session.add(Document(**row))
                inserted += 1
            elif old != row["sha256"]:
                await session.execute(
                    update(Document).where(Document.external_id == row["external_id"]).values(**row)
                )
                updated += 1
            else:
                unchanged += 1
    await engine.dispose()
    print(f"records={len(records)} inserted={inserted} updated={updated} unchanged={unchanged}")


if __name__ == "__main__":
    asyncio.run(main())

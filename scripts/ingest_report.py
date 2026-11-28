"""Write docs/INGEST_REPORT.md from what is really in the database.

  uv run python scripts/ingest_report.py

Run it after an ingestion. The numbers between the markers are replaced on every run;
whatever you write outside the markers is kept.
"""

import asyncio
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from rti_mate.config import get_settings
from rti_mate.db.session import make_engine

REPORT = Path("docs/INGEST_REPORT.md")
START, END = "<!-- generated:start -->", "<!-- generated:end -->"

QUERIES = {
    "documents": "select count(*) from documents where doc_type <> 'record'",
    "pages": "select count(*) from pages",
    "characters": "select coalesce(sum(length(text)), 0) from pages",
    "parse_failures": "select count(*) from parse_failures",
    "extracted": "select count(*) from documents where metadata ? 'extract' "
    "and not (metadata->'extract' ? 'error')",
    "extract_failed": "select count(*) from documents where metadata->'extract' ? 'error'",
    "jobs": "select count(*) from ingest_jobs",
    "items_done": "select count(*) from ingest_items where status in ('done', 'skipped')",
    "dead_letter": "select count(*) from ingest_items where status = 'failed'",
    "retried": "select count(*) from ingest_items where attempts > 1",
    "model_calls": "select count(*) from llm_calls where purpose = 'extract'",
    "tokens_in": "select coalesce(sum(tokens_in), 0) from llm_calls where purpose = 'extract'",
    "tokens_out": "select coalesce(sum(tokens_out), 0) from llm_calls where purpose = 'extract'",
    "cost_inr": "select coalesce(sum(cost_inr), 0) from llm_calls where purpose = 'extract'",
}
LAST_JOB = """
select j.id, j.requested, extract(epoch from max(i.updated_at) - j.created_at) as seconds,
       count(*) filter (where i.status in ('done', 'skipped')) as ok,
       count(*) filter (where i.status = 'failed') as failed
from ingest_jobs j join ingest_items i on i.job_id = j.id
where j.id = (select id from ingest_jobs order by created_at desc limit 1)
group by j.id, j.requested, j.created_at
"""
REASONS = """
select split_part(error, ':', 1) as stage, count(*) from ingest_items
where status = 'failed' group by 1 order by 2 desc
"""


async def collect() -> tuple[dict, object, list]:
    engine = make_engine(get_settings())
    async with engine.connect() as conn:
        numbers = {name: (await conn.execute(text(sql))).scalar() for name, sql in QUERIES.items()}
        last = (await conn.execute(text(LAST_JOB))).first()
        reasons = (await conn.execute(text(REASONS))).all()
    await engine.dispose()
    return numbers, last, reasons


def render(n: dict, last, reasons: list) -> str:
    lines = [
        START,
        f"_Generated {datetime.now().astimezone():%d %b %Y %H:%M} from the database._",
        "",
        "| What | Count |",
        "|---|---|",
        f"| Documents in the database | {n['documents']} |",
        f"| Pages | {n['pages']} |",
        f"| Tokens of text (characters ÷ 4) | {n['characters'] // 4:,} |",
        f"| Files the parser gave up on | {n['parse_failures']} |",
        f"| Documents with an extracted record | {n['extracted']} |",
        f"| Documents whose extraction failed | {n['extract_failed']} |",
        "",
        "| Queue | Count |",
        "|---|---|",
        f"| Ingest jobs started | {n['jobs']} |",
        f"| Items finished (done or skipped) | {n['items_done']} |",
        f"| Items that needed more than one try | {n['retried']} |",
        f"| Items in the dead-letter list | {n['dead_letter']} |",
        "",
        f"Model calls for extraction: {n['model_calls']} · tokens in {n['tokens_in']:,} · "
        f"tokens out {n['tokens_out']:,} · cost at list price Rs {float(n['cost_inr']):.2f}",
    ]
    if last:
        minutes = float(last.seconds or 0) / 60
        lines += [
            "",
            f"Last job `{last.id}`: {last.requested} requested, {last.ok} ok, "
            f"{last.failed} failed, {minutes:.1f} minutes.",
        ]
    if reasons:
        lines += ["", "Dead-letter list by stage: " + ", ".join(f"{s} {c}" for s, c in reasons)]
    return "\n".join([*lines, END])


def main() -> int:
    numbers, last, reasons = asyncio.run(collect())
    block = render(numbers, last, reasons)
    if REPORT.exists() and START in (old := REPORT.read_text(encoding="utf-8")) and END in old:
        new = old[: old.index(START)] + block + old[old.index(END) + len(END) :]
    else:
        new = "# Ingestion report\n\n" + block + "\n\n## What I learnt\n\n(three lines, yours)\n"
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(new, encoding="utf-8")
    summary = f"documents={numbers['documents']} pages={numbers['pages']}"
    print(f"{summary} dead_letter={numbers['dead_letter']} -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

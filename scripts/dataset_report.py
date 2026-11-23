"""Write DATASET.md (where every file came from) and docs/CAPACITY.md (what the full corpus costs).

  uv run python scripts/dataset_report.py --full-pages 3000
  uv run python scripts/dataset_report.py --full-files 2500    if your target counts files

Only the part between the two "generated" markers is replaced, so your own notes stay.
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader

MANIFEST = Path("data/manifest.jsonl")
CACHE = Path("data/raw/.measured.json")  # so a second run is instant
START, END = "<!-- generated:start -->", "<!-- generated:end -->"
TEXT_EXT = {
    ".md", ".mdx", ".markdown", ".txt", ".rst", ".adoc", ".sgml", ".json", ".yaml", ".yml",
    ".csv", ".xml", ".py",
}  # fmt: skip
CHARS_PER_PAGE = 3000  # about 500 English words: one printed page
CHARS_PER_TOKEN = 4  # rule of thumb for English; you count real tokens on Day 8
PDF_SAMPLE = 5  # pages read per PDF to estimate its text
OVERLAP = 1.15  # chunks overlap by about 15% (you choose the real value on Day 11)

logging.getLogger("pypdf").setLevel(logging.ERROR)


class VisibleText(HTMLParser):
    """Counts the characters a reader would see: no tags, scripts or styles."""

    def __init__(self) -> None:
        super().__init__()
        self.chars = 0
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._hidden += tag in {"script", "style", "noscript"}

    def handle_endtag(self, tag: str) -> None:
        self._hidden -= tag in {"script", "style", "noscript"} and self._hidden > 0

    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self.chars += len(" ".join(data.split()))


def measure(path: Path) -> dict:
    """Pages and characters of one file. PDFs are sampled; text and HTML are read fully."""
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            reader = PdfReader(path)
            pages = len(reader.pages)
            step = max(1, pages // PDF_SAMPLE)
            sample = list(range(0, pages, step))[:PDF_SAMPLE]
            seen = sum(len(reader.pages[i].extract_text() or "") for i in sample)
            chars = round(seen / max(1, len(sample)) * pages)
            note = "almost no text: scanned?" if pages and chars / pages < 100 else ""
            return {"kind": "pdf", "pages": pages, "chars": chars, "note": note}
        if ext in {".html", ".htm"}:
            parser = VisibleText()
            parser.feed(path.read_text(encoding="utf-8", errors="replace"))
            return {"kind": "html", "pages": parser.chars / CHARS_PER_PAGE, "chars": parser.chars}
        if ext in TEXT_EXT:
            chars = len(path.read_text(encoding="utf-8", errors="replace"))
            return {"kind": "text", "pages": chars / CHARS_PER_PAGE, "chars": chars}
    except Exception as exc:  # a broken file must not stop the report
        return {"kind": "unreadable", "pages": 0, "chars": 0, "note": type(exc).__name__}
    return {"kind": "other", "pages": 0, "chars": 0, "note": "not measured"}


def load_records() -> list[dict]:
    latest: dict[str, dict] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        latest[record["url"]] = record
    return list(latest.values())


def measure_all(records: list[dict]) -> None:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    for number, record in enumerate(records, start=1):
        if record["sha256"] not in cache:
            cache[record["sha256"]] = measure(Path(record["path"]))
            if number % 100 == 0:
                print(f"measured {number} of {len(records)} files")
        record.update(cache[record["sha256"]])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache), encoding="utf-8")


def put_block(path: Path, title: str, block: str) -> None:
    """Replace the generated block, keep everything else. Creates the file if needed."""
    text = path.read_text(encoding="utf-8") if path.exists() else f"# {title}\n"
    wrapped = f"{START}\n{block.strip()}\n{END}"
    if START in text and END in text:
        text = text[: text.index(START)] + wrapped + text[text.index(END) + len(END) :]
    else:
        text = text.rstrip() + "\n\n" + wrapped + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def cell(value: object) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ").strip()


def dataset_block(done: list[dict], not_done: list[dict], today: str) -> str:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in done:
        groups[record["source"]].append(record)
    rows = []
    for name, items in sorted(groups.items()):
        how = sorted({r.get("via", "http") for r in items})
        commit = next((r["commit"][:10] for r in items if r.get("commit")), "")
        size = sum(r["bytes"] for r in items) / 1e6
        pages = round(sum(r["pages"] for r in items))
        fetched = max(r["fetched_at"] for r in items)[:10]
        rows.append(
            f"| {cell(name)} | {cell(items[0]['licence'])} | {len(items)} | {size:.1f} | {pages:,} "
            f"| {'+'.join(how)}{' @ ' + commit if commit else ''} | {fetched} | {items[0]['url']} |"
        )
    blocked = sum(r["status"] == "blocked" for r in not_done)
    failed = sum(r["status"] == "failed" for r in not_done)
    listed = sorted(done, key=lambda r: (r["source"], r["path"]))[:200]
    files = [
        f"| {i} | {cell(r.get('title') or Path(r['path']).name)} | {cell(r['source'])} "
        f"| {round(r['pages']) or ''} | {r['fetched_at'][:10]} | {r['url']} |"
        for i, r in enumerate(listed, start=1)
    ]
    total_mb = sum(r["bytes"] for r in done) / 1e6
    total_pages = round(sum(r["pages"] for r in done))
    return "\n".join(
        [
            f"## Sources (generated {today} UTC by scripts/dataset_report.py)",
            "",
            "| Source | Licence / terms | Files | MB | Pages* | How | Fetched | Example URL |",
            "|---|---|---|---|---|---|---|---|",
            *rows,
            "",
            f"**Total:** {len(done):,} files, {total_mb:.1f} MB, {total_pages:,} pages. "
            f"Not downloaded: {blocked} blocked by robots.txt, {failed} failed.",
            "",
            "*Pages = PDF pages, plus one page per 3,000 characters of text or HTML.",
            "",
            f"## Files (first {len(listed)} of {len(done):,})",
            "",
            "The complete list, with a sha256 fingerprint of every file, is `data/manifest.jsonl`.",
            "",
            "| # | Title / file | Source | Pages | Fetched | URL |",
            "|---|---|---|---|---|---|",
            *files,
        ]
    )


def capacity_block(done: list[dict], args: argparse.Namespace, today: str) -> str:
    files, size_mb = len(done), sum(r["bytes"] for r in done) / 1e6
    pages = sum(r["pages"] for r in done)
    chars = sum(r["chars"] for r in done)
    tokens = chars / CHARS_PER_TOKEN
    scanned = sum(1 for r in done if "scanned" in r.get("note", ""))
    skipped = sum(1 for r in done if r["kind"] in {"other", "unreadable"})
    if args.full_pages:
        scale, target = args.full_pages / pages, f"{args.full_pages:,} pages"
    else:
        scale, target = args.full_files / files, f"{args.full_files:,} files"
    full_tokens = tokens * scale
    chunks = full_tokens / args.chunk_tokens * OVERLAP
    embed_usd = full_tokens * OVERLAP / 1e6 * args.embed_usd
    vector_mb = chunks * args.dims * 4 / 1e6
    text_mb = chars * scale * 1.2 / 1e6
    return "\n".join(
        [
            f"## Measured on my start corpus ({today} UTC)",
            "",
            "| What | Value |",
            "|---|---|",
            f"| Files | {files:,} |",
            f"| Size on disk | {size_mb:.1f} MB |",
            f"| Pages (PDF pages + 1 per 3,000 characters of text/HTML) | {pages:,.0f} |",
            f"| Characters of text | {chars:,} |",
            f"| Estimated tokens (characters / {CHARS_PER_TOKEN}) | {tokens:,.0f} |",
            f"| Tokens per page | {tokens / pages:,.0f} |",
            f"| PDFs with almost no text (scanned? OCR is Day 7) | {scanned} |",
            f"| Files not measured (zip, xlsx, unreadable) | {skipped} |",
            "",
            f"## Estimate for the full corpus (target: {target})",
            "",
            "| What | How | Value |",
            "|---|---|---|",
            f"| Scale factor | target / measured | x {scale:.1f} |",
            f"| Tokens | measured tokens x scale | {full_tokens / 1e6:.2f} M |",
            f"| Raw files | measured MB x scale | {size_mb * scale:,.0f} MB |",
            f"| Chunks | tokens / {args.chunk_tokens} x {OVERLAP} overlap | {chunks:,.0f} |",
            f"| Embedding cost, one time | tokens x {OVERLAP} x ${args.embed_usd} per 1M "
            f"| ${embed_usd:,.2f} = Rs {embed_usd * args.usd_inr:,.0f} |",
            f"| Vector storage | chunks x {args.dims} numbers x 4 bytes | {vector_mb:,.0f} MB |",
            f"| Text in Postgres | characters x scale x 1.2 | {text_mb:,.0f} MB |",
            "",
            f"Assumptions: {CHARS_PER_TOKEN} characters per token, "
            f"{args.chunk_tokens}-token chunks, {args.dims}-dimension embeddings "
            f"at ${args.embed_usd} per 1M tokens, Rs {args.usd_inr:g} per US dollar.",
        ]
    )


def main() -> int:
    sys.stdout.reconfigure(errors="replace")  # odd characters never crash a Windows console
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    goal = parser.add_mutually_exclusive_group(required=True)
    goal.add_argument("--full-pages", type=int, help="pages in your FULL corpus target")
    goal.add_argument("--full-files", type=int, help="files in your FULL corpus target")
    parser.add_argument("--embed-usd", type=float, default=0.15, help="embedding $ per 1M tokens")
    parser.add_argument("--usd-inr", type=float, default=95.0, help="rupees per US dollar")
    parser.add_argument("--dims", type=int, default=768, help="numbers per embedding vector")
    parser.add_argument("--chunk-tokens", type=int, default=400)
    args = parser.parse_args()
    if not MANIFEST.exists():
        print("data/manifest.jsonl not found: run scripts/fetch.py first")
        return 1
    records = load_records()
    done = [r for r in records if r["status"] == "downloaded" and Path(r["path"]).is_file()]
    not_done = [r for r in records if r["status"] != "downloaded"]
    measure_all(done)
    if not sum(r["pages"] for r in done):
        print("nothing measurable yet: download some PDF, HTML or text files first")
        return 1
    today = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    put_block(Path("DATASET.md"), "Dataset", dataset_block(done, not_done, today))
    put_block(Path("docs/CAPACITY.md"), "Capacity plan", capacity_block(done, args, today))
    pages = sum(r["pages"] for r in done)
    print(f"files={len(done)} pages={pages:,.0f} -> wrote DATASET.md and docs/CAPACITY.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

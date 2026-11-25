"""Compare two parsers on your hardest files and write the table into NOTES.md.

  uv run python scripts/compare_parsers.py                     your 10 biggest PDF / HTML files
  uv run python scripts/compare_parsers.py data/raw/a.pdf ...  the files you choose

PDF: PyMuPDF against pypdf. HTML: trafilatura against simply stripping the tags.
Text files (Markdown, reStructuredText, YAML ...) have one parser, so you check headings by eye.
"""

import json
import re
import sys
import time
from pathlib import Path

from rti_mate.ingest.parse import (
    ParsedDoc,
    ParseError,
    finish,
    headings_in,
    parse_file,
    split_pages,
)

MANIFEST = Path("data/manifest.jsonl")
NOTES = Path("NOTES.md")
START, END = "<!-- parsers:start -->", "<!-- parsers:end -->"


def strip_tags(path: Path) -> ParsedDoc:
    """The naive HTML "parser": delete every tag and keep whatever text is left."""
    html = path.read_text(encoding="utf-8", errors="replace")
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return finish("strip-tags", "html", "", split_pages(re.sub(r"(?s)<[^>]+>", " ", html)))


def measure(parser, path: Path) -> dict:
    started = time.perf_counter()
    try:
        doc = parser(path)
    except ParseError as error:
        return {"ok": False, "note": error.reason, "seconds": time.perf_counter() - started}
    text = "\n".join(page.text for page in doc.pages)
    return {
        "ok": True,
        "pages": len(doc.pages),
        "chars": len(text),
        "headings": len(headings_in(text)[0]),
        "tables": sum(page.tables for page in doc.pages),
        "seconds": time.perf_counter() - started,
    }


def pick_files() -> list[Path]:
    """Default choice: the 10 biggest PDF and HTML files (or text files if there are none)."""
    records = [json.loads(ln) for ln in MANIFEST.read_text(encoding="utf-8").splitlines() if ln]
    files = {r["path"]: r.get("bytes", 0) for r in records if r.get("status") == "downloaded"}
    by_size = sorted((p for p in files if Path(p).is_file()), key=lambda p: -files[p])
    rich = [p for p in by_size if Path(p).suffix.lower() in {".pdf", ".html", ".htm"}]
    return [Path(p) for p in (rich or by_size)[:10]]


def cells(result: dict) -> str:
    if not result["ok"]:
        return f"FAILED: {result['note']}"
    return f"{result['chars']:,} chars, {result['headings']} headings, {result['tables']} tables"


def main() -> int:
    sys.stdout.reconfigure(errors="replace")
    files = [Path(arg) for arg in sys.argv[1:]] or pick_files()
    rows = []
    for path in files:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            a = measure(parse_file, path)
            b = measure(lambda p: parse_file(p, pdf_parser="pypdf"), path)
            names = "PyMuPDF / pypdf"
        elif suffix in {".html", ".htm"}:
            a, b, names = (
                measure(parse_file, path),
                measure(strip_tags, path),
                "trafilatura / strip tags",
            )
        else:
            a, b, names = measure(parse_file, path), None, "plain (check headings by eye)"
        pages = a.get("pages", "-")
        speed = f"{a['seconds']:.2f} s" + (f" / {b['seconds']:.2f} s" if b else "")
        rows.append(
            f"| {path.name[:48]} | {names} | {pages} | {cells(a)} | {cells(b) if b else '-'} "
            f"| {speed} | |"
        )
        print(rows[-1])
    table = "\n".join(
        [
            START,
            "| File | Parsers (A / B) | Pages | A found | B found | Time (A / B) | Better, why |",
            "|---|---|---|---|---|---|---|",
            *rows,
            END,
        ]
    )
    text = NOTES.read_text(encoding="utf-8") if NOTES.exists() else "# Notes\n"
    if START in text and END in text:
        text = text[: text.index(START)] + table + text[text.index(END) + len(END) :]
    else:
        text = text.rstrip() + "\n\n## D07 · Parser comparison\n\n" + table + "\n"
    NOTES.write_text(text, encoding="utf-8")
    print(f"compared {len(rows)} files -> table written to NOTES.md (fill in the last column)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

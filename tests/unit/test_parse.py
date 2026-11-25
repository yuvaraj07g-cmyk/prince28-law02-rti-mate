"""The parser, tested on small files the tests build themselves (no binary files in Git)."""

from pathlib import Path

import pymupdf
import pytest

from rti_mate.ingest import parse
from rti_mate.ingest.parse import ParseError, parse_file

BODY = "Dengue is a viral infection spread by Aedes mosquitoes and is common after the rains."


def make_pdf(path: Path, pages: list[list[tuple[str, float]]]) -> Path:
    """Each page is a list of (text, font size) lines."""
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        y = 72.0
        for text, size in lines:
            page.insert_text((72, y), text, fontsize=size)
            y += size * 1.8
    doc.save(path)
    return path


def body_page(*extra: tuple[str, float]) -> list[tuple[str, float]]:
    return [*extra, *[(BODY, 11.0)] * 6]


def test_pdf_pages_keep_their_numbers(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf", [body_page(("First", 11)), body_page(("Second", 11))])
    doc = parse_file(pdf)
    assert doc.kind == "pdf" and doc.parser == "pymupdf"
    assert [p.page_no for p in doc.pages] == [1, 2]
    assert "First" in doc.pages[0].text and "Second" in doc.pages[1].text


def test_big_fonts_become_headings_and_the_path_follows_the_pages(tmp_path):
    pdf = make_pdf(
        tmp_path / "guide.pdf",
        [
            body_page(("Fever Guidelines", 22), ("Dengue", 15)),
            body_page(),
            body_page(("Malaria", 15)),
        ],
    )
    doc = parse_file(pdf)
    assert "# Fever Guidelines" in doc.pages[0].text and "## Dengue" in doc.pages[0].text
    assert doc.pages[0].headings == []  # nothing came before page 1
    assert doc.pages[1].headings == ["Fever Guidelines", "Dengue"]  # page 2 continues Dengue
    assert doc.pages[2].headings == ["Fever Guidelines", "Dengue"]
    assert doc.title == "Fever Guidelines"


def test_a_table_becomes_markdown(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 60), BODY, fontsize=11)
    rows = [["Drug", "Dose", "Days"], ["Paracetamol", "500 mg", "3"], ["ORS", "200 ml", "2"]]
    left, top, width, height = 72, 100, 120, 24
    for r in range(len(rows) + 1):
        page.draw_line((left, top + r * height), (left + 3 * width, top + r * height))
    for c in range(4):
        page.draw_line((left + c * width, top), (left + c * width, top + len(rows) * height))
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            page.insert_text((left + c * width + 6, top + r * height + 16), cell, fontsize=10)
    doc.save(tmp_path / "table.pdf")
    parsed = parse_file(tmp_path / "table.pdf")
    text = parsed.pages[0].text
    assert "|Drug|Dose|Days|" in text.replace(" ", "")
    assert "|Paracetamol|500mg|3|" in text.replace(" ", "")
    assert parsed.pages[0].tables == 1
    assert text.count("Paracetamol") == 1  # the cells are not repeated as loose text


def test_a_scanned_pdf_is_a_recorded_failure_not_a_crash(tmp_path):
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page()  # pages with no text layer, like a scan
    doc.save(tmp_path / "scan.pdf")
    with pytest.raises(ParseError) as error:
        parse_file(tmp_path / "scan.pdf")
    assert error.value.reason == "no_text_layer"


def test_a_broken_file_is_reported_as_corrupt(tmp_path):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"%PDF-1.7 this is not really a pdf")
    for parser in ("pymupdf", "pypdf"):
        with pytest.raises(ParseError) as error:
            parse_file(bad, pdf_parser=parser)
        assert error.value.reason in {"corrupt", "empty"}


def test_a_password_protected_pdf_is_reported_as_encrypted(tmp_path):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), BODY)
    locked = tmp_path / "locked.pdf"
    doc.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    with pytest.raises(ParseError) as error:
        parse_file(locked)
    assert error.value.reason == "encrypted"


def test_repeated_headers_and_footers_are_removed(tmp_path):
    topics = ["Dengue", "Malaria", "Typhoid", "Cholera", "Measles"]
    pages = [
        [
            ("Ministry of Health - Circular 12", 11),
            *[(f"{topic} step {k}: rest, fluids and review after two days.", 11) for k in "abcde"],
            (f"Page {n} of 5", 11),
        ]
        for n, topic in enumerate(topics, start=1)
    ]
    doc = parse_file(make_pdf(tmp_path / "circular.pdf", pages))
    whole = "\n".join(p.text for p in doc.pages)
    assert "Ministry of Health" not in whole and "Page 3 of 5" not in whole
    assert whole.count("review after two days") == 25  # the real text is all still there


def test_both_pdf_parsers_agree_on_the_page_count(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf", [body_page(), body_page(), body_page()])
    assert len(parse_file(pdf, pdf_parser="pypdf").pages) == len(parse_file(pdf).pages) == 3


def test_clean_text_repairs_what_pdfs_break():
    dirty = "The ﬁrst treat-\nment\x00 is   rest.­\n\n\n\nNext."
    assert parse.clean_text(dirty) == "The first treatment is rest.\n\nNext."


def test_tamil_text_survives_cleaning():
    kural = "அகர முதல எழுத்தெல்லாம் ஆதி பகவன் முதற்றே உலகு"
    assert parse.clean_text(f"  {kural}  ") == kural


def test_markdown_gets_pages_and_a_heading_path(tmp_path):
    md = tmp_path / "tutorial.md"
    para = "FastAPI reads the path parameter and converts it to the type you declared. " * 12
    md.write_text(
        f"# Tutorial\n\n{para}\n\n## Path Parameters\n\n{para}\n\n{para}\n\n{para}\n\n{para}"
    )
    doc = parse_file(md)
    assert doc.kind == "text" and doc.title == "Tutorial"
    assert len(doc.pages) >= 2
    assert doc.pages[-1].headings == ["Tutorial", "Path Parameters"]


def test_rst_and_asciidoc_headings_are_understood(tmp_path):
    rst = tmp_path / "models.rst"
    rst.write_text(
        "Models\n======\n\nA model maps to a table.\n\nFields\n------\n\nEach field is a column.\n"
    )
    text = parse_file(rst).pages[0].text
    assert "# Models" in text and "## Fields" in text and "======" not in text
    adoc = tmp_path / "boot.adoc"
    adoc.write_text("= Spring Boot\n\n== Getting Started\n\nRun the application class.\n")
    assert "## Getting Started" in parse_file(adoc).pages[0].text


def test_html_keeps_the_article_and_drops_the_menu(tmp_path):
    html = tmp_path / "page.html"
    article = "".join(f"<p>{BODY} Paragraph number {i}.</p>" for i in range(8))
    html.write_text(
        "<html><head><title>Dengue advice</title><script>var tracking = 1;</script></head><body>"
        "<nav><a href='/'>Home</a><a href='/login'>Login</a><a href='/tenders'>Tenders</a></nav>"
        f"<main><article><h1>Dengue advice</h1><h2>Symptoms</h2>{article}</article></main>"
        "<footer>Copyright 2026. Site map. Visitor count 123456.</footer></body></html>"
    )
    doc = parse_file(html)
    text = "\n".join(p.text for p in doc.pages)
    assert doc.kind == "html" and "Paragraph number 7" in text and "## Symptoms" in text
    assert "tracking" not in text and "Tenders" not in text and "Visitor count" not in text


def test_an_empty_file_and_an_unknown_type_fail_with_a_reason(tmp_path):
    (tmp_path / "empty.txt").write_text("   \n\n  ")
    (tmp_path / "archive.zip").write_bytes(b"PK\x03\x04")
    with pytest.raises(ParseError) as error:
        parse_file(tmp_path / "empty.txt")
    assert error.value.reason == "empty"
    with pytest.raises(ParseError) as error:
        parse_file(tmp_path / "archive.zip")
    assert error.value.reason == "unsupported_type"


def test_split_pages_cuts_on_blank_lines():
    text = "\n\n".join(f"Paragraph {i} " + "x" * 900 for i in range(10))
    pages = parse.split_pages(text)
    assert len(pages) == 4 and all(len(p) <= 3200 for p in pages)
    assert "\n\n".join(pages) == text  # nothing lost, nothing repeated


def test_comments_inside_code_blocks_are_not_headings(tmp_path):
    md = tmp_path / "guide.md"
    md.write_text(
        "# Install { #install }\n\nRun this:\n\n```bash\n# Print a greeting\necho hello\n```\n\n"
        "## Next steps { #next }\n\nRead the tutorial.\n"
    )
    doc = parse_file(md)
    found, _ = parse.headings_in(doc.pages[0].text)
    assert found == [(1, "Install"), (2, "Next steps")]
    assert doc.title == "Install"

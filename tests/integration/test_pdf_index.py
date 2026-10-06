from pypdf import PdfReader, PdfWriter

from dt_ai.core.io import digest
from dt_ai.drawing.index import index_pdf


def test_pdf_index_preserves_source_pages_and_marks_blank(root, tmp_path):
    source = next((root / "standards/source").glob("*.pdf"))
    writer = PdfWriter()
    writer.add_page(PdfReader(source).pages[0])
    writer.add_blank_page(width=595, height=842)
    path = tmp_path / "fixture.pdf"
    with path.open("wb") as stream:
        writer.write(stream)
    result = index_pdf(path, tmp_path / "index")
    assert result["source_sha256"] == digest(path.read_bytes())
    assert [p["page"] for p in result["pages"]] == [1, 2]
    assert result["pages"][0]["text_characters"] > 500
    assert result["pages"][1]["status"] == "needs_ocr"
    assert result["pages"][0]["id"] != result["pages"][1]["id"]
    assert all(len(p["region_pdf_points"]) == 4 for p in result["pages"])

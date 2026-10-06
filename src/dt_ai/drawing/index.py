from pathlib import Path

from pypdf import PdfReader

from dt_ai.core.io import digest, write_json


def index_pdf(source: Path, output: Path):
    """Text and embedded-image inventory; no OCR or automatic material approval."""
    sha = digest(source.read_bytes())
    reader = PdfReader(source)
    output.mkdir(parents=True, exist_ok=True)
    pages = []
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        path = output / f"page-{number:03}.txt"
        path.write_text(text, encoding="utf-8")
        images = []
        for i, im in enumerate(page.images):
            suffix = Path(im.name).suffix or ".bin"
            target = output / f"page-{number:03}-image-{i:03}{suffix}"
            target.write_bytes(im.data)
            images.append({"file": target.name, "sha256": digest(im.data)})
        pages.append({"id": f"{sha[:16]}:page:{number}", "page": number,
                      "text_file": path.name, "text_characters": len(text),
                      "status": "extracted_needs_visual_review" if text.strip() else "needs_ocr",
                      "region_pdf_points": [float(x) for x in page.mediabox], "images": images})
    result = {"schema_version": "1.0.0", "source_file": source.name, "source_sha256": sha,
              "pages": pages, "limitations": ["No OCR, drawing semantics, dimensions or material inference."]}
    write_json(output / "index.json", result)
    return result

"""docs/agr/ is opened only through docs/agr/INDEX.md, which lists every document there (#120)."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROW = re.compile(r"^\| `([^`]+)` \|")


def test_index_lists_every_document_once():
    listed = subprocess.run(["git", "ls-files", "docs/agr"], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8")
    assert listed.returncode == 0, listed.stderr
    tracked = {p.removeprefix("docs/agr/") for p in listed.stdout.splitlines()} - {"INDEX.md"}
    text = (ROOT / "docs/agr/INDEX.md").read_text(encoding="utf-8")
    rows = [m.group(1) for line in text.splitlines() if (m := ROW.match(line))]
    assert len(rows) == len(set(rows)), "a document is listed twice"
    assert set(rows) == tracked

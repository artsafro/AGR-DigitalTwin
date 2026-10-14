"""docs/decisions.md: one dated user decision per line, referenced where it applies (#120)."""
import datetime
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = "docs/decisions.md"
ROW = re.compile(r"^\| (D\d{3}) \|")
REF = re.compile(r"\[(D\d{3}(?:, D\d{3})*)\]")
# A dated user decision in prose: "user ... 2026-10-08" or "2026-10-08 ... user" on one line.
MENTION = re.compile(
    r"(user|пользовател).{0,40}2026-\d\d-\d\d|2026-\d\d-\d\d.{0,25}(user|пользовател)", re.IGNORECASE)
# Files with no decisions of their own: history, research, the spec, Russian originals, state and handoff.
EXCLUDED = ("docs/agr/", "docs/research/", "docs/prd/", "jobs/", "technical_library/", "data/",
            "docs/HANDOFF", "docs/PROJECT_STATE.md", LOG)
# Lines that match MENTION but state no decision: (file, text on the line).
NOT_DECISIONS = [
    ("docs/backlog.md", "AGR_Project-uncommitted-2026-10-06.zip"),  # an archive name next to "the user plans"
]


def log_rows():
    rows = []
    for line in (ROOT / LOG).read_text(encoding="utf-8").splitlines():
        if ROW.match(line):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def scope_files():
    listed = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8")
    assert listed.returncode == 0, listed.stderr
    return [f for f in listed.stdout.splitlines() if not f.startswith(EXCLUDED)]


def unreferenced(files, known_ids):
    problems = []
    for name in files:
        for n, line in enumerate((ROOT / name).read_text(encoding="utf-8").splitlines(), 1):
            if not MENTION.search(line) or any(f == name and t in line for f, t in NOT_DECISIONS):
                continue
            refs = [i for group in REF.findall(line) for i in group.split(", ")]
            if not refs:
                problems.append(f"{name}:{n}: dated user decision without [D<n>]")
            problems += [f"{name}:{n}: unknown {i}" for i in refs if i not in known_ids]
    return problems


def test_log_format():
    rows = log_rows()
    assert rows, "no decisions"
    dates = []
    for number, row in enumerate(rows, 1):
        assert len(row) == 5 and all(row), row
        assert row[0] == f"D{number:03d}", f"{row[0]}: ids must run D001, D002, ... without gaps"
        dates.append(datetime.date.fromisoformat(row[1]))
    assert dates == sorted(dates), "decisions must be sorted by date"


def test_every_dated_decision_carries_its_id():
    known = {row[0] for row in log_rows()}
    assert unreferenced(scope_files(), known) == []


def test_unreferenced_mentions_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(__import__(__name__), "ROOT", tmp_path)
    (tmp_path / "a.md").write_text(
        "Rule (user 2026-10-12): x.\nRule (пользователь 2026-10-12 [D999]).\nOK (user 2026-10-12 [D001]).\n",
        encoding="utf-8")
    problems = unreferenced(["a.md"], {"D001"})
    assert problems == ["a.md:1: dated user decision without [D<n>]", "a.md:2: unknown D999"]

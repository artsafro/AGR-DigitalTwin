"""docs/PROJECT_STATE.md is a state file: fixed sections, at most 80 lines (#119)."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "docs" / "PROJECT_STATE.md"
OLD_STATE_COMMIT = "5b1a5b2"  # main before #119: the history-shaped file
MAX_LINES = 80
TITLE = "Project state"
SECTIONS = ["Goal", "In production", "Harness", "Next step", "Links"]

ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")


def headings(lines):
    """Every Markdown heading as (level, text): ATX in any form, and setext."""
    found = []
    for i, line in enumerate(lines):
        match = ATX.match(line)
        if match:
            found.append((len(match.group(1)), (match.group(2) or "").strip()))
        elif SETEXT.match(line) and i and lines[i - 1].strip() and not ATX.match(lines[i - 1]):
            found.append((1 if "=" in line else 2, lines[i - 1].strip()))
    return found


def state_problems(text):
    problems = []
    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        problems.append(f"{len(lines)} lines, limit {MAX_LINES}")
    expected = [(1, TITLE)] + [(2, name) for name in SECTIONS]
    found = headings(lines)
    if found != expected:
        problems.append(f"headings {found}, expected {expected}")
    return problems


def test_project_state_is_a_state_file():
    assert state_problems(STATE.read_text(encoding="utf-8")) == []


def test_old_history_shaped_file_fails():
    old = subprocess.run(
        ["git", "show", f"{OLD_STATE_COMMIT}:docs/PROJECT_STATE.md"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert old.returncode == 0, old.stderr
    problems = state_problems(old.stdout)
    assert any("lines" in p for p in problems)
    assert any("headings" in p for p in problems)


def body(*heading_lines):
    return "\n".join(["# Project state", *heading_lines])


def test_wrong_section_set_fails():
    assert state_problems(body(*(f"## {n}" for n in SECTIONS + ["History"])))
    assert state_problems(body(*(f"## {n}" for n in SECTIONS[:-1])))
    assert state_problems(body(*(f"## {n}" for n in reversed(SECTIONS))))
    assert state_problems(body(*(f"## {n}" for n in SECTIONS), "### History"))


def test_any_heading_form_counts():
    five = [f"## {n}" for n in SECTIONS]
    assert state_problems(body(*five)) == []
    for extra in [" ## History", "##\tHistory", "   ## History ##", "##", "History\n---", "# History"]:
        assert state_problems(body(*five, "", extra)), extra
    assert state_problems(body(*five, "", "text", "", "---")) == []

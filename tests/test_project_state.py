"""docs/PROJECT_STATE.md is a state file: fixed sections, at most 80 lines (#119)."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "docs" / "PROJECT_STATE.md"
MAX_LINES = 80
SECTIONS = ["Goal", "In production", "Harness", "Next step", "Links"]


def state_problems(text):
    problems = []
    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        problems.append(f"{len(lines)} lines, limit {MAX_LINES}")
    headings = [line[3:].strip() for line in lines if line.startswith("## ")]
    if headings != SECTIONS:
        problems.append(f"sections {headings}, expected {SECTIONS}")
    return problems


def test_project_state_is_a_state_file():
    assert state_problems(STATE.read_text(encoding="utf-8")) == []


def test_history_shaped_state_fails():
    old = subprocess.run(
        ["git", "show", "5b1a5b2:docs/PROJECT_STATE.md"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    text = old.stdout if old.returncode == 0 else (
        "# Project state\n\n## Current goal\n" + "merged PR line\n" * 120)
    problems = state_problems(text)
    assert any("lines" in p for p in problems)
    assert any("sections" in p for p in problems)


def test_extra_or_missing_section_fails():
    text = "\n".join(f"## {name}" for name in SECTIONS + ["History"])
    assert state_problems(text)
    text = "\n".join(f"## {name}" for name in SECTIONS[:-1])
    assert state_problems(text)

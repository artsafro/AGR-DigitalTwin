"""Context rotation: tools/hooks/session_context.py, its wiring, the handoff template and the two commands."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "tools/hooks/session_context.py"
SECTIONS = ["Where we are", "In progress", "User decisions not in the code", "Waiting for the user", "Next step",
            "Rules broken", "Open PRs and issues for this task"]


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True,
                   capture_output=True)


def handoff(branch, extra=""):
    return f"# Handoff — 2026-10-14\n\nBranch: `{branch}` · Commit: `abc1234` · Job: `-`\n\n## Next step\n\nDo X.\n{extra}"


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "task/a")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/HANDOFF.md").write_text(handoff("task/a"), encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "Handoff: do X")
    return tmp_path


def run(mode, payload, repo):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo),
           "PATH": os.path.dirname(shutil.which("git"))}          # no gh: the test stays offline
    r = subprocess.run([sys.executable, str(HOOK), mode], input=json.dumps(payload), capture_output=True,
                       text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout


def start(repo, source):
    raw = run("start", {"source": source}, repo)
    assert raw.isascii()                                          # survives any console code page
    out = json.loads(raw)["hookSpecificOutput"]
    assert out["hookEventName"] == "SessionStart"
    return out["additionalContext"]


def test_hooks_are_wired():
    hooks = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    entry = hooks["SessionStart"][0]
    assert all(re.search(entry["matcher"], s) for s in ("startup", "clear", "compact"))
    assert not re.search(entry["matcher"], "resume")              # a resumed session has its own context
    assert entry["hooks"][0]["command"].endswith('session_context.py" start')
    pre = hooks["PreCompact"][0]
    assert all(re.search(pre["matcher"], s) for s in ("manual", "auto"))
    assert pre["hooks"][0]["command"].endswith('session_context.py" precompact')


def test_current_handoff(repo):
    ctx = start(repo, "clear")
    assert "Branch: task/a" in ctx
    assert "Handoff: current" in ctx and "--- docs/HANDOFF.md ---" in ctx and "Do X." in ctx
    assert "Handoff: do X" in ctx                                 # the last commits
    assert "(gh not found)" in ctx and "продолжай" in ctx


def test_stale_foreign_and_old_handoffs_are_flagged(repo):
    (repo / "x.txt").write_text("x", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "work")
    ctx = start(repo, "startup")
    assert "1 commit(s) after the last commit" in ctx and "?? " not in ctx
    git(repo, "switch", "-q", "-c", "task/b")
    assert "belongs to branch `task/a`" in start(repo, "startup")
    (repo / "docs/HANDOFF.md").write_text("# Handoff\n\nold format\n", encoding="utf-8")
    ctx = start(repo, "startup")
    assert "no `Branch:` line" in ctx and "uncommitted changes" in ctx and "?? " not in ctx


def test_compact_with_a_stale_handoff_asks_for_a_checkpoint(repo):
    assert "checkpoint procedure" not in start(repo, "compact")
    (repo / "x.txt").write_text("x", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "work")
    assert "run the /checkpoint procedure" in start(repo, "compact")
    assert "checkpoint procedure" not in start(repo, "startup")


def test_long_handoff_is_cut_under_the_hook_cap(repo):
    (repo / "docs/HANDOFF.md").write_text(handoff("task/a", "line of text\n" * 2000), encoding="utf-8")
    ctx = start(repo, "startup")
    assert len(ctx) < 10_000 and "cut at" in ctx


def test_precompact(repo):
    log = repo / ".git/agr-compactions.log"
    assert run("precompact", {"trigger": "manual", "custom_instructions": None}, repo) == ""   # current: passes
    (repo / "x.txt").write_text("x", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "work")
    out = json.loads(run("precompact", {"trigger": "manual", "custom_instructions": None}, repo))
    assert out["decision"] == "block" and "/checkpoint" in out["reason"]
    assert run("precompact", {"trigger": "manual", "custom_instructions": "force"}, repo) == ""
    assert run("precompact", {"trigger": "auto", "custom_instructions": None}, repo) == ""   # never blocks auto
    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert [x["trigger"] for x in lines] == ["manual", "manual", "manual", "auto"]
    assert lines[-1]["handoff_warnings"]


def test_unreadable_input_does_not_break_the_session(repo):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo), "PATH": os.path.dirname(shutil.which("git"))}
    r = subprocess.run([sys.executable, str(HOOK), "start"], input="not json", capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "Session context (startup" in json.loads(r.stdout)["hookSpecificOutput"][
        "additionalContext"]


def test_template_has_every_section_and_a_parsable_branch_line():
    text = (ROOT / "docs/HANDOFF.template.md").read_text(encoding="utf-8")
    assert re.search(r"^Branch:\s*`[^`]+`.*Commit:\s*`", text, re.M)
    assert [s for s in SECTIONS if f"\n## {s}\n" not in text] == []


@pytest.mark.parametrize("name", ["checkpoint", "resume"])
def test_commands(name):
    text = (ROOT / f".claude/commands/{name}.md").read_text(encoding="utf-8")
    meta = yaml.safe_load(text.split("---\n")[1])
    assert meta["disable-model-invocation"] is True and meta["description"]
    assert "!`py -3 tools/hooks/session_context.py report`" in text
    if name == "checkpoint":
        assert "HANDOFF.template.md" in text and "Чекпоинт готов, можно /clear" in text
    else:
        assert "Wait for the user's «да»" in text

"""Auto-generated worktree branches: the pattern, the pre-commit block and the SessionStart prompt (user 2026-10-14)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/git-hooks"))
from branch_names import is_auto  # noqa: E402

GATE = ROOT / "tools/git-hooks/pipeline_gate.py"
SESSION = ROOT / "tools/hooks/session_context.py"


@pytest.mark.parametrize("branch, auto", [
    ("claude/laughing-hawking-e62961", True),
    ("claude/kanban-project-4bec5c", True),
    ("claude/3d-max-floor-modeling-742570", True),
    ("claude/checkpoint-resume-rotation-d361be", True),
    ("brave-otter-a1b2c3", True),
    ("codex/quiet-lake-0f9e8d", True),
    ("main", False), ("", False),
    ("harness/checkpoint-resume", False),
    ("job/obj03-decor", False),
    ("codex/b01-etalon-20261010", False),                  # eight digits: a date, not a worktree suffix
    ("harness/fix-abc123", False),                          # a NAMING prefix is never auto
    ("claude/laughing-hawking-E62961", False),
    ("feature/extract-spec-mesh-v1", False),
])
def test_pattern(branch, auto):
    assert is_auto(branch) is auto


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True,
                          capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def gate(repo):
    return subprocess.run([sys.executable, str(GATE), "--staged"], cwd=repo, capture_output=True, text=True)


def test_gate_blocks_a_commit_on_an_auto_branch_until_renamed(repo):
    git(repo, "switch", "-q", "-c", "claude/brave-otter-a1b2c3")
    (repo / "b.txt").write_text("b", encoding="utf-8")
    git(repo, "add", ".")
    r = gate(repo)
    assert r.returncode == 1 and "auto-generated worktree name" in r.stderr and "git branch -m" in r.stderr
    git(repo, "branch", "-m", "harness/otter-notes")
    assert gate(repo).returncode == 0


def test_a_tag_of_the_same_name_does_not_hide_the_branch(repo):      # review 3 of #107
    git(repo, "switch", "-q", "-c", "claude/brave-otter-a1b2c3")
    git(repo, "tag", "claude/brave-otter-a1b2c3")
    (repo / "b.txt").write_text("b", encoding="utf-8")
    git(repo, "add", ".")
    assert gate(repo).returncode == 1


def test_gate_passes_main_and_a_detached_head(repo):
    (repo / "b.txt").write_text("b", encoding="utf-8")
    git(repo, "add", ".")
    assert gate(repo).returncode == 0
    git(repo, "switch", "-q", "--detach")
    assert gate(repo).returncode == 0


def test_session_start_asks_for_a_name(repo):
    def context():
        r = subprocess.run([sys.executable, str(SESSION), "start"], input=json.dumps({"source": "startup"}),
                           capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)})
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "BRANCH NAME" not in context()
    git(repo, "switch", "-q", "-c", "claude/laughing-hawking-e62961")
    ctx = context()
    assert "BRANCH NAME: `claude/laughing-hawking-e62961`" in ctx
    assert "propose a branch name" in ctx and "job/<object-id>-<stage>`." in ctx and "git branch -m <name>" in ctx
    assert "[...]" not in ctx.split("Last 5 commits")[0]                 # no line of the prompt is cut

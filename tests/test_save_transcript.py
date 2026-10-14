"""tools/hooks/save_transcript.py: the session transcript kept at /handover, by branch and PR (#121)."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "tools/hooks/save_transcript.py"
CONTEXT = ROOT / "tools/hooks/session_context.py"


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True,
                   capture_output=True)


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "harness/task-x")
    (repo / "docs").mkdir()
    (repo / "docs/HANDOFF.md").write_text("# Handoff\n\nBranch: `harness/task-x` · Commit: `abc1234`\n",
                                          encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    return repo


@pytest.fixture
def config(tmp_path, repo):
    """A Claude Code config dir whose project folder for `repo` holds two transcripts; the newer is the session."""
    config = tmp_path / "claude"
    folder = config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(repo))
    folder.mkdir(parents=True)
    old = folder / "old-session.jsonl"
    old.write_text('{"old": 1}\n', encoding="utf-8")
    os.utime(old, (1_000_000, 1_000_000))
    (folder / "s-123.jsonl").write_text('{"type": "user"}\n', encoding="utf-8")
    return config


def run(script, repo, config, *args, session=None):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo), "CLAUDE_CONFIG_DIR": str(config),
           "PATH": os.path.dirname(shutil.which("git"))}          # no gh: the test stays offline
    env.pop("CLAUDE_SESSION_ID", None)
    if session:
        env["CLAUDE_SESSION_ID"] = session
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, encoding="utf-8",
                          env=env, cwd=repo)


def test_copy_named_by_branch_and_pr_and_never_overwritten(repo, config):
    first = run(HOOK, repo, config, "--pr", "140")
    assert first.returncode == 0, first.stderr
    dest = Path(first.stdout.strip())
    assert dest == repo / "logs/transcripts/harness-task-x-pr140-s-123.jsonl"
    assert dest.read_text(encoding="utf-8") == '{"type": "user"}\n'
    dest.write_text("kept", encoding="utf-8")
    second = run(HOOK, repo, config, "--pr", "140")
    assert second.returncode == 1 and "not overwritten" in second.stderr
    assert dest.read_text(encoding="utf-8") == "kept"


def test_without_a_pr_and_by_session_id(repo, config):
    r = run(HOOK, repo, config, session="old-session")
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()).name == "harness-task-x-prnone-old-session.jsonl"


def test_no_transcript_is_an_error(repo, tmp_path):
    r = run(HOOK, repo, tmp_path / "empty-config")
    assert r.returncode == 2 and "no transcript" in r.stderr
    assert not (repo / "logs").exists()


def test_the_folder_is_git_ignored():
    r = subprocess.run(["git", "check-ignore", "-q", "logs/transcripts/x.jsonl"], cwd=ROOT)
    assert r.returncode == 0


def report_head(repo, config):
    """The report without the handoff body (which repeats its own `Transcript:` line)."""
    return run(CONTEXT, repo, config, "report").stdout.split("--- docs/HANDOFF.md ---")[0]


def test_report_prints_the_handoff_transcript(repo, config):
    saved = Path(run(HOOK, repo, config, "--pr", "7").stdout.strip())
    handoff = repo / "docs/HANDOFF.md"
    handoff.write_text(handoff.read_text(encoding="utf-8") + f"Transcript: `{saved}`\n", encoding="utf-8")
    assert f"Transcript: {saved}\n" in report_head(repo, config)
    handoff.write_text(handoff.read_text(encoding="utf-8").replace(str(saved), str(saved) + ".gone"),
                       encoding="utf-8")
    assert "(missing on this machine)" in report_head(repo, config)
    handoff.write_text("# Handoff\n\nBranch: `harness/task-x` · Commit: `abc1234`\nTranscript: `-`\n",
                       encoding="utf-8")
    assert "Transcript:" not in report_head(repo, config)


def test_template_and_handover_carry_the_step():
    assert re.search(r"^Transcript:\s*`", (ROOT / "docs/HANDOFF.template.md").read_text(encoding="utf-8"), re.M)
    assert "tools/hooks/save_transcript.py" in (ROOT / ".claude/commands/handover.md").read_text(encoding="utf-8")

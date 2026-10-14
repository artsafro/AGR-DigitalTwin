"""tools/hooks/save_transcript.py: the session transcript kept at /handover, by branch and PR (#121)."""
import importlib.util
import json
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
USAGE = ROOT / "tools/hooks/usage_log.py"
BRANCH = "harness/task-x"


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True,
                   capture_output=True)


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", BRANCH)
    (repo / "docs").mkdir()
    (repo / "docs/HANDOFF.md").write_text(f"# Handoff\n\nBranch: `{BRANCH}` · Commit: `abc1234`\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def folder_for(config, path):
    # Written out, not computed by the code under test: C:\x\repo -> C--x-repo (Claude Code's project folder).
    return config / "projects" / "".join(c if c.isascii() and c.isalnum() else "-" for c in str(path))


@pytest.fixture
def config(tmp_path, repo):
    """A Claude Code config dir with two sessions in the repo's project folder; `other` is the newest."""
    config = tmp_path / "claude"
    folder = folder_for(config, repo)
    folder.mkdir(parents=True)
    (folder / "s-123.jsonl").write_text('{"session": "s-123"}\n', encoding="utf-8")
    (folder / "other.jsonl").write_text('{"session": "other"}\n', encoding="utf-8")
    return config


def env_for(repo, config, usage):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo), "CLAUDE_CONFIG_DIR": str(config),
           "AGR_USAGE_LOG": str(usage), "PATH": os.path.dirname(shutil.which("git"))}   # no gh: offline
    env.pop("CLAUDE_SESSION_ID", None)
    return env


def run(script, repo, config, usage, *args, env_extra=None, cwd=None):
    env = {**env_for(repo, config, usage), **(env_extra or {})}
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, encoding="utf-8",
                          env=env, cwd=cwd or repo)


def handover_prompt(repo, config, usage, session, transcript=None, branch_repo=None):
    """The UserPromptSubmit hook as Claude Code calls it on `/handover`."""
    payload = {"hook_event_name": "UserPromptSubmit", "prompt": "/handover", "session_id": session,
               "transcript_path": str(transcript) if transcript else None}
    r = subprocess.run([sys.executable, str(USAGE), "prompt"], input=json.dumps(payload), text=True,
                       encoding="utf-8", capture_output=True, env=env_for(branch_repo or repo, config, usage))
    assert r.returncode == 0, r.stderr


@pytest.fixture
def usage(tmp_path):
    return tmp_path / "usage.jsonl"


def test_the_handover_session_not_the_newest_file(repo, config, usage):
    handover_prompt(repo, config, usage, "s-123")
    first = run(HOOK, repo, config, usage, "--pr", "140")
    assert first.returncode == 0, first.stderr
    dest = Path(first.stdout.strip())
    assert dest == repo / "logs/transcripts/harness-task-x-pr140-s-123.jsonl"
    assert dest.read_text(encoding="utf-8") == '{"session": "s-123"}\n'
    assert [p.name for p in dest.parent.iterdir()] == [dest.name]          # no temporary file left


def test_never_overwritten(repo, config, usage):
    handover_prompt(repo, config, usage, "s-123")
    dest = Path(run(HOOK, repo, config, usage, "--pr", "140").stdout.strip())
    dest.write_text("kept", encoding="utf-8")
    second = run(HOOK, repo, config, usage, "--pr", "140")
    assert second.returncode == 1 and "not overwritten" in second.stderr
    assert dest.read_text(encoding="utf-8") == "kept"


def test_transcript_path_from_the_hook_wins(repo, config, usage, tmp_path):
    elsewhere = tmp_path / "elsewhere" / "s-777.jsonl"
    elsewhere.parent.mkdir()
    elsewhere.write_text("{}\n", encoding="utf-8")
    handover_prompt(repo, config, usage, "s-777", transcript=elsewhere)
    r = run(HOOK, repo, config, usage)
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()).name == "harness-task-x-prnone-s-777.jsonl"


def test_no_session_is_an_error_not_a_guess(repo, config, usage):
    r = run(HOOK, repo, config, usage)                                      # two transcripts, no /handover
    assert r.returncode == 2 and "no /handover" in r.stderr
    assert not (repo / "logs").exists()
    r = run(HOOK, repo, config, usage, env_extra={"CLAUDE_SESSION_ID": "missing"})
    assert r.returncode == 2 and "no missing.jsonl" in r.stderr


def test_another_branch_handover_does_not_count(repo, config, usage):
    handover_prompt(repo, config, usage, "s-123")
    git(repo, "checkout", "-q", "-b", "harness/other")
    r = run(HOOK, repo, config, usage)
    assert r.returncode == 2 and "harness/other" in r.stderr


def test_a_linked_worktree_writes_into_the_main_checkout(repo, config, usage, tmp_path):
    tree = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "harness/wt", str(tree))
    folder = folder_for(config, tree)
    folder.mkdir(parents=True)
    (folder / "s-9.jsonl").write_text("{}\n", encoding="utf-8")
    handover_prompt(tree, config, usage, "s-9")
    r = run(HOOK, tree, config, usage, "--pr", "3", cwd=tree)
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()) == repo / "logs/transcripts/harness-wt-pr3-s-9.jsonl"


def test_a_failed_copy_leaves_nothing_and_a_retry_works(repo, config, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("save_transcript", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = folder_for(config, repo) / "s-123.jsonl"
    dest = repo / "logs/transcripts/x.jsonl"

    def broken(src, dst):
        Path(dst).write_text("partial", encoding="utf-8")
        raise OSError("sharing violation")
    monkeypatch.setattr(module.shutil, "copyfile", broken)
    assert module.publish(source, dest) == 2 and not dest.exists()
    assert list(dest.parent.iterdir()) == []
    monkeypatch.undo()
    assert module.publish(source, dest) == 0 and dest.read_text(encoding="utf-8") == '{"session": "s-123"}\n'


def test_the_folder_is_git_ignored():
    r = subprocess.run(["git", "check-ignore", "-q", "logs/transcripts/x.jsonl"], cwd=ROOT)
    assert r.returncode == 0


def report_head(repo, config, usage):
    """The report without the handoff body (which repeats its own `Transcript:` line)."""
    r = run(CONTEXT, repo, config, usage, "report")
    assert r.returncode == 0 and "# Session context" in r.stdout, r.stderr
    return r.stdout.split("--- docs/HANDOFF.md ---")[0]


def test_report_prints_the_handoff_transcript(repo, config, usage):
    handover_prompt(repo, config, usage, "s-123")
    saved = Path(run(HOOK, repo, config, usage, "--pr", "7").stdout.strip())
    handoff = repo / "docs/HANDOFF.md"
    base = handoff.read_text(encoding="utf-8")
    handoff.write_text(base + f"Transcript: `{saved}`\n", encoding="utf-8")
    assert f"Transcript: {saved}\n" in report_head(repo, config, usage)
    handoff.write_text(base + f"Transcript: `{saved}.gone`\n", encoding="utf-8")
    assert "(missing on this machine)" in report_head(repo, config, usage)
    for line in ["Transcript: `-`", "Transcript: `bad\x00path`"]:
        handoff.write_text(base + line + "\n", encoding="utf-8")
        head = report_head(repo, config, usage)
        assert ("Transcript:" not in head) if line.endswith("`-`") else ("(missing on this machine)" in head)


def test_template_and_handover_carry_the_step():
    assert re.search(r"^Transcript:\s*`", (ROOT / "docs/HANDOFF.template.md").read_text(encoding="utf-8"), re.M)
    assert "tools/hooks/save_transcript.py" in (ROOT / ".claude/commands/handover.md").read_text(encoding="utf-8")


def test_a_non_ascii_main_checkout(tmp_path, usage):
    repo = tmp_path / "проект"
    repo.mkdir()
    git(repo, "init", "-q", "-b", BRANCH)
    git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    config = tmp_path / "claude"
    folder_for(config, repo).mkdir(parents=True)
    (folder_for(config, repo) / "s-1.jsonl").write_text("{}\n", encoding="utf-8")
    handover_prompt(repo, config, usage, "s-1")
    r = run(HOOK, repo, config, usage)
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()) == repo / "logs/transcripts/harness-task-x-prnone-s-1.jsonl"
    assert (repo / "logs/transcripts/harness-task-x-prnone-s-1.jsonl").is_file()

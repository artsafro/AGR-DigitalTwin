"""Keep the session transcript at /handover (#121; docs/agents/WORKFLOW.md, "Context rotation").

  py -3 tools/hooks/save_transcript.py [--transcript PATH] [--pr N]

Copies this session's Claude Code transcript (.jsonl) to `<main checkout>/logs/transcripts/
<branch>-pr<N|none>-<session id>.jsonl` and prints that path for the handoff's `Transcript:` line, so a grader
can later read the task's session from a file tied to its branch and PR. The folder is local and git-ignored
(`/logs/`), next to `logs/agent-usage.jsonl`; every worktree writes into the main checkout.

Which transcript - from the hook input, never guessed (review 1 of #140): `--transcript`, else
`$CLAUDE_SESSION_ID`, else the last `/handover` of this branch in `logs/agent-usage.jsonl`, which the
UserPromptSubmit hook (`usage_log.py prompt`) writes with the session id and transcript path it was given. A
session id is looked up as `<id>.jsonl` in the worktree's project folder `<config dir>/projects/<path, every
non-alphanumeric character as '-'>`. Nothing found: exit 2, no copy.

The copy goes to a temporary file first and is published with a hard link, which never replaces a file.
Exit 0 copied, 1 a copy of this session exists already (kept), 2 any other failure (no transcript, git, I/O).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_log  # noqa: E402


def _root():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def _git(*args):
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=_root(), capture_output=True,
                           text=True, encoding="utf-8", errors="strict", timeout=10)
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def project_folders():
    """Claude Code's folders for this worktree: `C:\\a\\b.c` -> `<config>/projects/C--a-b-c`."""
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    paths = dict.fromkeys(p for p in (str(_root()), _git("rev-parse", "--show-toplevel")) if p)
    return [config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(Path(p))) for p in paths]


def by_session(session):
    for folder in project_folders():
        if (folder / f"{session}.jsonl").is_file():
            return folder / f"{session}.jsonl"
    return None


def last_handover(branch):
    """(session id, transcript path) of the last /handover of this branch in the usage log, or (None, None)."""
    rows = [r for r in usage_log.read() if r.get("kind") == "command" and r.get("name") == "handover"
            and r.get("branch") == branch and r.get("session_id")]
    return (rows[-1]["session_id"], rows[-1].get("transcript")) if rows else (None, None)


def find_transcript(explicit, branch):
    """(path or None, how it was found or why not)."""
    if explicit:
        return (Path(explicit), "--transcript") if Path(explicit).is_file() else (None, f"{explicit} is no file")
    session = os.environ.get("CLAUDE_SESSION_ID")
    if session:
        found = by_session(session)
        return (found, "$CLAUDE_SESSION_ID") if found else (None, f"no {session}.jsonl in {project_folders()}")
    session, path = last_handover(branch)
    if not session:
        return None, f"no /handover of branch {branch} in {usage_log.log_path()}"
    if path and Path(path).is_file() and Path(path).stem == session:
        return Path(path), "usage log"
    found = by_session(session)
    return (found, "usage log") if found else (None, f"session {session}: no {session}.jsonl in {project_folders()}")


def pr_number():
    if not shutil.which("gh"):
        return None
    try:
        r = subprocess.run(["gh", "pr", "view", "--json", "number"], cwd=_root(), capture_output=True, text=True,
                           encoding="utf-8", timeout=15)
        return json.loads(r.stdout)["number"] if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None


def destination(branch, pr, session):
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        return None
    name = re.sub(r"[^A-Za-z0-9._-]", "-", branch) + f"-pr{pr if pr else 'none'}-{session}.jsonl"
    return Path(common).parent / "logs" / "transcripts" / name


def publish(source, dest):
    """Copy source to dest through a temporary file; 0 published, 1 dest exists (kept), 2 failed (nothing left)."""
    if dest.exists():
        return 1
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, tmp)
        os.link(tmp, dest)                           # fails on an existing dest: never a replacement
        return 0
    except FileExistsError:
        return 1
    except OSError as e:
        print(f"copy failed: {e}", file=sys.stderr)
        return 2
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--transcript")
    parser.add_argument("--pr", type=int)
    args = parser.parse_args(argv)
    branch = _git("branch", "--show-current")
    if branch is None:
        print("git failed: the branch and the main checkout are unknown", file=sys.stderr)
        return 2
    source, how = find_transcript(args.transcript, branch or "detached")
    if source is None:
        print(f"no transcript: {how}; pass --transcript <path to this session's .jsonl>", file=sys.stderr)
        return 2
    dest = destination(branch or "detached", args.pr or pr_number(), source.stem)
    if dest is None:
        print("git failed: the main checkout is unknown", file=sys.stderr)
        return 2
    code = publish(source, dest)
    if code == 1:
        print(f"a copy exists, not overwritten: {dest}", file=sys.stderr)
    elif code == 0:
        print(dest)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

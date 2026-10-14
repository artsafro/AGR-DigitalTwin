"""Keep the session transcript at /handover (#121; docs/agents/WORKFLOW.md, "Context rotation").

  py -3 tools/hooks/save_transcript.py --nonce <fresh random token> [--pr N]
  py -3 tools/hooks/save_transcript.py --transcript PATH [--pr N]

Copies this session's Claude Code transcript (.jsonl) to `<main checkout>/logs/transcripts/
<branch>-pr<N|none>-<session id>.jsonl` and prints that path for the handoff's `Transcript:` line, so a grader
can later read the task's session from a file tied to its branch and PR. The folder is local and git-ignored
(`/logs/`), next to `logs/agent-usage.jsonl`; every worktree writes into the main checkout.
Pattern: new-case (a harness tool; no domain pattern applies).

Which transcript - proven, never guessed (reviews 1-2 of #140): `--transcript`, else `$CLAUDE_SESSION_ID`, else
`--nonce`. The agent's Bash call is written to its own transcript before the command runs, so the one transcript
in the worktree's project folder `<config dir>/projects/<path, every non-alphanumeric character as '-'>` that
contains the nonce is the calling session's. None (after a short wait) or more than one: exit 2.

The copy goes to a temporary file first and is published with a hard link, which never replaces a file.
Exit 0 copied, 1 a copy of this session exists already (kept), 2 any other failure (nothing written).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

NONCE = re.compile(r"^[A-Za-z0-9_-]{12,}$")


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
    paths = [p for p in (str(_root()), _git("rev-parse", "--show-toplevel")) if p]
    # One worktree may come as C:\a and C:/a: the same folder, listed once.
    return list(dict.fromkeys(config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(Path(p))) for p in paths))


def holding(nonce):
    found = {}
    for folder in project_folders():
        for f in sorted(folder.glob("*.jsonl")) if folder.is_dir() else []:
            try:
                if nonce.encode() in f.read_bytes():
                    found[os.path.normcase(os.path.realpath(f))] = f
            except OSError:
                continue
    return list(found.values())


def find_transcript(explicit, nonce):
    """(path or None, how it was found or why not)."""
    if explicit:
        return (Path(explicit), "--transcript") if Path(explicit).is_file() else (None, f"{explicit} is no file")
    session = os.environ.get("CLAUDE_SESSION_ID")
    if session:
        for folder in project_folders():
            if (folder / f"{session}.jsonl").is_file():
                return folder / f"{session}.jsonl", "$CLAUDE_SESSION_ID"
        return None, f"no {session}.jsonl in {project_folders()}"
    if not nonce:
        return None, "pass --nonce <fresh random token> (or --transcript)"
    if not NONCE.match(nonce):
        return None, "the nonce must be 12 or more letters, digits, '-' or '_'"
    deadline = time.monotonic() + float(os.environ.get("AGR_TRANSCRIPT_WAIT_S", "5"))
    while True:
        found = holding(nonce)
        if len(found) == 1:
            return found[0], "--nonce"
        if len(found) > 1:
            return None, f"the nonce is in {len(found)} transcripts: {[f.name for f in found]}; use a fresh one"
        if time.monotonic() >= deadline:
            return None, f"no transcript in {project_folders()} contains the nonce"
        time.sleep(0.5)


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
    if dest.is_file():
        return 1
    if dest.exists():
        print(f"copy failed: {dest} exists and is no file", file=sys.stderr)
        return 2
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, tmp)
        try:
            os.link(tmp, dest)                       # fails on an existing dest: never a replacement
        except FileExistsError:                      # only a collision here means "a copy exists" (review 3)
            if dest.is_file():
                return 1
            raise
        return 0
    except OSError as e:
        print(f"copy failed: {e}", file=sys.stderr)
        return 2
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def main(argv):
    for stream in (sys.stdout, sys.stderr):          # paths and Windows error texts are not ASCII
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--transcript")
    parser.add_argument("--nonce")
    parser.add_argument("--pr", type=int)
    args = parser.parse_args(argv)
    branch = _git("branch", "--show-current")
    if branch is None:
        print("git failed: the branch and the main checkout are unknown", file=sys.stderr)
        return 2
    source, how = find_transcript(args.transcript, args.nonce)
    if source is None:
        print(f"no transcript: {how}", file=sys.stderr)
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
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:                           # an unexpected error is a failure (2), never "copy exists" (1)
        print(f"save_transcript failed: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)

"""Keep the session transcript at /handover (#121; docs/agents/WORKFLOW.md, "Context rotation").

  py -3 tools/hooks/save_transcript.py [--transcript PATH] [--pr N]

Copies this session's Claude Code transcript (.jsonl) to `<main checkout>/logs/transcripts/
<branch>-pr<N|none>-<session id>.jsonl` and prints that path for the handoff's `Transcript:` line, so a grader
can later read the task's session from a file tied to its branch and PR. The folder is local and git-ignored
(`/logs/`), next to `logs/agent-usage.jsonl`; every worktree writes into the main checkout.

The transcript: `--transcript`, else `$CLAUDE_SESSION_ID`, else the newest `.jsonl` in the project folder
`<config dir>/projects/<worktree path, every non-alphanumeric character as '-'>` - the running session writes
its transcript as it goes, so it is the newest. The PR: `--pr`, else `gh pr view` of the branch, else none.
An existing copy is never overwritten. Exit 0 copied, 1 a copy exists, 2 no transcript or no git.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _root():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def _git(*args):
    try:
        r = subprocess.run(["git", *args], cwd=_root(), capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def project_folder(path):
    """Claude Code's folder for a working directory: `C:\\a\\b.c` -> `<config>/projects/C--a-b-c`."""
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(path))


def find_transcript(explicit=None):
    if explicit:
        return Path(explicit) if Path(explicit).is_file() else None
    folders = [project_folder(p) for p in dict.fromkeys([str(_root()), _git("rev-parse", "--show-toplevel") or ""])
               if p]
    session = os.environ.get("CLAUDE_SESSION_ID")
    for folder in folders:
        if session and (folder / f"{session}.jsonl").is_file():
            return folder / f"{session}.jsonl"
    found = [f for folder in folders if folder.is_dir() for f in folder.glob("*.jsonl")]
    return max(found, key=lambda f: f.stat().st_mtime) if found else None


def pr_number():
    if not shutil.which("gh"):
        return None
    try:
        r = subprocess.run(["gh", "pr", "view", "--json", "number"], cwd=_root(), capture_output=True, text=True,
                           timeout=15)
        return json.loads(r.stdout)["number"] if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        return None


def destination(branch, pr, session):
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        return None
    name = re.sub(r"[^A-Za-z0-9._-]", "-", branch) + f"-pr{pr if pr else 'none'}-{session}.jsonl"
    return Path(common).parent / "logs" / "transcripts" / name


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--transcript")
    parser.add_argument("--pr", type=int)
    args = parser.parse_args(argv)
    source = find_transcript(args.transcript)
    if source is None:
        print("no transcript found: pass --transcript <path to the session .jsonl>", file=sys.stderr)
        return 2
    branch = _git("branch", "--show-current") or "detached"
    dest = destination(branch, args.pr or pr_number(), source.stem)
    if dest is None:
        print("git failed: the main checkout is unknown", file=sys.stderr)
        return 2
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(dest, "xb") as out:                # never overwrite an existing copy
            out.write(source.read_bytes())
    except FileExistsError:
        print(f"a copy exists, not overwritten: {dest}", file=sys.stderr)
        return 1
    print(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

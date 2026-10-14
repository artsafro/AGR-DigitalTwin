"""Session context for a context rotation (/checkpoint -> /clear -> "продолжай" or /resume; docs/agents/WORKFLOW.md).

  py -3 tools/hooks/session_context.py start       SessionStart (startup / clear / compact): the git state, open PRs
                                                   and docs/HANDOFF.md as additionalContext
  py -3 tools/hooks/session_context.py precompact  PreCompact: a manual /compact with a stale HANDOFF is blocked
                                                   (`/compact force` passes); an auto compaction is logged, never
                                                   blocked - the agent is told after it (SessionStart compact)
  py -3 tools/hooks/session_context.py report      the same text as `start`, plain, for /resume

A hook cannot write the handoff itself: only the agent knows decisions and the next step. It can tell whether
docs/HANDOFF.md is behind HEAD, belongs to another branch or has an old format, and it says so.
SessionStart stdout and additionalContext both reach the context; either is capped at 10 000 characters
(code.claude.com/docs/en/hooks), so the HANDOFF body is cut to fit and the agent reads the file.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HANDOFF = "docs/HANDOFF.md"
LIMIT = 9500                                         # under the 10 000-character hook cap
BRANCH_LINE = re.compile(r"^Branch:\s*`([^`]+)`", re.M)
COMMIT_LINE = re.compile(r"Commit:\s*`([0-9a-f]{7,40})`")


def _root():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def _git(*args):
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=_root(), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.rstrip("\n") if r.returncode == 0 else None


def open_prs():
    """Open PRs of the repo as lines, or a note why there are none (gh missing, offline, not logged in)."""
    if not shutil.which("gh"):
        return ["(gh not found)"]
    try:
        r = subprocess.run(["gh", "pr", "list", "--state", "open", "--limit", "15", "--json",
                            "number,title,headRefName,isDraft"], cwd=_root(), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15)
        prs = json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        prs = None
    if prs is None:
        return ["(gh pr list failed)"]
    branch = _git("branch", "--show-current")
    return [f"#{p['number']} {p['title']} [{p['headRefName']}]" + (" draft" if p.get("isDraft") else "")
            + ("  <- this branch" if p["headRefName"] == branch else "") for p in prs] or ["(none)"]


def handoff_state():
    """(text, warnings) of docs/HANDOFF.md against the current branch and HEAD."""
    path = _root() / HANDOFF
    if not path.exists():
        return "", [f"{HANDOFF} does not exist: no checkpoint was made"]
    text = path.read_text(encoding="utf-8")
    warnings = []
    branch = _git("branch", "--show-current") or "(detached)"
    m = BRANCH_LINE.search(text)
    if not m:
        warnings.append(f"{HANDOFF} has no `Branch:` line (written before docs/HANDOFF.template.md): treat it as "
                        "background, check every fact against git")
    elif m.group(1) != branch:
        warnings.append(f"{HANDOFF} belongs to branch `{m.group(1)}`, this session is on `{branch}`: it is not "
                        "this task's handoff")
    last = _git("log", "-1", "--format=%H", "--", HANDOFF)
    behind = _git("rev-list", "--count", f"{last}..HEAD") if last else None
    if behind and behind != "0":
        warnings.append(f"{behind} commit(s) after the last commit of {HANDOFF}: the handoff is behind HEAD")
    if _git("status", "--porcelain", "--", HANDOFF):
        warnings.append(f"{HANDOFF} has uncommitted changes")
    return text, warnings


def context(source):
    branch = _git("branch", "--show-current") or "(detached)"
    status = _git("status", "--short") or ""
    lines = status.splitlines()
    head = [f"# Session context ({source}; tools/hooks/session_context.py)",
            f"Branch: {branch}  Worktree: {_root()}",
            "Last 5 commits:", *(("  " + c) for c in (_git("log", "-5", "--oneline") or "").splitlines()),
            "git status --short: " + ("clean" if not lines else f"{len(lines)} path(s)"),
            *(("  " + s) for s in lines[:25]), *(["  ..."] if len(lines) > 25 else []),
            "Open PRs (gh):", *(("  " + p) for p in open_prs())]
    text, warnings = handoff_state()
    if source == "compact" and warnings:
        warnings.insert(0, "the context was just compacted and the handoff is not current: before any other work "
                           "run the /checkpoint procedure (.claude/commands/checkpoint.md) while the summary is "
                           "fresh, or tell the user why you cannot")
    head += ["Handoff warnings:", *(("  - " + w) for w in warnings)] if warnings else ["Handoff: current"]
    if source in ("startup", "clear", "compact"):
        head += ["If the user says «продолжай»: first name the branch, the HEAD commit and the next step from the "
                 "handoff (and any warning above), then do that step. /resume is the full reconciliation."]
    body = "\n".join(head)
    room = LIMIT - len(body) - 200
    if text:
        cut = text if len(text) <= room else text[:max(room, 0)] + f"\n[... cut at {room} characters: read {HANDOFF}]"
        body += f"\n\n--- {HANDOFF} ---\n{cut}"
    return body


def _log_compaction(payload):
    git_dir = _git("rev-parse", "--absolute-git-dir")
    if not git_dir:
        return
    _, warnings = handoff_state()
    line = json.dumps({"time": datetime.datetime.now().isoformat(timespec="seconds"),
                       "trigger": payload.get("trigger"), "head": _git("rev-parse", "--short", "HEAD"),
                       "handoff_warnings": warnings}, ensure_ascii=False)
    try:
        with open(Path(git_dir) / "agr-compactions.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def precompact(payload):
    _log_compaction(payload)
    if payload.get("trigger") != "manual":           # blocking an auto compaction can fail the request
        return {}
    if "force" in str(payload.get("custom_instructions") or "").lower():
        return {}
    _, warnings = handoff_state()
    if not warnings:
        return {}
    return {"decision": "block", "reason": "docs/HANDOFF.md is not current (" + "; ".join(warnings) + "). Run "
            "/checkpoint first (then /clear rather than /compact), or `/compact force` to compact anyway."}


def main(mode):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        payload = json.loads(sys.stdin.read() or "{}") if mode != "report" else {}
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    if mode == "start":
        out = {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                      "additionalContext": context(payload.get("source") or "startup")}}
        print(json.dumps(out))                       # ASCII JSON: no console code page can break it
    elif mode == "precompact":
        out = precompact(payload)
        if out:
            print(json.dumps(out))
    elif mode == "report":
        print(context("report"))
    else:
        print(f"unknown mode {mode!r}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))

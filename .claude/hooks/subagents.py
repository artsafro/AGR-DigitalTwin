"""Hooks of the project's read-only subagents (.claude/agents/, docs/agents/WORKFLOW.md).

  py -3 .claude/hooks/subagents.py start          SubagentStart: the read-only reminder as additionalContext, and
                                                  a snapshot of `git status` for the stop check
  py -3 .claude/hooks/subagents.py stop           SubagentStop: tracked files changed during the run block the
                                                  stop until the subagent names them; for independent-checker also
                                                  a verdict table (a data row ending in pass / fail / not measured)
  py -3 .claude/hooks/subagents.py guard          PreToolUse in every subagent: Bash that plainly writes (a
                                                  redirect into a file, tee, sed -i, cp / mv / rm, git writes,
                                                  write_text / open(..., "w")) is denied
  py -3 .claude/hooks/subagents.py deny-geometry  PreToolUse in independent-checker: no reading of
                                                  src/dt_ai/geometry/ (it must not know how the model was built)

The hooks guard against a subagent forgetting it is read-only, not against a hostile one (user 2026-10-12): Bash
stays arbitrary code. Input is the hook's JSON on stdin; anything but a JSON object blocks (fail closed).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REMINDER = ("Read-only subagent: report facts only - numbers, lists, tables, paths. No fixes, no proposals, no "
            "edits, no saves of any scene or file outside your report. The main agent decides.")
VERDICT_CELL = re.compile(r"^(pass|fail|not measured)\b", re.I)
WRITES = re.compile(r"(?<![<>=!-])>{1,2}\s*(?!&|\s*/dev/null|\s*nul\b)\S"     # a redirect into a file
                    r"|\btee\b|\bsed\s+(-\w*\s+)*-i|\b(cp|mv|rm|rmdir|del|copy|move|ren|mkdir -p\s+(src|docs|jobs))\b"
                    r"|\bgit\s+(add|commit|push|checkout|switch|reset|restore|stash|rebase|merge|rm|mv|clean|apply)\b"
                    r"|\b(Set-Content|Add-Content|Out-File|New-Item|Remove-Item|Copy-Item|Move-Item)\b"
                    r"|write_text|write_bytes|\.write\(|open\([^)]*['\"][wax]\+?b?['\"]", re.I)
SEARCH = re.compile(r"\b(grep|rg|find|findstr|Select-String|Get-ChildItem|dir|ls|cat|type|more|head|tail)\b", re.I)


def _root():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def _forbidden():
    return (_root() / "src" / "dt_ai" / "geometry").resolve()


def _snapshot_path(agent_id):
    return Path(tempfile.gettempdir()) / f"agr-subagent-{re.sub(r'[^A-Za-z0-9_-]', '_', agent_id or 'x')}.status"


def _status():
    r = subprocess.run(["git", "-c", "core.quotepath=false", "status", "--porcelain", "--untracked-files=no"],
                       cwd=_root(), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def start(payload):
    status = _status()
    if status is not None:
        _snapshot_path(payload.get("agent_id")).write_text(status, encoding="utf-8")
    return {"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": REMINDER}}


def _has_verdict_table(text):
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and not set(cells[-1]) <= set("-: ") and VERDICT_CELL.match(cells[-1]) \
                and cells[-1].lower() != "pass/fail":
            return True
    return False


def stop(payload):
    reasons = []
    before = _snapshot_path(payload.get("agent_id"))
    now = _status()
    if now is None or not before.exists():
        reasons.append("the tracked-file check could not run; state in your report that you changed no file")
    elif now != before.read_text(encoding="utf-8"):
        changed = sorted(set(now.splitlines()) - set(before.read_text(encoding="utf-8").splitlines()))
        reasons.append(f"tracked files changed during your run: {changed}; name them in your report (you are "
                       "read only)")
    if payload.get("agent_type") == "independent-checker" and not _has_verdict_table(
            payload.get("last_assistant_message") or ""):
        reasons.append("report the table: check | expected | measured | pass/fail")
    if reasons and not payload.get("stop_hook_active"):
        return {"decision": "block", "reason": "; ".join(reasons)}
    before.unlink(missing_ok=True)
    return {}


def _deny(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def guard(payload):
    if payload.get("tool_name") == "Bash" and WRITES.search(str((payload.get("tool_input") or {}).get("command", ""))):
        return _deny("read-only subagent: this command writes a file; report instead, the main agent writes")
    return {}


def _inside(path, base):
    try:
        return path == base or base in path.parents
    except TypeError:
        return False


def deny_geometry(payload):
    tool, args = payload.get("tool_name"), payload.get("tool_input") or {}
    geo = _forbidden()
    reason = ("independent-checker does not read src/dt_ai/geometry/: it checks the model, not how it was "
              "built")
    if tool == "Bash":
        cmd = str(args.get("command", ""))
        low = cmd.lower().replace("\\", "/")
        if "from_spec" in low or ("dt_ai" in low and "geometry" in low) \
                or (SEARCH.search(cmd) and re.search(r"(^|[\s'\"=])(\.|\./?|src|src/dt_ai|\.\./\S*)(/?)(\s|$|['\"])",
                                                     low) and re.search(r"\s-\w*r|\brecurse\b|\bfind\b|\brg\b", low)):
            return _deny(reason)
        return {}
    for key in ("file_path", "path", "notebook_path"):
        value = args.get(key)
        if not value:
            continue
        p = (_root() / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
        if _inside(p, geo) or (tool in ("Grep", "Glob") and _inside(geo, p)):   # an ancestor search reads it too
            return _deny(reason)
    if tool in ("Grep", "Glob") and not args.get("path") and _inside(geo, _root().resolve()):
        return _deny(reason)                                                  # no path: the whole project
    pattern = str(args.get("pattern", "")) + str(args.get("glob", ""))
    if "dt_ai/geometry" in pattern.replace("\\", "/") or "from_spec" in pattern:
        return _deny(reason)
    return {}


def main(mode):
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = None
    if not isinstance(payload, dict):                # fail closed on anything but an object
        payload = None
    if mode == "start":
        out = start(payload or {})
    elif payload is None:
        out = {"decision": "block", "reason": "report the table (hook input unreadable)"} if mode == "stop" \
            else _deny("hook input unreadable")
    elif mode == "stop":
        out = stop(payload)
    elif mode == "guard":
        out = guard(payload)
    elif mode == "deny-geometry":
        out = deny_geometry(payload)
    else:
        print(f"unknown mode {mode!r}", file=sys.stderr)
        return 2
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))

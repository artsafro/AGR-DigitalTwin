"""Hooks of the project's read-only subagents (.claude/agents/, docs/agents/WORKFLOW.md).

  py -3 .claude/hooks/subagents.py start          SubagentStart: the read-only reminder as additionalContext
  py -3 .claude/hooks/subagents.py stop           SubagentStop of independent-checker: the report must be a
                                                  table with a pass/fail column, else block ("report the table")
  py -3 .claude/hooks/subagents.py deny-geometry  PreToolUse inside independent-checker: no reading of
                                                  src/dt_ai/geometry/ (it must not know how the model was built)

Reads the hook's JSON on stdin, answers JSON on stdout; never fails open on its own errors for `stop` and
`deny-geometry` (a broken input blocks).
"""
import json
import re
import sys

REMINDER = ("Read-only subagent: report facts only - numbers, lists, tables, paths. No fixes, no proposals, no "
            "edits, no saves of any scene or file outside your report. The main agent decides.")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.M)
VERDICT = re.compile(r"\b(pass|fail)\b", re.I)
GEOMETRY = re.compile(r"dt_ai[\\/]+geometry", re.I)


def start(_payload):
    return {"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": REMINDER}}


def stop(payload):
    last = payload.get("last_assistant_message") or ""
    rows = TABLE_ROW.findall(last)
    if len(rows) >= 3 and sum(1 for r in rows if VERDICT.search(r)) >= 1:   # header, rule, one verdict row
        return {}
    return {"decision": "block", "reason": "report the table: check | expected | measured | pass/fail"}


def deny_geometry(payload):
    text = json.dumps(payload.get("tool_input") or {})
    if GEOMETRY.search(text):
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": "independent-checker does not read "
                                                                   "src/dt_ai/geometry/: it checks the model, not how "
                                                                   "it was built"}}
    return {}


def main(mode):
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = None
    if mode == "start":
        out = start(payload or {})
    elif payload is None:                            # fail closed on unreadable input
        out = ({"decision": "block", "reason": "report the table (hook input unreadable)"} if mode == "stop" else
               {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": "hook input unreadable"}})
    elif mode == "stop":
        out = stop(payload)
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

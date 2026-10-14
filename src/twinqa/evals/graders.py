"""Code graders: evidence paths in, one check row out (`check`, `expected`, `measured`, `passed`, `details`).

A grader raises `EvidenceError` when its evidence cannot prove anything (absent, empty, unreadable); the runner
reports that as not measured (exit 2), never as a pass.

Claude Code transcript shapes relied on (inspected 2026-10-15 over the local transcripts; re-check when the CLI
changes its format, spec "Further Notes"):
- a tool call refused by a PreToolUse hook is a `user` record whose `message.content` holds the `tool_result`
  (`is_error: true`, text `PreToolUse:<tool> hook error: <reason>`) and whose top-level `permissionDecision` is
  `{"decision": "reject", "source": "hook", ...}`;
- a hook that merely failed (`attachment.type == "hook_non_blocking_error"`) or allowed the call
  (`permissionDecision.decision == "accept"`) is not a denial.
"""
import json
import re
from pathlib import Path

HOOK_ERROR = re.compile(r"^PreToolUse:(\S+) hook error:\s*")
DENIED = {"reject", "deny"}


class EvidenceError(Exception):
    """The evidence is missing or unreadable: the check is not measured."""


def read_jsonl(path):
    """Records of a .jsonl file and the count of lines that are not JSON objects (a torn last line, say)."""
    path = Path(path)
    if not path.is_file():
        raise EvidenceError(f"{path} does not exist")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise EvidenceError(f"{path}: {type(exc).__name__}: {exc}") from exc
    records, bad = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(value, dict):
            records.append(value)
        else:
            bad += 1
    if not records:
        raise EvidenceError(f"{path} holds no transcript records")
    return records, bad


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):          # [{"type": "text", "text": ...}, ...]
        return "".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def hook_denials(records):
    """Every tool call a hook refused, from the record structure only: text quoted in a file or a message never
    counts. One entry per tool_use_id."""
    found = {}
    for n, rec in enumerate(records):
        if rec.get("type") != "user":
            continue
        content = (rec.get("message") or {}).get("content")
        results = [c for c in content if isinstance(c, dict) and c.get("type") == "tool_result"] \
            if isinstance(content, list) else []
        decision = rec.get("permissionDecision")
        by_hook = isinstance(decision, dict) and decision.get("source") == "hook" \
            and decision.get("decision") in DENIED
        for res in results:
            text = _text(res.get("content"))
            match = HOOK_ERROR.match(text) if res.get("is_error") is True else None
            # The decision field rules when present; only a record without one (older CLI) falls back to the text.
            if not (by_hook or (match and decision is None)):
                continue
            key = res.get("tool_use_id") or f"record-{n}"
            found.setdefault(key, {
                "record": n,
                "tool_use_id": res.get("tool_use_id"),
                "tool": match.group(1) if match else None,
                "reason": (text[match.end():] if match else text)[:200],
                "sidechain": bool(rec.get("isSidechain")),
            })
    return list(found.values())


def no_hook_denial(evidence):
    """Regression grader: no PreToolUse hook denial in the task's transcripts (`evidence["transcript"]`)."""
    paths = evidence["transcript"]
    details, skipped = [], 0
    for path in paths:
        records, bad = read_jsonl(path)
        skipped += bad
        details += [{"file": str(path), **d} for d in hook_denials(records)]
    row = {"check": "hook denials in the transcript", "expected": 0, "measured": len(details),
           "passed": not details, "details": details}
    if skipped:
        row["skipped_lines"] = skipped
    return row


GRADERS = {"no_hook_denial": no_hook_denial}

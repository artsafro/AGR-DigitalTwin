"""Code graders: evidence paths in, one check row out (`check`, `expected`, `measured`, `passed`, `details`).

A grader raises `EvidenceError` when its evidence is absent or unreadable, and returns `passed: None` with an
`error` when it is incomplete; the runner reports both as not measured (exit 2), never as a pass.

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
CONVERSATION = ("user", "assistant")


class EvidenceError(Exception):
    """The evidence is missing or unreadable: the check is not measured."""


def _recognized(value):
    """A Claude Code transcript entry: an object with a non-empty string `type`; a `user` / `assistant` entry also
    carries its `message` object. Every record of the local transcripts had this shape (2026-10-15)."""
    if not isinstance(value, dict) or not isinstance(value.get("type"), str) or not value["type"]:
        return False
    if value["type"] not in CONVERSATION:
        return True
    message = value.get("message")              # review 2 of #142: an empty message is no conversation record
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return True
    if not isinstance(content, list):
        return False
    # Review 3 of #142: every block is typed, and a tool_result carries its payload (the denial text may be there).
    return all(isinstance(b, dict) and isinstance(b.get("type"), str)
               and (b["type"] != "tool_result" or isinstance(b.get("content"), (str, list))) for b in content)


def read_jsonl(path):
    """Recognized records of a transcript and the problems that make it incomplete as evidence: lines that are not
    JSON or not a transcript entry (a torn last line included), or no user / assistant record at all.
    Raises EvidenceError when the file is absent or unreadable."""
    path = Path(path)
    if not path.is_file():
        raise EvidenceError(f"{path} does not exist")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise EvidenceError(f"{path}: {type(exc).__name__}: {exc}") from exc
    records, bad = [], 0
    for line in text.split("\n"):  # only \n ends a JSON Lines record; U+2028, 0x1c, 0x85 may sit inside strings
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = None
        if _recognized(value):
            records.append(value)
        else:
            bad += 1
    problems = [f"{path}: {bad} line(s) not a transcript record"] if bad else []
    if not any(r["type"] in CONVERSATION for r in records):
        problems.append(f"{path}: no user or assistant record")
    return records, problems


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
        if by_hook and not results:                  # review 2 of #142: the decision alone is authoritative
            found.setdefault(f"record-{n}", {"record": n, "tool_use_id": None, "tool": None,
                                             "reason": str(decision.get("reason") or "")[:200],
                                             "sidechain": bool(rec.get("isSidechain"))})
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
    """Regression grader: no PreToolUse hook denial in the task's transcripts (`evidence["transcript"]`).

    Strict about partial evidence (review 1 of #142): a line that is not a transcript record - a torn last line of
    a live session too - makes the check not measured, because the lost line may be the denial. A denial found in
    the readable records is a definite failure and wins."""
    details, problems, seen = [], [], set()
    for path in evidence["transcript"]:
        try:                                         # review 2 of #142: one unreadable file never hides a denial
            records, issues = read_jsonl(path)
        except EvidenceError as exc:
            problems.append(str(exc))
            continue
        problems += issues
        for d in hook_denials(records):
            # Copies of one session (a handover before and after the PR) hold the same denial: count it once.
            if d.get("tool_use_id") in seen:
                continue
            if d.get("tool_use_id"):
                seen.add(d["tool_use_id"])
            details.append({"file": str(path), **d})
    row = {"check": "hook denials in the transcript", "expected": 0, "measured": len(details),
           "passed": not details, "details": details}
    if problems and not details:
        row.update(measured="not measured", passed=None, error="incomplete evidence: " + "; ".join(problems))
    elif problems:
        row["evidence_problems"] = problems
    return row


# grader name -> (function, the evidence names it reads); task.json is checked against the names.
GRADERS = {"no_hook_denial": (no_hook_denial, ("transcript",))}

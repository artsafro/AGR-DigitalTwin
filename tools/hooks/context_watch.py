"""UserPromptSubmit: tell the agent when the context is full enough to rotate (docs/agents/WORKFLOW.md, "Context rotation").

  py -3 tools/hooks/context_watch.py      hook input JSON on stdin; additionalContext once per threshold per session

Hook input has no context-usage field (code.claude.com/docs/en/hooks: token fields come only to SessionStart on
resume / fork), so the hook reads `transcript_path`. Tokens = the last main-chain response's `usage` (input +
cache creation + cache read: the formula of the status line's `used_percentage`) plus an estimate of what came
after it (tool results, the new prompt: characters / 2, an image 1600 tokens, base64 never counted as text). With
no response yet (a new or just compacted session) everything after the last compaction is estimated.

Window (code.claude.com/docs/en/model-config): CLAUDE_CODE_MAX_CONTEXT_TOKENS; a `[1m]` model; 200K under
CLAUDE_CODE_DISABLE_1M_CONTEXT; 1M for the models with a native 1M window; else 200K.

Each threshold fires once per session: a flag file next to the transcript (`<transcript>.context-watch.json`).
/clear starts a new session with a new transcript, so the flags start empty. Advisory only: any failure is silent.
"""
import json
import os
import re
import sys
from pathlib import Path

THRESHOLDS = [
    (65, "context ≈{pct} % ({used}k of {window}k tokens): strongly urge the user, in one sentence, to run /handover "
         "now and then /clear; then continue with the task."),
    (45, "context ≈{pct} % ({used}k of {window}k tokens): suggest /handover to the user in one sentence, then continue "
         "with the task."),
]
NATIVE_1M = re.compile(r"fable|sonnet-([5-9]|\d\d)|haiku-5-5|opus-4-([7-9])|opus-([5-9]|\d\d)", re.I)
BASE64 = re.compile(r"[A-Za-z0-9+/=]{2000,}")
IMAGE_TOKENS = 1600
CHARS_PER_TOKEN = 2                                  # measured: 3 gave 0.57 of the real tail (median, 5890 gaps)


def window(model):
    env = os.environ.get("CLAUDE_CODE_MAX_CONTEXT_TOKENS", "")
    if env.isdigit() and int(env) > 0:
        return int(env)
    model = model or ""
    if "[1m]" in model.lower():
        return 1_000_000
    if os.environ.get("CLAUDE_CODE_DISABLE_1M_CONTEXT", "").lower() in ("1", "true", "yes"):
        return 200_000
    return 1_000_000 if NATIVE_1M.search(model) else 200_000


def _estimate(value):
    """Tokens of a message content: text by characters, images flat, base64 blobs not as text."""
    if isinstance(value, dict):
        if value.get("type") == "image":
            return IMAGE_TOKENS
        return sum(_estimate(v) for k, v in value.items() if k not in ("type", "signature", "id", "tool_use_id"))
    if isinstance(value, list):
        return sum(_estimate(v) for v in value)
    if isinstance(value, str):
        return len(BASE64.sub("", value)) // CHARS_PER_TOKEN
    return 0


def _entry_content(entry):
    if entry.get("type") in ("user", "assistant"):
        return (entry.get("message") or {}).get("content")
    if entry.get("type") == "attachment":
        return entry.get("attachment")
    return None


def used_tokens(transcript, prompt=""):
    """(tokens, model) of the main conversation as of now."""
    usage, model, after = None, None, 0
    for line in Path(transcript).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("isSidechain"):
            continue
        if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
            usage, after = None, 0                   # what came before is summarised away
            continue
        msg = entry.get("message") or {}
        if entry.get("type") == "assistant" and isinstance(msg.get("usage"), dict):
            u = msg["usage"]
            usage = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                                     "cache_read_input_tokens"))
            model, after = msg.get("model") or model, _estimate(msg.get("content"))   # its output is input next
            continue
        after += _estimate(_entry_content(entry))
    return (usage or 0) + after + _estimate(prompt), model


def check(payload):
    transcript = payload.get("transcript_path")
    if not transcript or not Path(transcript).exists():
        return {}
    used, model = used_tokens(transcript, payload.get("prompt") or "")
    size = window(model)
    pct = 100 * used / size
    flags_path = Path(f"{transcript}.context-watch.json")
    try:
        flags = json.loads(flags_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        flags = {}
    if flags.get("session_id") != payload.get("session_id"):
        flags = {"session_id": payload.get("session_id"), "fired": []}
    for threshold, text in THRESHOLDS:               # the highest crossed threshold speaks, lower ones are spent
        if pct >= threshold and threshold not in flags["fired"]:
            flags["fired"] = sorted(set(flags["fired"]) | {t for t, _ in THRESHOLDS if t <= threshold})
            flags_path.write_text(json.dumps(flags), encoding="utf-8")
            return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text.format(
                pct=round(pct), used=round(used / 1000), window=round(size / 1000))}}
    return {}


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        out = check(payload) if isinstance(payload, dict) else {}
    except Exception:                                # advisory: never block or break a prompt
        out = {}
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""PreToolUse on DCC MCP tools: the matching skill must be loaded in this session first (docs/agents/WORKFLOW.md,
"Triggers").

  py -3 tools/hooks/skill_gate.py      hook input JSON on stdin; denies with the skill to load, or stays silent

A skill counts as loaded when the session's transcript has a Skill call for it or the user ran it as /<skill>, or
when logs/agent-usage.jsonl has it for this session (the transcript is written asynchronously and may lag).
Subagents are not gated: they are read only and preload their skills in .claude/agents/*.md. Unreadable input
or transcript: the call passes (the gate reminds, it does not secure).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_log  # noqa: E402

# MCP server name in the tool name -> project skill (plugin skill for 3ds Max).
SKILLS = [(re.compile(r"^mcp__[^_]*3dsmax", re.I), "3dsmax-mcp-dev"),
          (re.compile(r"^mcp__[^_]*blender", re.I), "blender-mcp"),
          (re.compile(r"^mcp__[^_]*revit", re.I), "revit-mcp")]


def required(tool):
    return next((skill for pattern, skill in SKILLS if pattern.search(tool or "")), None)


def _matches(name, skill):
    return bool(name) and (name == skill or name.endswith(":" + skill))


def loaded(skill, payload):
    """Success evidence only (review 2 of #107): the user ran /<skill> (a genuine command record), or a Skill call
    returned success (`toolUseResult.success` with its `commandName`), or the PostToolUse log has it (PostToolUse
    fires on success only). A tag quoted in a tool result or a failed Skill call does not count."""
    transcript = payload.get("transcript_path")
    try:
        text = Path(transcript).read_text(encoding="utf-8", errors="replace")
    except (OSError, TypeError):
        return True                                  # cannot tell: let it pass (documented)
    for line in text.splitlines():
        if skill not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        if _matches(usage_log.command_of(entry), skill):
            return True
        result = entry.get("toolUseResult")
        if isinstance(result, dict) and result.get("success") is True and _matches(result.get("commandName"), skill):
            return True
    return any(r.get("session_id") == payload.get("session_id") and r.get("kind") in ("skill", "command")
               and _matches(r.get("name"), skill) for r in usage_log.read())


def check(payload):
    if payload.get("agent_id"):
        return {}
    skill = required(payload.get("tool_name"))
    if not skill or loaded(skill, payload):
        return {}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": f"Load the `{skill}` skill first (Skill tool), follow it, "
                                   "then repeat this call (docs/agents/WORKFLOW.md, Triggers)."}}


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        out = check(payload) if isinstance(payload, dict) else {}
    except Exception:
        out = {}
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

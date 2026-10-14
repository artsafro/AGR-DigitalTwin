"""Triggers: tools/hooks/usage_log.py, tools/hooks/skill_gate.py, their wiring, /reuse-scan and agent descriptions."""
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
LOG_HOOK = ROOT / "tools/hooks/usage_log.py"
GATE = ROOT / "tools/hooks/skill_gate.py"


def run(script, args, payload, log):
    env = {**os.environ, "AGR_USAGE_LOG": str(log), "CLAUDE_PROJECT_DIR": str(ROOT)}
    r = subprocess.run([sys.executable, str(script), *args], input=json.dumps(payload), capture_output=True,
                       text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout


def lines(log):
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def transcript(tmp_path, *entries):
    t = tmp_path / "s.jsonl"
    t.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
    return t


def command(name):
    return {"type": "user", "message": {"content": f"<command-message>{name}</command-message>\n"
                                                   f"<command-name>/{name}</command-name>\n<command-args></command-args>"}}


def skill_call(name, success=True):
    """The tool result of a Skill call, as Claude Code records it (toolUseResult.success, commandName)."""
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                                     "content": f"Launching skill: {name}"}]},
            "toolUseResult": {"success": success, "commandName": name}}


def quoted(text):
    """A tool result that only quotes a command tag (a file read, a grep)."""
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "content": text}]}}


def test_hooks_are_wired():
    hooks = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    post = hooks["PostToolUse"][0]
    assert all(re.search(post["matcher"], t) for t in ("Agent", "Task", "Skill")) and not re.search(post["matcher"], "Bash")
    assert post["hooks"][0]["command"].endswith('usage_log.py" post')
    assert any(h["command"].endswith('usage_log.py" prompt') for h in hooks["UserPromptSubmit"][0]["hooks"])
    gate = next(e for e in hooks["PreToolUse"] if "skill_gate.py" in e["hooks"][0]["command"])
    for tool in ("mcp__3dsmax-mcp__inspect_mesh", "mcp__blender__get_objects_summary", "mcp__revit-http-2025__revit_ping",
                 "mcp__revit-twin__x"):
        assert re.search(gate["matcher"], tool)
    assert not re.search(gate["matcher"], "Bash") and not re.search(gate["matcher"], "mcp__github__get_me")


def test_usage_log_records_agents_skills_and_commands(tmp_path):
    log, t = tmp_path / "logs/u.jsonl", transcript(tmp_path, command("takeover"))
    base = {"session_id": "s1", "transcript_path": str(t)}
    run(LOG_HOOK, ["post"], {**base, "tool_name": "Agent", "tool_input": {"subagent_type": "bench-runner"}}, log)
    run(LOG_HOOK, ["post"], {**base, "tool_name": "Task", "tool_input": {}}, log)
    run(LOG_HOOK, ["post"], {**base, "tool_name": "Skill", "tool_input": {"skill": "blender-mcp"}}, log)
    run(LOG_HOOK, ["post"], {**base, "tool_name": "Bash", "tool_input": {"command": "ls"}}, log)
    run(LOG_HOOK, ["prompt"], {**base, "hook_event_name": "UserPromptSubmit", "prompt": "/handover"}, log)
    run(LOG_HOOK, ["prompt"], {**base, "hook_event_name": "UserPromptSubmit", "prompt": "продолжай"}, log)
    got = [(r["kind"], r["name"], r["command"]) for r in lines(log)]
    assert got == [("agent", "bench-runner", "takeover"), ("agent", "general-purpose", "takeover"),
                   ("skill", "blender-mcp", "takeover"), ("command", "handover", None)]
    assert all(r["session_id"] == "s1" and r["time"] for r in lines(log))


def test_command_attribution_ignores_quoted_tags(tmp_path):        # review 2 of #107
    log = tmp_path / "u.jsonl"
    t = transcript(tmp_path, command("handover"), quoted("example: <command-name>/takeover</command-name>"))
    run(LOG_HOOK, ["post"], {"session_id": "s", "transcript_path": str(t), "tool_name": "Agent",
                             "tool_input": {"subagent_type": "bench-runner"}}, log)
    assert lines(log)[0]["command"] == "handover"


def test_reuse_candidates_fails_loudly_without_git(tmp_path):     # review 2 of #107
    r = subprocess.run([sys.executable, str(ROOT / "tools/reuse_candidates.py")], capture_output=True, text=True,
                       env={**os.environ, "PATH": str(tmp_path)})
    assert r.returncode != 0 and "Job scripts" not in r.stdout


def test_usage_log_never_fails(tmp_path):
    for raw in ("not json", "[]", "{}"):
        r = subprocess.run([sys.executable, str(LOG_HOOK), "post"], input=raw, capture_output=True, text=True,
                           env={**os.environ, "AGR_USAGE_LOG": str(tmp_path / "u.jsonl")})
        assert r.returncode == 0 and r.stdout == ""


def test_stats_counts_and_names_the_unused(tmp_path):
    log = tmp_path / "u.jsonl"
    old = {"time": "2020-01-01T00:00:00+00:00", "kind": "agent", "name": "mesh-reader"}
    log.write_text(json.dumps(old) + "\n", encoding="utf-8")
    run(LOG_HOOK, ["post"], {"tool_name": "Agent", "tool_input": {"subagent_type": "bench-runner"}}, log)
    run(LOG_HOOK, ["post"], {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore"}}, log)
    env = {**os.environ, "AGR_USAGE_LOG": str(log)}
    out = subprocess.run([sys.executable, str(LOG_HOOK), "stats", "--days", "7"], capture_output=True, text=True,
                         encoding="utf-8", env=env).stdout
    assert "bench-runner 1" in out and "mesh-reader 0" in out                 # the 2020 line is outside 7 days
    assert re.search(r"never called: .*mesh-reader", out) and "Explore (agent) 1" in out
    assert "handover 0" in out and "validate-delivery 0" in out


@pytest.mark.parametrize("tool, loaded_by, denied", [
    ("mcp__blender__get_objects_summary", None, True),
    ("mcp__blender__get_objects_summary", skill_call("blender-mcp"), False),
    ("mcp__blender__get_objects_summary", command("blender-mcp"), False),
    ("mcp__blender__get_objects_summary", skill_call("revit-mcp"), True),
    ("mcp__3dsmax-mcp__inspect_mesh", skill_call("3dsmax-mcp-dev"), False),
    ("mcp__3dsmax-mcp__inspect_mesh", skill_call("3dsmax-mcp:3dsmax-mcp-dev"), False),
    ("mcp__revit-http-2025__revit_ping", skill_call("blender-mcp"), True),
    ("mcp__github__get_me", None, False),
    # review 2 of #107: a failed Skill call or a quoted tag is no load
    ("mcp__blender__get_objects_summary", skill_call("blender-mcp", success=False), True),
    ("mcp__blender__get_objects_summary", quoted("<command-name>/blender-mcp</command-name>"), True),
])
def test_skill_gate(tmp_path, tool, loaded_by, denied):
    t = transcript(tmp_path, *([loaded_by] if loaded_by else []), {"type": "user", "message": {"content": "hi"}})
    out = run(GATE, [], {"session_id": "s", "transcript_path": str(t), "tool_name": tool}, tmp_path / "u.jsonl")
    if denied:
        decision = json.loads(out)["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny" and "Skill tool" in decision["permissionDecisionReason"]
    else:
        assert out == ""


def test_skill_gate_trusts_the_usage_log_and_skips_subagents(tmp_path):
    t = transcript(tmp_path, {"type": "user", "message": {"content": "hi"}})
    log = tmp_path / "u.jsonl"
    payload = {"session_id": "s", "transcript_path": str(t), "tool_name": "mcp__revit-http-2025__revit_ping"}
    assert run(GATE, [], {**payload, "agent_id": "a1"}, log) == ""            # subagent: not gated
    assert run(GATE, [], payload, log) != ""
    run(LOG_HOOK, ["post"], {"session_id": "s", "tool_name": "Skill", "tool_input": {"skill": "revit-mcp"}}, log)
    assert run(GATE, [], payload, log) == ""
    assert run(GATE, [], {**payload, "session_id": "other"}, log) != ""       # another session's load does not count
    assert run(GATE, [], {**payload, "transcript_path": str(tmp_path / "missing.jsonl")}, log) == ""


def test_reuse_scan_command_and_helper():
    text = (ROOT / ".claude/commands/reuse-scan.md").read_text(encoding="utf-8")
    meta = yaml.safe_load(text.split("---\n")[1])
    assert meta["disable-model-invocation"] is True
    assert "!`py -3 tools/reuse_candidates.py --days 7`" in text and "usage_log.py stats --days 7" in text
    r = subprocess.run([sys.executable, str(ROOT / "tools/reuse_candidates.py"), "--days", "7"], capture_output=True,
                       text=True, encoding="utf-8")
    assert r.returncode == 0 and r.stdout.startswith("Job scripts: ")
    takeover = (ROOT / ".claude/commands/takeover.md").read_text(encoding="utf-8")
    assert "!`py -3 tools/hooks/usage_log.py stats --days 7`" in takeover
    assert "Repeats" in (ROOT / ".claude/commands/handover.md").read_text(encoding="utf-8")


def test_logs_are_ignored():
    r = subprocess.run(["git", "check-ignore", "-q", "logs/agent-usage.jsonl"], cwd=ROOT)
    assert r.returncode == 0


@pytest.mark.parametrize("path", sorted(glob.glob(str(ROOT / ".claude/agents/*.md")) + [
    p for p in glob.glob(str(ROOT / ".agents/skills/*/SKILL.md"))
    if Path(p).parent.name not in json.loads((ROOT / "skills-lock.json").read_text(encoding="utf-8"))["skills"]]))
def test_descriptions_have_use_when_examples(path):
    meta = yaml.safe_load(Path(path).read_text(encoding="utf-8").split("---\n")[1])
    tail = meta["description"].split("Use when:")[-1]
    assert "Use when:" in meta["description"] and 2 <= tail.count("«") <= 3, meta["description"]

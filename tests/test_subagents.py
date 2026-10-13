"""The project's read-only subagents (.claude/agents/) and their hooks (.claude/hooks/subagents.py)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude/hooks/subagents.py"
AGENTS = ["source-inspector", "pattern-librarian", "bench-runner", "independent-checker", "mesh-reader"]


def run(mode, payload):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    result = subprocess.run([sys.executable, str(HOOK), mode], input=raw, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout.strip() else {}


def frontmatter(name):
    text = (ROOT / f".claude/agents/{name}.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    return yaml.safe_load(text.split("---\n")[1])


@pytest.mark.parametrize("name", AGENTS)
def test_every_subagent_is_read_only(name):
    meta = frontmatter(name)
    assert meta["name"] == name and "use when" in meta["description"].lower()
    tools = [t.strip() for t in meta["tools"].split(",")]
    assert not {"Edit", "Write", "NotebookEdit"} & set(tools)
    assert {t.strip() for t in meta["disallowedTools"].split(",")} >= {"Edit", "Write"}
    assert meta["model"] == "inherit" and meta["memory"] == "project"
    assert not any(t.startswith("mcp__") and t.endswith("__*") for t in tools)   # no whole MCP server
    assert not [t for t in tools if any(w in t for w in ("delete", "create", "set_", "save", "execute", "edit",
                                                          "move", "rename", "batch_replace", "transform"))]


def test_subagent_hooks_are_wired():
    hooks = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    start = hooks["SubagentStart"][0]
    assert all(n in start["matcher"] for n in AGENTS) and "subagents.py\" start" in start["hooks"][0]["command"]
    stop = hooks["SubagentStop"][0]
    assert stop["matcher"] == "independent-checker" and "subagents.py\" stop" in stop["hooks"][0]["command"]
    checker = frontmatter("independent-checker")["hooks"]["PreToolUse"][0]
    assert "deny-geometry" in checker["hooks"][0]["command"]


def test_start_gives_the_read_only_reminder():
    out = run("start", {"agent_type": "bench-runner"})
    assert out["hookSpecificOutput"]["hookEventName"] == "SubagentStart"
    assert "Read-only" in out["hookSpecificOutput"]["additionalContext"]


def test_stop_blocks_without_the_table():
    out = run("stop", {"agent_type": "independent-checker", "last_assistant_message": "Everything looks fine."})
    assert out == {"decision": "block", "reason": "report the table: check | expected | measured | pass/fail"}
    table = ("| check | expected | measured | pass/fail |\n|---|---|---|---|\n| bbox | 10 | 10.0 | pass |\n"
             "| levels | 3 | 3 | pass |")
    assert run("stop", {"last_assistant_message": table}) == {}
    assert run("stop", "not json")["decision"] == "block"                     # fail closed


@pytest.mark.parametrize("tool_input, denied", [
    ({"file_path": "C:/repo/src/dt_ai/geometry/from_spec.py"}, True),
    ({"pattern": "def build", "path": "src\\dt_ai\\geometry"}, True),
    ({"command": "cat src/dt_ai/geometry/from_spec.py"}, True),
    ({"file_path": "C:/repo/src/twinqa/geometry/checks.py"}, False),
    ({"file_path": "C:/repo/docs/domain/patterns/opening-plane.md"}, False),
])
def test_the_checker_never_reads_how_the_model_was_built(tool_input, denied):
    out = run("deny-geometry", {"tool_name": "Read", "tool_input": tool_input})
    assert (out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny") is denied
    assert run("deny-geometry", "broken")["hookSpecificOutput"]["permissionDecision"] == "deny"

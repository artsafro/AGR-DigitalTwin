"""The project's read-only subagents (.claude/agents/) and their hooks (.claude/hooks/subagents.py)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude/hooks/subagents.py"
AGENTS = ["source-inspector", "pattern-librarian", "bench-runner", "independent-checker", "mesh-reader"]
TABLE = ("| check | expected | measured | pass/fail |\n|---|---|---|---|\n| bbox | 10 | 10.0 | pass |\n"
         "| levels | 3 | 2 | fail |")


def run(mode, payload, root=ROOT):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
    result = subprocess.run([sys.executable, str(HOOK), mode], input=raw, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout.strip() else {}


def frontmatter(name):
    text = (ROOT / f".claude/agents/{name}.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    return yaml.safe_load(text.split("---\n")[1])


@pytest.mark.parametrize("name", AGENTS)
def test_every_subagent_is_read_only(name):
    meta = frontmatter(name)
    assert meta["name"] == name and meta["description"].lower().startswith("use when")
    tools = [t.strip() for t in meta["tools"].split(",")]
    assert not {"Edit", "Write", "NotebookEdit"} & set(tools)
    assert {t.strip() for t in meta["disallowedTools"].split(",")} >= {"Edit", "Write"}
    assert meta["model"] == "inherit" and meta["memory"] == "project"
    assert not any(t.startswith("mcp__") and (t.endswith("__*") or t.count("__") == 1) for t in tools)
    assert not [t for t in tools if any(w in t for w in ("delete", "create", "set_", "save", "execute", "edit",
                                                          "move", "rename", "batch_replace", "transform"))]
    bash_hooks = [h for e in meta["hooks"]["PreToolUse"] if "Bash" in e["matcher"] for h in e["hooks"]]
    assert any(h["command"].endswith("subagents.py\" guard") for h in bash_hooks)


def test_subagent_hooks_are_wired():
    hooks = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    for event, mode in (("SubagentStart", "start"), ("SubagentStop", "stop")):
        entry = hooks[event][0]
        assert all(n in entry["matcher"] for n in AGENTS) and f"subagents.py\" {mode}" in entry["hooks"][0]["command"]
    checker = frontmatter("independent-checker")["hooks"]["PreToolUse"]
    assert any("deny-geometry" in h["command"] for e in checker for h in e["hooks"])


def test_start_gives_the_read_only_reminder():
    out = run("start", {"agent_type": "bench-runner", "agent_id": "t-start"})
    assert out["hookSpecificOutput"]["hookEventName"] == "SubagentStart"
    assert "Read-only" in out["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("message, ok", [
    ("Everything looks fine.", False),
    ("| check | expected | measured | pass/fail |\n|---|---|---|---|\n| bbox | 10 | 99 | unknown |", False),
    ("| pass |\n| prose |\n| no verdict table |", False),                    # review 1 of #86
    (TABLE, True),
    ("check | expected | measured | pass/fail\n---|---|---|---\nbbox | 10 | 10 | pass", True),   # no outer pipes
    ("| check | expected | measured | pass/fail |\n|---|---|---|---|\n| uv | - | - | not measured: no UV |", True),
    ("bbox | 10 | 10 | pass", False),                                          # review 2 of #86: no table
    ("| check | expected | measured | pass/fail |\n|---|---|---|---|\n| bbox | 10 | 10 | pass-through |", False),
])
def test_stop_wants_a_verdict_table_from_the_checker(message, ok):
    run("start", {"agent_id": "t-stop"})
    out = run("stop", {"agent_type": "independent-checker", "agent_id": "t-stop", "last_assistant_message": message})
    assert (out == {}) is ok, out
    if not ok:                                                                # a retry must comply too (review 2)
        run("start", {"agent_id": "t-stop"})
        assert run("stop", {"agent_type": "independent-checker", "agent_id": "t-stop", "stop_hook_active": True,
                            "last_assistant_message": message})["decision"] == "block"
    if not ok:
        assert out["decision"] == "block" and "report the table" in out["reason"]


def test_stop_names_tracked_files_a_subagent_changed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@x"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=repo, check=True)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "a"], cwd=repo, check=True)
    run("start", {"agent_id": "t-changed"}, root=repo)
    (repo / "a.txt").write_text("changed\n", encoding="utf-8")
    out = run("stop", {"agent_type": "bench-runner", "agent_id": "t-changed", "last_assistant_message": "done"},
              root=repo)
    assert out["decision"] == "block" and "a.txt" in out["reason"]
    retry = {"agent_type": "bench-runner", "agent_id": "t-changed", "stop_hook_active": True}
    assert run("stop", {**retry, "last_assistant_message": "Done."}, root=repo)["decision"] == "block"   # review 2
    assert run("stop", {**retry, "last_assistant_message": "I changed a.txt."}, root=repo) == {}


@pytest.mark.parametrize("raw", ["not json", "[]", "null", '"x"'])
def test_hooks_fail_closed_on_bad_input(raw):
    assert run("stop", raw)["decision"] == "block"
    for mode in ("guard", "deny-geometry"):
        assert run(mode, raw)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("command, denied", [
    ("python -c \"from pathlib import Path; Path('docs/x.txt').write_text('y')\"", True),   # review 1 of #86
    ("echo x > docs/x.txt", True),
    ("git commit -qm x", True),
    ("sed -i s/a/b/ src/dt_ai/spec/mesh.py", True),
    ("rm -rf jobs/OBJ03", True),
    ("git -C . restore docs/probe.txt", True),                                  # review 2 of #86
    ("git -c core.x=y commit -qm x", True),
    ("uv run python tools/qa/run_benchmark.py --etalon e.fbx --object o.json --tolerances t.json --output C:/x/o", False),
    ("uv run python -m pytest -q -p no:cacheprovider --basetemp=C:/x/t tests/test_subagents.py", False),
    ("git log -1 --oneline", False),
    ("grep -n plane docs/domain/patterns/opening-plane.md 2>/dev/null", False),
])
def test_guard_denies_plain_writes_in_bash(command, denied):
    out = run("guard", {"tool_name": "Bash", "tool_input": {"command": command}})
    assert (out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny") is denied


@pytest.mark.parametrize("tool, tool_input, denied", [
    ("Read", {"file_path": "src/dt_ai/geometry/from_spec.py"}, True),
    ("Read", {"file_path": "src/dt_ai/./geometry/from_spec.py"}, True),                  # review 1 of #86
    ("Read", {"file_path": str(ROOT / "src/dt_ai/geometry/from_spec.py")}, True),
    ("Grep", {"pattern": "def build", "path": "src/dt_ai"}, True),                         # an ancestor search
    ("Grep", {"pattern": "def build"}, True),                                              # the whole project
    ("Glob", {"pattern": "src/dt_ai/geometry/*.py"}, True),
    ("Bash", {"command": "cd src/dt_ai && cat geometry/from_spec.py"}, True),
    ("Bash", {"command": "grep -rn build src"}, True),
    ("Bash", {"command": "grep -R FORBIDDEN ./src"}, True),                       # review 2 of #86
    ("Bash", {"command": "cat src/dt_ai/*/*.py"}, True),
    ("Bash", {"command": "grep -rn plane ."}, True),
    ("Bash", {"command": "git grep FORBIDDEN"}, True),                            # review 3 of #86
    ("Bash", {"command": "grep -R FORBIDDEN . docs"}, True),
    ("Bash", {"command": "grep -rn plane docs/domain/patterns"}, False),
    ("Read", {"file_path": "src/twinqa/geometry/checks.py"}, False),
    ("Grep", {"pattern": "opening", "path": "docs/domain/patterns"}, False),
    ("Bash", {"command": "uv run python tools/qa/check_geometry.py --model m.json"}, False),
])
def test_the_checker_never_reads_how_the_model_was_built(tool, tool_input, denied):
    out = run("deny-geometry", {"tool_name": tool, "tool_input": tool_input})
    assert (out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny") is denied

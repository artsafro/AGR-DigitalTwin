"""PreToolUse pipeline gate for Claude Code (docs/HARNESS_PLAN.md §16; rules in tools/git-hooks/pipeline_gate.py).

Blocks (permission "deny", unlike guard.py's "ask": it checks the pipeline state, not a danger):
- a Write/Edit of `jobs/<JOB>/STATE.md` that leaves a `Pipeline status` above draft without the job's
  `pipeline/spec.json`, `spec.report.json` and `check.json` on disk (checked: also no failed check);
- a Write of a new `jobs/<JOB>/scripts/*` file that does not name a listed engine gap (`Engine gap: EG<n>`).
Every other call passes. The git pre-commit runs the same rules for every agent.
"""
import importlib.util
import json
import sys
from pathlib import Path


def _gate():
    path = Path(__file__).resolve().parents[2] / "tools" / "git-hooks" / "pipeline_gate.py"
    spec = importlib.util.spec_from_file_location("pipeline_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def deny(reasons):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "pipeline_gate: " + "; ".join(reasons) + " (docs/HARNESS_PLAN.md §16)",
    }}))
    sys.exit(0)


def new_text(tool, tin, path):
    if tool == "Write":
        return tin.get("content", "")
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    a, b = tin.get("old_string", ""), tin.get("new_string", "")
    return old.replace(a, b) if tin.get("replace_all") else old.replace(a, b, 1)


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        sys.exit(0)
    if not isinstance(data, dict) or not isinstance(data.get("tool_input"), dict):
        sys.exit(0)
    tool = data.get("tool_name", "")
    tin = data["tool_input"]
    target = tin.get("file_path", "")
    if tool not in ("Write", "Edit") or not isinstance(target, str) or not target:
        sys.exit(0)
    path = Path(target)
    parts = [p.lower() for p in path.parts]
    if "jobs" not in parts:
        sys.exit(0)
    k = len(parts) - 1 - parts[::-1].index("jobs")
    if len(path.parts) < k + 3:
        sys.exit(0)
    root, job, rest = Path(*path.parts[:k]), path.parts[k + 1], path.parts[k + 2:]
    gate = _gate()
    rel = "/".join(("jobs", job) + tuple(rest))
    if tuple(r.lower() for r in rest) == ("state.md",):       # Windows names are case-blind (review 1 of PR #73)
        rel = f"jobs/{job}/STATE.md"
        text = new_text(tool, tin, path)

        def read(p):
            if p == rel:
                return text
            f = root / p
            return f.read_bytes() if f.is_file() else None

        errors = gate.job_errors(job, read, require_line=False)
        if errors:
            deny(errors)
    elif tool == "Write" and not path.exists() and gate.is_job_script(rel):
        backlog = root / "docs" / "backlog.md"
        errors = gate.script_errors(rel, str(tin.get("content", "")),
                                    backlog.read_text(encoding="utf-8") if backlog.is_file() else None)
        if errors:
            deny(errors)
    sys.exit(0)


if __name__ == "__main__":
    main()

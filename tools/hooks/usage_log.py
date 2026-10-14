"""Usage log of subagents, skills and slash commands: logs/agent-usage.jsonl (docs/agents/WORKFLOW.md, "Triggers").

  py -3 tools/hooks/usage_log.py post            PostToolUse on Agent / Task / Skill: one line per call
  py -3 tools/hooks/usage_log.py prompt          UserPromptSubmit: one line when the prompt is a /command
  py -3 tools/hooks/usage_log.py stats [--days N]   counts per subagent, project skill and command (zeros too)

A line: time (UTC), session_id, branch, kind (agent | skill | command), name, command (the last /command of the
session before the call, or null). The log lives in the main checkout (`git rev-parse --git-common-dir`/..), so
every worktree writes one file; it is local and git-ignored. Logging never blocks or fails a call.
"""
import datetime
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

COMMAND_TAG = re.compile(r"<command-name>/?([^<\s]+)</command-name>")


def _root():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def _git(*args):
    try:
        r = subprocess.run(["git", *args], cwd=_root(), capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def log_path():
    if os.environ.get("AGR_USAGE_LOG"):              # tests and dry runs
        return Path(os.environ["AGR_USAGE_LOG"])
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir")
    base = Path(common).parent if common else _root()
    return base / "logs" / "agent-usage.jsonl"


def last_command(transcript):
    """The last /command the user ran in this session, from the transcript (None without one)."""
    found = None
    try:
        for line in Path(transcript).read_text(encoding="utf-8", errors="replace").splitlines():
            if "<command-name>" in line:
                m = COMMAND_TAG.findall(line)
                found = m[-1] if m else found
    except (OSError, TypeError):
        return None
    return found


def entry(payload):
    tool, args = payload.get("tool_name"), payload.get("tool_input") or {}
    if payload.get("hook_event_name") == "UserPromptSubmit":
        m = re.match(r"\s*/([\w:.-]+)", payload.get("prompt") or "")
        if not m:
            return None
        kind, name = "command", m.group(1)
    elif tool in ("Agent", "Task"):
        kind, name = "agent", args.get("subagent_type") or "general-purpose"
    elif tool == "Skill":
        kind, name = "skill", args.get("skill")
    else:
        return None
    return {"time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "session_id": payload.get("session_id"), "branch": _git("branch", "--show-current"), "kind": kind,
            "name": name, "command": None if kind == "command" else last_command(payload.get("transcript_path"))}


def write(payload):
    line = entry(payload)
    if not line:
        return
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def read(days=None):
    path = log_path()
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days) if days else None
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
            if since is None or datetime.datetime.fromisoformat(row["time"]) >= since:
                rows.append(row)
        except (ValueError, KeyError, TypeError):
            continue
    return rows


def known():
    """{kind: names} the project defines: subagents, project skills (not vendored), commands."""
    root = _root()
    lock = root / "skills-lock.json"
    vendored = set(json.loads(lock.read_text(encoding="utf-8"))["skills"]) if lock.exists() else set()
    return {"agent": sorted(p.stem for p in (root / ".claude/agents").glob("*.md")),
            "skill": sorted(p.name for p in (root / ".agents/skills").iterdir() if p.is_dir() and p.name not in vendored),
            "command": sorted(p.stem for p in (root / ".claude/commands").glob("*.md"))}


def stats(days):
    rows = read(days)
    counts = Counter((r.get("kind"), r.get("name")) for r in rows)
    out = [f"Usage, last {days} days ({log_path()}; {len(rows)} entries):"]
    if not log_path().exists():
        out.append("  (no log yet: the hooks write it from the first call on)")
    for kind, names in known().items():
        cells = [f"{n} {counts.get((kind, n), 0)}" for n in names]
        out.append(f"  {kind}s: " + ", ".join(cells))
        zero = [n for n in names if not counts.get((kind, n))]
        if zero:
            out.append(f"    never called: {', '.join(zero)}")
    other = sorted({(k, n) for k, n in counts if n not in known().get(k, [])})
    if other:
        out.append("  other: " + ", ".join(f"{n} ({k}) {counts[(k, n)]}" for k, n in other))
    return "\n".join(out)


def main(argv):
    mode = argv[0] if argv else ""
    if mode == "stats":
        days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 7
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(stats(days))
        return 0
    if mode not in ("post", "prompt"):
        print(f"unknown mode {mode!r}", file=sys.stderr)
        return 2
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if isinstance(payload, dict):
            write(payload)
    except Exception:                                # logging is never a reason to fail a call
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

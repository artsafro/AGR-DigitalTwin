"""PreToolUse guard for Claude Code, Codex and Antigravity.

Forces a user confirmation for destructive, outward, or asset-corrupting actions.
Never blocks outright; returns permission decision "ask" so the user decides.
Dual-protocol support:
- Antigravity: inputs 'toolCall', outputs {"decision": "ask"|"allow", "reason": ...}
- Claude Code: inputs 'tool_name', outputs {"hookSpecificOutput": ...} or exit 0
"""
import json
import os
import re
import sys
from pathlib import Path

PRODUCTION_EXT = r"\.(fbx|blend|max|uasset|umap|obj|abc|usd[az]?|glb|gltf|rvt|skp|dwg|psd|exr|tiff?|png|tga)\b"

# (regex, reason) checked against shell commands (Bash and PowerShell / cmd).
SHELL_RULES = [
    (r"\bgit\b[^|;&]*\bpush\b", "git push publishes to a remote"),
    (r"\bgit\b[^|;&]*\breset\b[^|;&]*--hard", "git reset --hard discards work"),
    (r"\bgit\b[^|;&]*\bclean\b", "git clean deletes untracked files"),
    (r"\bgit\b[^|;&]*\bbranch\b[^|;&]*(\s-D\b|--delete\s+--force|-d\s+-f)", "force branch delete"),
    (r"\bgit\b[^|;&]*\b(checkout|restore)\b[^|;&]*\s(--\s+)?\.(\s|$)", "discards working-tree changes"),
    (r"\bgit\b[^|;&]*\b(filter-branch|filter-repo|rebase|update-ref\s+-d)\b", "rewrites history/refs"),
    (r"\bgit\s+lfs\s+migrate\b", "rewrites history (LFS migrate)"),
    (r"\b(rm|del|rmdir|rd|Remove-Item|ri)\b[^|;&]*(Revit[/\\\\]|Source[/\\\\]|Unreal[/\\\\]|" + PRODUCTION_EXT + ")",
     "deletes source/production assets"),
    (r"\brm\s+-[a-zA-Z]*r|\bRemove-Item\b[^|;&]*-(Recurse|Rec)|\b(rmdir|rd)\b[^|;&]*/[sS]|\brobocopy\b[^|;&]*/(MIR|PURGE)|\bfind\b[^|;&]*-delete",
     "recursive delete / mass overwrite"),
    (r"\b(winget|choco|scoop|msiexec)\b|\bnpm\s+(i|install)\s+(-g|--global)|\b(pip|uv\s+pip|uv\s+tool)\s+install\b",
     "installs software"),
    (r"\b(setx|reg\s+(add|delete)|Set-ExecutionPolicy|New-ItemProperty|Set-ItemProperty)\b", "system-level change"),
]

HOME = Path.home()
ALLOWED_WRITE_ROOTS = [
    HOME / ".claude" / "projects",
    HOME / ".claude" / "skills",
    HOME / ".gemini",
    Path(os.environ.get("TEMP", HOME / "AppData/Local/Temp")) / "claude",
    Path(os.environ.get("TEMP", HOME / "AppData/Local/Temp")) / "antigravity",
]


def ask(reason: str, is_antigravity: bool) -> None:
    if is_antigravity:
        print(json.dumps({
            "decision": "ask",
            "reason": f"guard.py: {reason}"
        }))
    else:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"guard.py: {reason}",
        }}))
    sys.exit(0)


def allow(is_antigravity: bool) -> None:
    if is_antigravity:
        print(json.dumps({"decision": "allow"}))
    sys.exit(0)


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, RuntimeError):
        return False


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            allow(False)
        data = json.loads(raw)
    except Exception:
        allow(False)

    is_antigravity = "toolCall" in data

    if is_antigravity:
        tool_call = data.get("toolCall", {}) or {}
        tool = tool_call.get("name", "")
        targs = tool_call.get("args", {}) or {}
        cmd = targs.get("CommandLine", "")
        target = targs.get("TargetFile", "")
    else:
        tool = data.get("tool_name", "")
        tin = data.get("tool_input", {}) or {}
        cmd = tin.get("command", "")
        target = tin.get("file_path") or tin.get("notebook_path", "")

    # 1. Shell commands
    if tool in ("Bash", "PowerShell", "run_command", "shell", "exec_command", "local_shell"):
        for pattern, reason in SHELL_RULES:
            if re.search(pattern, cmd, re.IGNORECASE):
                ask(reason, is_antigravity)

    # 2. File write/edit commands
    elif tool in ("Write", "Edit", "NotebookEdit", "write_to_file", "replace_file_content"):
        if target:
            p = Path(target)
            # Protect binary/production extensions from accidental text overwrites
            if re.search(PRODUCTION_EXT, p.name, re.IGNORECASE):
                ask(f"writing to production asset: {p.name}", is_antigravity)

            # Check boundary
            workspaces = data.get("workspacePaths", [])
            project_roots = [Path(w) for w in workspaces] if workspaces else []
            if os.environ.get("CLAUDE_PROJECT_DIR"):
                project_roots.append(Path(os.environ["CLAUDE_PROJECT_DIR"]))
            if data.get("cwd"):
                project_roots.append(Path(data["cwd"]))
            project_roots.append(Path("."))

            all_allowed = project_roots + ALLOWED_WRITE_ROOTS
            if not any(inside(p, r) for r in all_allowed):
                ask(f"write outside project/allowed folders: {target}", is_antigravity)

    allow(is_antigravity)


if __name__ == "__main__":
    main()

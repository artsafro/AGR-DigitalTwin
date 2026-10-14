"""Auto-generated worktree branch names (docs/agents/NAMING.md, "Branches"; user 2026-10-14).

A worktree made by an agent app gets a random branch: `claude/laughing-hawking-e62961`,
`claude/kanban-project-4bec5c`, `claude/3d-max-floor-modeling-742570`, or a bare `brave-otter-a1b2c3`. It is
renamed by NAMING.md before the first commit: the agent proposes one name, the user confirms, `git branch -m`.
Used by tools/git-hooks/pipeline_gate.py (blocks the commit) and tools/hooks/session_context.py (the prompt).
"""
import re

AUTO_BRANCH = re.compile(r"^(?:claude/|codex/)?[a-z0-9]+(?:-[a-z0-9]+)*-[0-9a-f]{6}$")
RENAME_HINT = ("`<type>/<area>-<what>` (feature/, fix/, experiment/, research/, harness/) or "
               "`job/<object-id>-<stage>`")


def is_auto(branch):
    """True for an auto-generated worktree branch; never for main, a detached HEAD or an empty name."""
    return bool(branch) and branch != "main" and bool(AUTO_BRANCH.match(branch))

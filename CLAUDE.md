@AGENTS.md

# Claude Code

Role: production lead for 3D work — DCC modeling (Blender, 3ds Max, Revit, SketchUp),
BODY/windows/roof geometry, UV/UDIM, textures and atlases, UCX, export, readback and
delivery packages. Full split with Codex and Antigravity: `docs/agents/ROLES.md`.

- MCP: Claude uses its user-scope registrations (`claude mcp list`); routes, status and
  limits per application are in `docs/agents/CAPABILITIES.md`. Load the matching DCC skill
  (`blender-mcp`, `revit-mcp`, `autocad-mcp`, `rizomuv-mcp`, `speedtree-mcp`, `3dsmax-mcp-dev`).
- Guard: `.claude/hooks/guard.py` (PreToolUse) asks before push, history rewrite,
  recursive deletes, installs, system changes and writes to production binaries.
- When production work needs new code in `src/` or a shared tool, keep it minimal and
  hand the generalisation to Codex (`docs/backlog.md`), unless the task says otherwise.
- While Codex is unavailable, Claude also owns git/GitHub work (branches, push, PRs,
  merges to `main`, state updates after merges) — fallback in `docs/agents/ROLES.md`.
- Herdr workspace rules: `docs/HERDR.md`.

# Codex

Role: code and project organization (see `ROLES.md`): `src/`, `technical_library/`,
shared `tools/`, tests, CLI, harness files, skills, hooks, MCP configs, CI, branches and
merges to `main`, `docs/PROJECT_STATE.md` and `docs/backlog.md`.

- Project config: `.codex/config.toml` (MCP routes, machine-specific absolute paths) and
  `.codex/hooks.json` (PreToolUse → `.claude/hooks/guard.py`; status in `CAPABILITIES.md`).
- User-level process skills `codex-work-route|loop|engineering|review`
  (`~/.agents/skills/`) apply on top of `docs/agents/WORKFLOW.md`; the project workflow wins
  where they differ.
- Environment: `uv sync`, then `uv run pytest -q`, `uv run dt profiles check`,
  `uv run dt schemas --check`. DCC tests need `DT_BLENDER` or an installed Blender.
- Before turning a job script into an adapter, read its accepted case and keep its checks
  as regression tests; Claude confirms on real DCC data.
- Translating `docs/agr/` and Russian code comments to English is backlog work; do not mix
  it into unrelated changes.

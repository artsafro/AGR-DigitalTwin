# Roles

Decided by the user on 2026-10-06: Claude is stronger at 3D/DCC production work,
Codex at coding and project organization. Antigravity supports both.
Any agent may take any task the user assigns; this table decides the default owner.

| Area | Owner | Reviewer |
|---|---|---|
| DCC production: modeling, BODY/windows/roof, UV/UDIM, textures, atlases, UCX, export, readback, packages (`jobs/`, DCC runs) | Claude | Codex for code; user for acceptance |
| Domain rules and conflicts (`docs/domain/`, `standards/`, `GLOSSARY.md`) | Claude (proposes) | user decides every conflict |
| Code: `src/`, `technical_library/`, `tools/` (except one-off job scripts), tests, CLI | Codex | Claude when production behaviour changes |
| Generalising a proven job script into an adapter / library package | Codex | Claude (checks against the accepted case) |
| Harness and organization: `AGENTS.md`, `docs/agents/`, skills, hooks, MCP configs, CI, repo hygiene, branches, merges to `main` | Codex | Claude for files it relies on (`CLAUDE.md`, DCC skills) |
| `docs/PROJECT_STATE.md`, `docs/backlog.md` | Codex (after merges) | — |
| Research, documentation and translation (`docs/agr/` → English), independent second-opinion review | Antigravity | owner of the area |

## Agent homes

| Agent | Instructions | Own config | Skills |
|---|---|---|---|
| Claude Code | `CLAUDE.md` (imports `AGENTS.md`) | `.claude/settings.json`, `.claude/hooks/` | `.claude/skills/` (generated from `.agents/skills/`) |
| Codex | `AGENTS.md`, `docs/agents/codex.md` | `.codex/config.toml`, `.codex/hooks.json` | `.agents/skills/` + user `codex-work-*` |
| Antigravity | `GEMINI.md` → `AGENTS.md` | `.agents/mcp_config.json`, `.agents/hooks.json` | `.agents/skills/` |

## Handoffs

- Claude → Codex: a working job script plus the case that accepted it, when the operation
  should become reusable; a missing check in the validator; a broken tool (with evidence).
- Codex → Claude: a new or changed adapter/tool, with tests and the exact command; Claude
  confirms it on real DCC data before it is marked WORKING in `CAPABILITIES.md`.
- Handoff text lives in the branch (job `STATE.md` or the PR description), not in chat.

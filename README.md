# AGR-DigitalTwin

Architectural digital twin production: NPM/VPM delivery models per the Moscow regulation
(later IFC) for buildings, Ground, MAF, Flora and UCX collisions, plus an Unreal experience.
Worked on by Claude Code (3D/DCC production), Codex (code and organization) and
Antigravity (research, docs, review) — see `AGENTS.md` and `docs/agents/ROLES.md`.

## Setup (Windows)

```powershell
git lfs install
uv sync
uv run pytest -q
uv run dt profiles check
uv run dt schemas --check
```

Install the pre-commit hook that commits files over 50 MB as links:

```powershell
Copy-Item tools/git-hooks/pre-commit .git/hooks/pre-commit
```

DCC tests use an installed Blender (auto-detected) or `DT_BLENDER`.

## Layout

| Path | Content |
|---|---|
| `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` | agent instructions |
| `docs/` | state, roles, workflow, domain rules, pipeline, backlog, cases; `docs/agr/` = AGR knowledge base (Russian originals) |
| `standards/` | locked machine-readable NPM/VPM rules + regulation PDF (LFS) |
| `src/dt_ai/`, `src/twinqa/` | pipeline core and delivery validator |
| `technical_library/`, `tools/`, `adapters/` | operation packages, scripts, MCP servers, DCC bridges |
| `jobs/` | per-object specs, STATE and evidence (outputs local only) |
| `data/` | local only: sources, archives of the former projects |

## Origin

Created on 2026-10-06 from two projects, without their Git history:
DigitalTwinProject (Claude; harness, domain rules, validator, MCP routes) and AGR_Project
(Codex; pipeline code, operation library, accepted cases). Full histories:
`data/archive/*.bundle` (local).

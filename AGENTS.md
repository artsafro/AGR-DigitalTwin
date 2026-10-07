# AGR-DigitalTwin — agent instructions

Shared by every agent (Claude Code, Codex, Antigravity). Agent-specific notes:
`CLAUDE.md`, `docs/agents/codex.md`, `GEMINI.md`. Talk to the user in Russian; write code,
commands, identifiers and docs in English.

## Goal

Produce delivery models from architectural sources — NPM and VPM per the Moscow
regulation, later IFC — for buildings (OKS), Ground, MAF (GroundEl), Flora and UCX
collisions, plus the interactive Unreal experience. Priorities, in order:
1. Architectural accuracy 2. Correct scale and transforms 3. Material correctness
4. Performance 5. Visual fidelity.

## Where things are

| Need | Read |
|---|---|
| Current state, next actions | `docs/PROJECT_STATE.md` |
| Who owns what (Claude / Codex / Antigravity) | `docs/agents/ROLES.md` |
| Task loop, handoff, experience capture | `docs/agents/WORKFLOW.md` |
| Tools, MCP routes and their verified status | `docs/agents/CAPABILITIES.md` |
| Production rules with citations (NPM/VPM, geometry, UV, materials, export, validation) | `docs/domain/` |
| Open conflicts between sources | `docs/domain/conflicts.md` |
| Pipeline stages and their status | `docs/pipeline.md` |
| Unsolved work | `docs/backlog.md` |
| Accepted cases and lessons | `docs/cases.md` |
| Terms | `GLOSSARY.md` |
| Names for scripts, tools, jobs, outputs, branches and tags; object ids | `docs/agents/NAMING.md`, `jobs/REGISTRY.md` |
| Machine-readable rules | `standards/` (locked; change procedure in `standards/README.md`) |
| AGR knowledge base (Russian originals, read-only) | `docs/agr/` |

Read the domain file that matches the task before production work. Where sources
disagree (`docs/domain/conflicts.md`), ask the user; never pick a side silently.

## Code map

- `src/dt_ai/` — pipeline core: models, build, geometry (exterior, shell, connect, UV),
  materials, packaging, RunRecord. CLI: `uv run dt --help`.
- `src/twinqa/` — delivery validator V001–V017, standards loader, PNG/UV/GeoJSON/clearance.
- `technical_library/` — reviewed operation packages (atlases, UV, texture tiles, mesh audit).
- `tools/` — runnable scripts: `qa/`, `blender/`, `mcp/` (servers), `herdr/`, `git-hooks/`,
  plus object/operation scripts from accepted cases.
- `adapters/` — DCC bridges (Blender, SketchUp, Max/Revit/CAD notes).
- `jobs/<JOB>/` — per-object spec, STATE and evidence (text tracked; `outputs/`, `runs/` local only).
- `data/` — local only, git-ignored: heavy sources (`data/sources/`), archives.

Checks: `uv run pytest -q`, `uv run dt profiles check`, `uv run dt schemas --check`.

## Rules for every task

- One task = one branch = one worktree = one writing agent. Branch names, prefixes and tags:
  `docs/agents/NAMING.md`. `main` stays clean; work reaches it by reviewed merge.
  A second agent in someone else's worktree only reads, researches or reviews.
- One owner per DCC scene, MCP port and export folder at a time; worktrees do not isolate them.
- Before any DCC call confirm the application, document, units and version; start read-only.
  Saves and exports go to a new versioned path. Never overwrite sources or approved versions.
- A successful import or exit code 0 is not a finished model: read the exported file back
  and check topology, UV, materials and transforms (`validate-delivery` skill).
- `passed=true` is forbidden while any mandatory check or manual gate is open.
  Technical QA, user acceptance and publication are separate statuses.
- Mark synthetic data as synthetic. Never present it as data of a real object.
- Never push, rewrite history, delete source/production assets or change machine
  settings without the user's explicit approval (the guard hook asks).
- Update `docs/PROJECT_STATE.md` only on `main` after a merge; in task branches report
  state changes in the final summary.
- A new tool counts as shared only after it is listed in `docs/agents/CAPABILITIES.md` on `main`.

## Skills

Canonical project skills live in `.agents/skills/*/SKILL.md` (Codex, Antigravity);
`.claude/skills/` is a generated copy (`py -3 tools/sync_skills.py`; a test checks parity).
Follow the matching skill step by step.

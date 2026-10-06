# Project state

Last updated: 2026-10-07

## Current goal

NPM and VPM deliveries (later IFC) and an Unreal experience. The repository was just
assembled from the two former projects; the next step is the first real object through
the pipeline (`docs/pipeline.md`) and the conflict decisions that block it (`docs/backlog.md`).

## Repository

- Local: `C:\Users\artsafro\AGR-DigitalTwin` (branch `main`).
- GitHub: https://github.com/artsafro/AGR-DigitalTwin (private, `origin`).
- Task worktrees: `C:\Users\artsafro\HerdrWorktrees\AGR-DigitalTwin\<name>` (Herdr) or the
  agent's own worktree folder.
- `.gitattributes` routes production binaries to Git LFS, but the GitHub account's LFS budget
  is exhausted (push rejected 2026-10-06) — do not commit LFS files until H9 is decided.
  Files over 50 MB are committed as links (`tools/git-hooks/`).

## Former projects

| Project | Path | Archive in `data/archive/` |
|---|---|---|
| DigitalTwinProject (Claude) | `C:\Users\artsafro\DigitalTwinProject` | `DigitalTwinProject-Claude-all.bundle` |
| AGR_Project (Codex) | `C:\Users\artsafro\.AGR_Project` | `AGR_Project-all.bundle`, `AGR_Project-uncommitted-2026-10-06.zip` |

Their knowledge, code, rules and data were moved here. The user plans to delete both
folders. Before that, also check the user-level configs that still point at them
(backlog H2, H3) and re-create the bundles if work continued there after 2026-10-06 23:24.
Dropped on purpose: AGR process history (chat audits, receipts, PR queue), the Cursor
verifier, the KPP1-VPM task (cancelled by the user), Codex `agent_monitor` panel
(kept in the uncommitted-files archive).

## Agents

Roles: `docs/agents/ROLES.md` (Claude — 3D/DCC production; Codex — code and organization;
Antigravity — research, docs, review). Tools and MCP: `docs/agents/CAPABILITIES.md`.

## Available applications

Blender 4.4 and 5.1.2, Unreal Engine 5.5 and 5.7, 3ds Max 2024 and 2026, Revit 2025,
AutoCAD 2025, SketchUp 2026, SpeedTree Modeler 10.0.1, RizomUV 2024.1, Python 3.13 (`py -3`),
uv, Node/npx, Git LFS, GitHub CLI, poppler. DCC executables are not on PATH.

## Sources (local, `data/sources/`)

| Source | Path | Format | Status |
|---|---|---|---|
| PSU275 AR/MEP | `data/sources/revit/26_ПСУ275_АР_МЭП_RVT22.rvt` | Revit 2022, 282 MB | not analyzed |
| PSU275 MEP layout | `data/sources/revit/26_ПСУ275_Разбивочный файл_МЭП_RVT22.rvt` | Revit 2022 | not analyzed |
| KPP1 AR/MEP | `data/sources/revit/26_КПП1_АР_МЭП_RVT22.rvt` | Revit 2022, 110 MB | not analyzed (KPP1 task cancelled) |

Legacy job outputs (Obr22, GLB, SOSH1150, Ground, MASHI, facades…) are in
`jobs/<JOB>/outputs/` and other untracked job files, about 4.9 GB, local only.

## Deliverables

| Deliverable | Path | Status | Last validation |
|---|---|---|---|

No official delivery has passed yet. Accepted partial results: `docs/cases.md`.

## Known limitations

- Drive C is ~99% full (about 20 GB free); heavy data has no backup outside this machine (H9).
- 22 source conflicts and 5 dubious rules are open (`docs/domain/conflicts.md`). Decided on
  2026-10-07, mostly as SINTEZ AGR Checker: C1, C2, C3, C5, C6, C12, C13, C14, C19, C20, C21, C26
  (VPM target 150 000 triangles). Pending implementation: Q6 (C20), Q7 (GLB RGBA atlases, NPM placeholders).
- `docs/agr/` and parts of `technical_library/`, `tools/`, `jobs/` are in Russian (H4).
- Codex and Antigravity guard hooks are configured but not validated (H1).

## Next actions

1. Claude: P1 — analyze a real source read-only; decide remaining conflicts as they block work.
2. Codex: Q6 (encode C20), H1 (Codex hook), H2 (SketchUp venv), Q3 (one validator).
3. Claude + Codex: Q7 — RGB + `_o_` conversion of GLB NPM atlases, 128 px NPM placeholders.
4. Antigravity: H4 — translate `docs/agr/` core documents.

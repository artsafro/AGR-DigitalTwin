# Project state

Last updated: 2026-10-08

## Current goal

NPM and VPM deliveries (later IFC) and an Unreal experience. Two real objects are in
production: KPP1 (models v005 accepted as reviewed) and PSU275 (delivery-v003 accepted as reviewed).
Next: close their delivery gates (`docs/pipeline.md`, `docs/backlog.md`).

Harness rebuild (2026-10-08): `docs/HARNESS_PLAN.md` rev 3 (grilled §11/§12) — every modelling
run starts from an extracted `spec.json`, checked against hand-made etalons (`benchmark/`).
Week-1 work is tracked as GitHub issues #1–#14 (labels `extractor`, `benchmark`, `pattern`;
native blocked-by links). Order with one writing agent: #1 scaffolding → #3 material ID
ranges → #5 spec extractor on a synthetic box. Human tickets: #2 (move `Unreal/`),
#4 (window library file), #12 (etalon B01 in 3ds Max). Decisions: ADR 0001 (`docs/adr/`).

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
Fallback since 2026-10-07: while Codex is out of limits, Claude also owns git/GitHub work
(branches, push, PRs, merges to `main`, this file).
Claude has the `mattpocock-skills` plugin (user scope, 2026-10-08); its repo configuration
(issue tracker, triage labels, glossary = `GLOSSARY.md`) is in `AGENTS.md` → `## Agent skills`.

## Available applications

Blender 4.4 and 5.1.2, Unreal Engine 5.5 and 5.7, 3ds Max 2024 and 2026, Revit 2025,
AutoCAD 2025, SketchUp 2026, SpeedTree Modeler 10.0.1, RizomUV 2024.1, Python 3.13 (`py -3`),
uv, Node/npx, Git LFS, GitHub CLI, poppler. DCC executables are not on PATH.

## Sources (local, `data/sources/`)

| Source | Path | Format | Status |
|---|---|---|---|
| PSU275 AR/MEP | `data/sources/revit/26_ПСУ275_АР_МЭП_RVT22.rvt` | Revit 2022, 282 MB | analyzed with PDF/FBX/PPTX (`docs/sources/psu275.md`) |
| PSU275 MEP layout | `data/sources/revit/26_ПСУ275_Разбивочный файл_МЭП_RVT22.rvt` | Revit 2022 | not analyzed |
| KPP1 AR/MEP | `data/sources/revit/26_КПП1_АР_МЭП_RVT22.rvt` | Revit 2022, 110 MB | used for KPP1 v005 (Revit 2025 copy, `jobs/KPP1/STATE.md`) |

Legacy job outputs (Obr22, GLB, SOSH1150, Ground, MASHI, facades…) are in
`jobs/<JOB>/outputs/` and other untracked job files, about 4.9 GB, local only.

## Deliverables

| Deliverable | Path | Status | Last validation |
|---|---|---|---|
| KPP1 VPM + NPM v005 | `jobs/KPP1/` (`REPORT.md`) | accepted by the user as reviewed (~90 %); not a delivery — GeoJSON, MSK-77, district code, manual SINTEZ items open | 2026-10-07: xView overlaps 0/0, SINTEZ VPM 64/3, NPM 38/5 (deferred) |
| PSU275 VPM + NPM delivery-v003 (main SM_Psu_1 v009 + OKS SM_Psu_2..5) | `jobs/PSU275/` (`REPORT.md`) | accepted by the user as reviewed (3ds Max + Blender); not a delivery — GeoJSON, MSK-77, district code, address, УКЭП, Ground, racks, manual SINTEZ items open | 2026-10-07: T/leaks/overlaps/non-manifold/doubles 0, UV overflow 0, SINTEZ VPM 64/3 (deferred only) |

No official delivery has passed yet. Accepted partial results: `docs/cases.md`.

## Known limitations

- Drive C is ~99% full (about 20 GB free); heavy data has no backup outside this machine (H9).
- 22 source conflicts and 5 dubious rules are open (`docs/domain/conflicts.md`). Decided on
  2026-10-07, mostly as SINTEZ AGR Checker: C1, C2, C3, C5, C6, C12, C13, C14, C19, C20, C21, C26
  (VPM target 150 000 triangles). Pending implementation: Q6 (C20), Q7 (GLB RGBA atlases, NPM placeholders).
- Not merged on purpose (user, 2026-10-07): `claude/npm-models-school-kpp-ec9ced`
  (BUTOVSKAYA-NPM, work in progress), `claude/modest-ptolemy-684fb7` and `feature/kpp1-ground`
  (TEC26 ground, adds `ezdxf`).
- `docs/agr/` and parts of `technical_library/`, `tools/`, `jobs/` are in Russian (H4).
- Codex and Antigravity guard hooks are configured but not validated (H1).
- `fix/export-safety` (merged 2026-10-07): KPP1 `run_all.sh` refuses reused versions and
  writes quad review exports to a new `max-<V>`; PSU275 `assemble_body_roof.py` takes
  `<BODY> <out> <readback> <mesh.json>...` with provenance checks. Synthetic tests pass; real
  KPP1 full run and PSU275 v003/v004 re-assembly with the merged scripts not yet rerun.

## Next actions

0. Claude: harness week 1 — #1 → #3 → #5 (one writing agent, one branch per ticket).
1. Claude: PSU275 — racks, transformer massing, window frame density; check `clean_loops.py`
   and the unwelded-roof rule on KPP1 before generalising (case `PSU275_VPM_NPM_DELIVERY_V003.md`).
2. Claude: KPP1 — real `run_all.sh` run on a new version to confirm the merged runner;
   deferred delivery items when the user unblocks them.
3. Codex (when back): Q6 (encode C20), H1 (Codex hook), H2 (SketchUp venv), Q3 (one validator).
4. Claude + Codex: Q7 — RGB + `_o_` conversion of GLB NPM atlases, 128 px NPM placeholders.
5. Antigravity: H4 — translate `docs/agr/` core documents.

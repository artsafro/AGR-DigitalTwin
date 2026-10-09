# Project state

Last updated: 2026-10-08

## Current goal

NPM and VPM deliveries (later IFC) and an Unreal experience. Two real objects are in
production: KPP1 (models v005 accepted as reviewed) and PSU275 (delivery-v003 accepted as reviewed).
Next: close their delivery gates (`docs/pipeline.md`, `docs/backlog.md`).

Harness rebuild (2026-10-08): `docs/HARNESS_PLAN.md` rev 3 (grilled §11/§12) — every modelling
run starts from an extracted `spec.json`, checked against hand-made etalons (`benchmark/`).
Week-1 work is tracked as GitHub issues #1–#14 (labels `extractor`, `benchmark`, `pattern`;
native blocked-by links). Done and merged: #1 scaffolding, #3 material ID ranges, #5 spec
extractor (`dt spec extract`, PR #15), #16 roof confirmed at the input level (PR #18), #6 kinks,
rounded corners, strict full-height contour and questions file (PR #19), #7 openings from holes
or glass panes and one `jobs/<object>/questions.md` per object (`dt spec merge-questions`, PR #20).
Each PR had up to three Codex review rounds that ran the tests (`docs/agents/REVIEW_CHECKLIST.md`);
findings left open by that limit are extractor issues #21-#24. #8 typical floors written once
(`typical_of` / `repeat_to`, PR #25) merged with no findings left open. #9 KPP1 spec v001 merged
(PR #27): `jobs/KPP1/object.json` frame checked on Revit within 0.0 mm, roof 7.909 and contour
heights confirmed by the user, roof 7.911 (drainage slopes <= 2 deg), 23 glass openings, 58
questions in `jobs/KPP1/questions.md` for the user. Roof rules (drainage <= 10 deg, caps and
closure by structure) are in `docs/domain/patterns/parapet.md`. #10 Revit path merged (PR #30):
`measure_spec_revit.mjs` reads the document read only through `revit-http-2025`; walls and roofs as
bounding boxes, a wall proven along X/Y by its type width, curtain walls as glazing hosted by proven
walls, anything else a question. KPP1 Revit vs mesh: L0 324.20 / 319.48 m2 (Hausdorff 0.70 m), L1
322.52 / 322.00 m2 (0.26 m); `window_type` waits for #4, wall location lines #29. #11 merged
(PR #32): `dt spec compare`, report `jobs/KPP1/spec-compare-v001.md` — levels, roof and parapet
match the Revit reference within 2 mm; L0 0.70 m is the Revit path (entrance-frame walls as body,
#29); door recesses and 7.5 x 9 cm frame profiles are the mesh side (#31, user rules 2026-10-08:
recess from the floor >= 1.9 m, 0.7-3 m wide = door; curtain wall = one opening with `panes`;
both sizes <= 10 cm = relief). No Rhino verdict until #29. #31 merged (PR #33, spec v0.2):
door recesses from the floor leave the contour as openings (`kind` door, or window when glass
fills the height), relief <= 10 cm is no kink, panes of one frame are one opening with `panes`, an
opening across a level is one record with `level_from` / `level_to`. KPP1 mesh spec v009/v010:
both contours the facade rectangle; L1 equal to Revit (Hausdorff 0.0 m); L0 differs only by the
Revit entrance frames (0.70 m). Review-3 leftovers: #34. #29 merged (PR #35): Revit walls on
their location lines through the TwinPack commands of the revit-http add-in
(`tools/source/measure_spec_revit_twin.mjs`, `dt_ai.spec.revit_twin`; document never modified);
attachments by the main-walls hull rule (user decision 2026-10-08). KPP1 comparison v002
(`jobs/KPP1/spec-compare-v002.md`): levels, roof, parapet within 2 mm, both contours equal to
0.0 mm — Rhino not needed for contours (HARNESS_PLAN §11, closed test); openings differ by
definition (frame vs glass): user decision — the spec opening is the hole with its frame, glass as
attributes (#36). Review-3 leftovers: #37. The box route of #10 (`revit.py`) was removed (PR #38).
#36 merged (PR #39, spec v0.3): opening = hole with frame (mesh: the reveal the glass fills up to a
0.20 m frame; Revit: frame or curtain wall, else the family box), glass as `glass_w` / `glass_h`,
`depth_m` only as an exception (> 0.10 m off the default); glass without a reveal is a size question.
KPP1 comparison v003 (`jobs/KPP1/spec-compare-v003.md`): **match** on every criterion (openings 21 + 11
pairs within 5 mm) — first case "two paths match" in `docs/cases.md` (a comparison result, not a
model acceptance). PR #40 (user decisions 2026-10-09): the 0.20 / 0.10 m thresholds live in
`spec_extract` of the benchmark tolerances (`dt spec extract --tolerances`); vent grilles are openings of
kind `grille` (pattern `vent-grille`: npm_min texture, mid geometry; mesh classifier pending), reported
and kept out of the comparison verdict; KPP1 still match. #4 (PRs #41-#44): `library/windows/window_types.json`,
46 entries — 37 confirmed and named by the user (W01-W07, D01-D03, KPP1-W01..03, WT-01..24 of `Win_Typical.max`;
`confirmations.json`; WT-01 / WT-08 role `balcony_block`), the rest unconfirmed: SOSH1150 size variants,
CW_021 / CW_022 / D04 not typed. Fields = columns of the row under the fanlight (lower opaque panels excluded);
leftover #45 (opaque upper fanlight over a glazed lower band). Human tickets: #2 (move `Unreal/`), #4 (window
library file), #12 (etalon B01 in 3ds Max). Decisions: ADR 0001 (`docs/adr/`); user decisions
of 2026-10-08 on roof, contour and projections are in GLOSSARY and HARNESS_PLAN §4.

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

0. Claude: harness week 1 done for KPP1 (two paths match); next per the user: B01 etalon (#12); #4: the WT types wait for the user's acceptance and names; extractor follow-ups #21-#24, #34, #37 and the drainage issue (one writing agent, one branch per ticket, Codex review per PR).
1. Claude: PSU275 — racks, transformer massing, window frame density; check `clean_loops.py`
   and the unwelded-roof rule on KPP1 before generalising (case `PSU275_VPM_NPM_DELIVERY_V003.md`).
2. Claude: KPP1 — real `run_all.sh` run on a new version to confirm the merged runner;
   deferred delivery items when the user unblocks them.
3. Codex (when back): Q6 (encode C20), H1 (Codex hook), H2 (SketchUp venv), Q3 (one validator).
4. Claude + Codex: Q7 — RGB + `_o_` conversion of GLB NPM atlases, 128 px NPM placeholders.
5. Antigravity: H4 — translate `docs/agr/` core documents.

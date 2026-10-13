# Project state

Last updated: 2026-10-10

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
leftover #45 (opaque upper fanlight over a glazed lower band).
PRs #46-#49 (2026-10-09, two Codex review rounds each): #46 relief in section (user decision: a
projection or groove with depth and height both <= 0.10 m is relief, not a question); KPP1 spec v021
equals v020, all 83 rows of `jobs/KPP1/questions.md` gone, no open contour question. #47 benchmark
checkers `src/twinqa/geometry/` + `tools/qa/check_geometry.py` (bbox, levels, storey areas,
silhouettes, mesh, budget, opening planes, ID ranges; UCX_ meshes left out), B01 `tolerances.json`
and README; open edges are reported, never block (user decision); working on synthetic boxes only,
issue #14 stays open until the first green run on the etalon. #48 patterns `opening-plane`,
`typical-floor-repeat`, `non-90-corner`, `contour-niche` approved by the user (status draft until a
benchmark proves them; the 95 % plane cover stays a proposal until B01). #49 choices page
`docs/domain/conflict-choices-2026-10-09.md` for C7, C8, C10, C24, C25 (C3 decided earlier) waits
for the user's decisions. PR #50 (2026-10-10, three Codex review rounds): engine
`src/dt_ai/geometry/from_spec.py` builds a quad, welded mesh dump from a spec (walls by contour,
holes with reveals and planes, roof, parapet; unsupported shapes are errors); the B01 fixture spec
passes all 8 benchmark checks against the synthetic box — first spec -> model -> checkers loop,
synthetic only. PR #51 (2026-10-10): `tools/qa/run_benchmark.py` runs etalon FBX -> spec -> engine ->
`tools/export/export_mesh_blender.py` -> FBX readback -> checks; first green B01 run on the user's
etalon (files in `data/benchmark/bench-b01-box/`, hashes in `etalon.json`, `docs/cases.md`); #12-#14
closed. PR #52: C24 final (user, 2026-10-10, replaces the same-day reversed rule) — one opening depth
per building, `depth_m` only as an exception; `npm_min` plane = back polygon at the full depth, `mid`
at half; the extractor takes the depth from the opening plane (else the reveal, never the glass) and
asks about a plane or glass flush with the facade; the checker wants the profile's seat ±2 cm. B01
etalon moved to 0.2 m (run-v003 green); KPP1 v025 still matches Revit. Modeller briefs (Claude
Docs): B01 https://claude.ai/code/artifact/62e3769e-f61e-4c7c-96ee-7682fea85a5f, B02
https://claude.ai/code/artifact/e332aa9d-b0ae-4084-b70b-735eda67f741. PRs #53-#58 (2026-10-10, Codex
review rounds each): #53 B02 etalon checked (spec equal to the brief), runner checks the etalon before
the engine; #54 pattern `roof-inset-plane` (parapet from LEVEL_roof, structural parapet presence;
open edges = bottom ring + per inset roof exactly contour A + B, B embedded 10-50 mm, gap 2-10 mm);
#55 pattern `floor-step` (contour per floor, ledge roof ID / soffit facade ID); #58 pattern
`non-90-corner` (oblique walls, trapezoid strips; the engine refuses anything that would break under
the checkers' 0.1 mm weld). **B02 green end to end** (engine model 8/8 against the etalon). Issues
#56 (checker: horizontal face orientation), #57 (checker: non-manifold vertices). Next: terrace
with a parapet from the spec (PR A: pattern + contract + engine; PR B: extractor + etalon B02t).
#59 terrace PR A merged (2026-10-10, 3 Codex rounds, last two clean): pattern `terrace`, spec v0.4
`terraces: [{level, parapet_h_m}]`, engine parapet along the ledge's outer edges (outer face facade
ID, inner face / cap / walkable roof ID, thickness = `parapet_thickness_m`, every ledge part its own
parapet). Etalon B02t delivered (`data/benchmark/bench-b02t-terrace/`, FBX exported by Claude; mesh,
IDs and areas match the brief: walkable 45.42 + cap 6.48 = ledge 51.9 m2). Modeller brief B02t
https://claude.ai/code/artifact/95f7af8a-f484-4d9e-80ce-2a0f50ece086. Plan for markup helpers
(LEVEL_, AXIS_, anchors): PR #60 (HARNESS_PLAN §14, backlog MH1-MH3), after the terrace.
#61 terrace PR B merged (3 Codex rounds, findings fixed with regressions): the extractor reads a terrace
parapet (two section shapes, the lower = the floor below; walkable + cap cover the ledge in plan without
overlap; the parapet inner face covers its line over the full height; anything else on a ledge is a
`ledge-structure` question) into spec v0.4; bench `bench-b02t-terrace` (etalon hand-made by the user);
pattern `terrace` proven on benchmark (user). Harness rule (user): an etalon never comes from the engine.
#62 merged, #57 closed: non-manifold vertices fail the mesh check. User rule 2026-10-10: every slab
(roof in a parapet, terrace) is inset — hole at the level + plate at level + 5 mm, outline the hole
grown 20 mm as in the etalons; the user remade B01 (inset roof) and B02t v2 (inset terrace); B02t
waits for the inset PR (engine + checker + extractor).
#63 merged (3 Codex rounds, findings fixed with regressions): the engine builds every slab (roof in a
parapet, each terrace part) as a plate 5 mm above its level, outline the hole + 20 mm, refusing
out-of-range or out-of-outline plates; the checker requires a paired hole + plate per slab the spec
implies and fails a solid slab inside a slab region; the extractor reads inset terrace plates (flat within
0.1 mm); pattern `roof-inset-plane` = "Inset slab", proven on B01 / B02 / B02t. B01 (user's inset v2),
B02, B02t all 8/8 etalon and engine model, two loops per slab. #60 merged: plan for markup helpers
(HARNESS_PLAN §14, backlog MH1-MH3). PSU275 delivery-v003 predates the inset rule (user: mark, do not touch).
Markup helpers: #68 merged (MH1 — pattern `markup-helpers`, level helper name rule, the Blender route proven on a
hand-made Blender B01 etalon 8/8); #69 merged (MH2 — LEVEL_ helpers generated from Revit Levels and the roof
covering through the object.json `revit_levels` table; KPP1 Revit vs FBX levels 0 / 0 / 0.3 mm, match).
Intake: #70 merged (plan, HARNESS_PLAN §15, approved), #71 merged (IN1 — formats, `dt intake check`, skill
procedure; 3 Codex rounds). #72 merged (K01: KPP1 material IDs from UDIM tiles via jobs/KPP1/materials.json,
geometry thresholds, first run 5/8 pass; open items in benchmark/bench-k01-kpp1/README.md).
#73 merged (3 Codex rounds): colleague case alina-bld as a lesson (HARNESS_PLAN §16): pattern
`facade-decor-inset` (draft; 0.10 m threshold inclusive, split pieces merged with seams <= plate_gap_m x 12),
decor benchmark K02 = real facade fragment `bench-k02-decor-fragment` (brief + `decor-catalog.json`; the user
cuts `source.max` and makes `etalon.max`), synthetic B03 decor deferred, old B03 attachments -> B04;
`pipeline_gate` (pre-commit + Claude PreToolUse: `Pipeline status` above draft needs pipeline/spec.json,
spec.report.json, check.json; new job scripts name an engine gap EG1-EG4); OD1 opening depth 0.4 in backlog.
#74 merged (3 Codex rounds): spec v0.5 `decor` block and extractor (`src/dt_ai/spec/decor.py`): wall decor
as boxes (band / strip / panel), free-standing columns on a level, split pieces merged up to 0.06 m seams,
<= 0.10 m texture; > 0.8 m = attachment candidates (EG2, report only); questions one per type. B01/B02/B02t
unchanged 8/8; K01: 1 decor strip, 6 attachment-candidate types.
#75 merged (3 Codex rounds): the engine builds facade decor in its own mesh (body never cut; 0.02 m inset,
5 mm off openings, run-in meetings: horizontal main over vertical, of one rank the longer; convex corners with
the main element running on and keeping its back outside the wall; `decor-corner` when the other is higher);
`check_decor` reads the model back with the extractor and matches it to the spec one to one (replaced the
first checker). Post-merge on main: B01 / B02 / B02t 9/9 etalon and model.
#76 merged (3 Codex rounds): OD1 - opening depth default 0.4; a source with no depth (no reveal, flush plane,
glass only, Revit host thickness) takes it, listed in the report as depth by default, never 0; the glass
position is never a depth. K01: `decor_tol_m`; `check_decor` on a real building (attachments are no decor);
decor ids by material - metal 16-20 or 26-30 (K01 id 17 = metal bracket, confirmed by the user). Post-merge
on main: B01 / B02 / B02t 9/9 etalon and model; K01 31 questions, decor passes, known engine stop.
#76 was merged by a parallel session without the user's command and without the agreed round 4 (procedure
violation, `docs/cases.md`).
#78 merged (5 Codex rounds; rounds 4-5 over the 3-round limit, user 2026-10-12): `check_decor` without the
invented `STRAY_EMBED_MAX_M`. An unlisted box set into the body counts as decor-like when, in every storey
band it enters by more than `weld_m`, its own plan geometry outside the body is one piece. Pieces join within
`weld_m` by their real distance, and nothing is filled. A box through the building is an attachment. Corner
run-ons, concave corners, recesses, holes, partial caps and welded halves are covered by regressions. B01 /
B02 / B02t 9/9; K01 spec and etalon self check unchanged (31 questions, 6/9).
#79 merged (3 Codex rounds): `pipeline_gate` fails closed. A git error or a missing git exits 2, an unresolved
merge blocks, and replace refs are ignored. The pre-commit blocks when the root lookup fails, and blocks jobs/
when the gate is missing. Test failures on this machine traced to their causes: `%TEMP%\pytest-of-artsafro` is
inaccessible (left as is, user 2026-10-12: run pytest with a short `--basetemp`), and a long basetemp passes
MAX_PATH (git `core.longpaths` in the gate tests; the KPP1 launcher test skips past the Win32 cwd limit).
Not covered: a compromised environment, for example a fake `py` on PATH (user 2026-10-12). The installed
`.git/hooks/pre-commit` was updated to the #79 version (the old one is backed up in
`C:/x/pre-commit.backup-2026-10-12b`). It blocks a built status without `pipeline/` on this machine.
#77 merged (3 Codex rounds): the materials table reads `slots` {slot: id} (1-based dump slots; an unlisted slot
is 0) and `glass_slots` + `glass_id`. Glass triangles move into `<name>_glass` for the extractor, and source
polygon sizes stay with their triangles. On the OBJ03 source FBX with the run table, 30 296 glass triangles get
id 12 and the other 387 034 get 0. Finish slots are not mapped to ids (user 2026-10-13): the engine sets the
output ids by group, and the material of a slot is asked only when a decision needs it. B01 / B02 / B02t 9/9;
K01 unchanged.
#80 merged (3 Codex rounds): rule 5 for OBJ03 (user 2026-10-12): `dt spec extract --collect-stops` makes one
pass and substitutes nothing. Each storey's contour is read on its own, and a stopped storey is left out. Every
stop goes to `<spec>.report.json` → `stops` with its stage (levels and body / contour / openings / roof /
plates / decor). No spec is written and the exit code is 3. A report with stops backs no job status above
draft (`pipeline_gate`). Without the flag nothing changed; B01 / B02 / B02t / K01 are identical.
#81 merged (3 Codex rounds): rules 3 and 4 for OBJ03 (user 2026-10-12).
- Rule 3: a storey's contour is its mid-storey section. A change only in the 0.3 m under the next level is the
  slab edge, not the contour; in a storey up to 0.6 m that band ends at mid storey. The report keeps
  `slab_edge`, and an open band is a `slab-edge-open` question. A change inside the wall band still asks for
  `contour_at_m`.
- Rule 4, spec v0.6: `roof.parapet_thickness_m` is measured as a mitred inset of the top contour at mid parapet
  height (facade relief left out). When it cannot be read, `parapet_thickness_default_m` applies and the report
  marks it; nothing is asked. The engine takes the spec thickness first, and a terrace parapet takes the same
  thickness (one per building, user 2026-10-13). Measuring terrace parapets is issue #82.
- B01 / B02 / B02t read 0.3 and K01 reads 0.555, the same as their build values. Models and checks are
  identical to main; the specs gain only version 0.6 and the thickness.
#64 merged (3 Codex rounds): `plate_gap_m` / `plate_overlap_m` are building parameters in the spec (defaults
0.005 / 0.02); the engine builds from them, the extractor reads every plate (flat, even overlap over one
hole; disagreement > 0.5 mm or an unreadable plate is a `plate-params` question), the checker compares each
plate within `plate_tol_m` 0.5 mm. B01 / B02 / B02t read 5 / 20 mm on every slab, 8/8.
#65 merged: inset slabs around shafts (a shaft's foot = an inner outline of the hole, the plate's hole
around it an inner outline of the plate; one to one per outline). #66 merged: ledges for `ledge-structure`
are taken between final contours minus the raw section shape (no false question from door recesses or
relief; found on KPP1). #67 merged (3 Codex rounds): KPP1 v007 (option a, flat inset roof around the
vent shaft) built by the job scripts — every face below 7.5 m keeps the v005 geometry, finish and UVs;
leaks 0, T-junctions 17 (as v005), overlap 0; SINTEZ as v005; spec v030 0 questions, comparison v031 with
Revit match (`jobs/KPP1/STATE.md`). User acceptance of v007 open (v005 stays the accepted ~90 %). K01 as a
full benchmark needs a material-ID scheme for KPP1 and a `geometry` block.
Human tickets: #2 (move `Unreal/`), #4 (window library file). Decisions: ADR 0001 (`docs/adr/`); user decisions
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

0. User: decisions on the choices page (C7, C8, C10, C25); KPP1 v007 acceptance; K01 open items (profile
   for openings, decor IDs, asphalt, the engine's parapet strip); cut K02 `source.max` + make `etalon.max`.
   Claude: case-alina-bld with the user's rules 1-5 (docs/HANDOFF.md); decor PR 4
   (K02 run, once the user gives the fragment); intake IN2-IN8; MH3; the
   modelling blockers (attachments, finishes, H10); issue #56; extractor follow-ups
   #21-#24, #28, #34, #37, #45 when they block a benchmark (one writing agent, one branch per ticket,
   Codex review per PR).
1. Claude: PSU275 — racks, transformer massing, window frame density; check `clean_loops.py`
   and the unwelded-roof rule on KPP1 before generalising (case `PSU275_VPM_NPM_DELIVERY_V003.md`).
2. Claude: KPP1 — real `run_all.sh` run on a new version to confirm the merged runner;
   deferred delivery items when the user unblocks them.
3. Codex (when back): Q6 (encode C20), H1 (Codex hook), H2 (SketchUp venv), Q3 (one validator).
4. Claude + Codex: Q7 — RGB + `_o_` conversion of GLB NPM atlases, 128 px NPM placeholders.
5. Antigravity: H4 — translate `docs/agr/` core documents.

# Backlog — unsolved decisions and missing stages

Each item names its default owner (`ROLES.md`). Take one item per branch; move finished
items out of this file in the same merge. `C<N>` = conflict N in `docs/domain/conflicts.md`.

## Decisions for the user (block production)

- **C1–C34** — open source conflicts and 5 dubious rules (`docs/domain/conflicts.md`).
  Decided on 2026-10-07 [D010, D011, D012, D013, D014, D015, D016, D017, D018, D019, D020, D021]: C1, C2, C3, C5, C6, C12, C13, C14, C19, C20, C21, C26. Owner: Claude
  prepares a one-page choice per conflict; the user decides; the decision goes to `docs/domain/`
  and the YAML `conflicts:` block (status `noted`).
- **G1** — GLOSSARY: expansion of "AGR", Master scene, Source album, Current album,
  Production asset. Owner: user + Claude.

## Production stages (default owner Claude; code parts handed to Codex)

- **P1** Run `analyze-architectural-source` on a real source (first: an Obr22 accepted FBX,
  read-only) and on the Revit sources in `data/sources/revit/`.
- **P2** Master building layer: schema and one real object.
- **P3** Windows / stained glass / doors: accept a general procedure (REVIT-OPENINGS pilot
  not accepted).
- **P4** Roof, decor, exterior equipment.
- **P5** UCX generation (VPM) + validator V010.
- **P6** Lights FBX (VPM).
- **P7** Coordinates: MSK-77, zero mark, pivot (reg p.32–33) — export experiment in
  Max and Blender; validator V013/V014.
- **P8** GeoJSON generation from object data.
- **P9** Ground: accept mesh shape (v008), height smoothing parameters (dubious D2).
- **P10** MAF (GroundEl) pipeline from the 3ds Max scripts.
- **P11** Flora: SpeedTree → FBX readback (geometry, scale, textures).
- **P12** (Codex) Generalize BODY extraction to multi-height massing: `exterior.py` supports one
  perimeter and one height. Working job version for PSU275: `jobs/PSU275/scripts/`
  `massing_profiles.py` (union of rectangular masses → per-plane profiles), `sample_wall_masks.py`
  (ray-measured openings), `massing_surface.py` (cut lines stop at holes, corner cuts exchanged,
  T-free quads), `drop_step_bottom_rims.py` (shell post-step). Move into `src/dt_ai/geometry/`
  with tests; keep the PSU275 outputs as regression.

## Engine gaps — mixed mode (user decision 2026-10-11 [D050], `docs/HARNESS_PLAN.md` §16)

The engine builds what it can (body, openings, floor steps, terraces, inset slabs). Job scripts do only
the gaps listed here; a job script names its gap in its header (`Engine gap: EG<n>`, checked by
`pipeline_gate` on new scripts); anything not listed is asked, not scripted. A gap leaves this list when
the engine covers it.

- **EG1** Facade decor (pattern `facade-decor-inset`): PR 2 spec block `decor` + extractor, with a test of
  merging a split element (same cross-section, one axis, gaps <= `plate_gap_m` x N, N = 12: 0.06 m, user 2026-10-12 [D054]) and of the
  inclusive 0.10 m threshold; PR 3 engine + (meeting by run-in and at building corners, user 2026-10-12 [D059]) +
  checker (no decor overlap with openings, no body edge cut, ids 26-30, 10 cm threshold); PR 4 run on
  `bench-k02-decor-fragment` (real fragment: `source.max` + `etalon.max` by the user). Later regression: the
  synthetic `bench-b03-decor` (free-standing column).
- **EG2** Attachments over 0.8 m (balconies, canopies, bays; slab, railing, soffit) — pattern to be written; the
  decor extractor already lists them as `decor.attachment_candidates` (user 2026-10-12 [D057]).
- **EG3** `mid` window sashes / detailed windows from the opening plane.
- **EG4** UV, atlas and delivery package = **H10**.
- **EG5** Pattern primitive-first, `from_source` (2026-10-14): (a) instances by translation only - a copy turned
  90/180 degrees is a type of its own (OBJ03 v009: 1 328 piers -> 798 types); add rotation to the type key and the
  modules export; (b) regenerate `npm/` from an edited `modules/modules.blend` (now both come from one build).
  Owner Codex.

## Markup helpers (after the terrace; owner Claude, code parts Codex)

Plan: `docs/HARNESS_PLAN.md` §14 (user decision 2026-10-10 [D044]). One PR each, in this order, each with
the pattern `markup-helpers` (written or extended) and its test.

- **MH1b** (MH1 done: Blender route closed on the Blender B01 etalon, pattern `markup-helpers`) — later:
  a script that places `LEVEL_*` Empties in a Blender scene from `spec.json`.
- **MH3** Axes and anchors: generate `AXIS_<name>` (line) from Revit `Grids` through TwinPack; the
  extractor reads the `AXIS_<letter>` / `AXIS_<digit>` grid and binds openings to axes, not absolute
  coordinates; named anchors `TERRACE_<n>`, `ENTRANCE_<name>` as hints to patterns (smaller gray zone).

## Intake — "study the sources" (after the plan is approved; owner Claude, code parts Codex)

Plan: `docs/HARNESS_PLAN.md` §15 (user decision 2026-10-11 [D049]). One PR each, extending the skill
`analyze-architectural-source` (no parallel skill); intake reads only, never changes or exports sources.

- **IN2** Intake on the existing adapters (FBX mesh dump, Revit twin): inventory, picture, contradictions,
  implementation proposal. Test: K01 KPP1 (Revit + FBX).
- **IN3** PDF adapter: text, vector dimensions, page rasters. Test: one real PDF.
- **IN4** Images: agent reading, scale anchors (a user-confirmed dimension or a brick / panel module);
  nothing measured, no spec and no engine run before an anchor is confirmed. Test: B02 from Max screenshots.
- **IN5** DWG through the AutoCAD MCP. Test: one real facade DWG.
- **IN6** SketchUp adapter on intake (after H2). Test: one real SKP.
- **IN7** 3ds Max through the MCP, read only. Test: one real MAX.
- **IN8** Acceptance cases: K01 full (Revit + FBX + PDF) matches the existing specs within the K01
  tolerances, Revit / mesh contradictions listed; B02 images give an estimated spec-draft and the anchor
  question.

## QA (default owner Codex)

- **Q1** Validator: NPM embedded atlas pixel rules (PNG inside FBX), units.
- **Q2** Texel density V009.
- **Q3** Merge `src/dt_ai/validate/bundle.py` (C001–C004) and `src/twinqa` (V001–V017)
  into one validator and one report format.
- **Q4** Clearance hits: classify embed vs defect automatically where possible.
- **Q5** SINTEZ AGR Checker integration (AGR INT-001): coverage map vs the regulation,
  run in an isolated Blender 4.4, import findings.

- **Q6** Encode conflict #20 (decided 2026-10-07 [D019]): `_NNN` address index only with more than one
  OKS; GeoJSON field types/required/decimals as the checker table and lengths from reg p.53-55;
  alpha-plane offset 0.003-0.01 m; Light FBX rules (point/spot, `_Omni`/`_Spot`, numbering).
- **Q7** Convert accepted GLB RGBA NPM atlases to RGB + `_o_` opacity (conflict #21); fix the 3ds Max
  placeholder tool to write 128x128 for NPM (conflict #5). Owner: Claude (DCC), Codex (tool).

## Unreal and IFC

- **U1** Unreal import rules (UE 5.5/5.7): scale, pivots, materials, collisions, LODs.
- **U2** Interactive experience project in `Unreal/`.
- **U3** IFC export route.

## Reuse proposals (rule of three, `docs/agents/WORKFLOW.md`; proposals only, nothing created)

Added by `/handover` (procedures repeated in a session) and `/reuse-scan` (repeats across jobs). Line:
`- **R<n>** proposal <date>, <branch> - <CLI command | skill | pattern | src/ module>: <what>; seen <N> times;
effort <S/M/L>`. The user or the owner turns one into a task or drops it.

- **R1** proposal 2026-10-15, harness/agent-ready-prd - CLI command: set a board card's Status and Agent for an
  issue number (find the project item by graphql, `gh project item-edit` twice, option ids from
  `docs/agents/issue-tracker.md`); seen 18 times (17 cards + 1 move to In progress) as an ad-hoc shell loop; effort S
- **R2** proposal 2026-10-15, harness/agent-ready-prd - CLI command: publish a set of tickets from one definition
  file (title, labels, owner, blocked-by keys, body sections) in dependency order with native blocked-by links,
  sub-issue links to a parent and board cards; seen 1 run of 16 tickets through a scratchpad script plus 3 body
  edits by a second script; effort M
- **R3** proposal 2026-10-15, harness/evals-runner - CLI command: the post-merge state update - temporary detached
  worktree from `origin/main`, replace given `PROJECT_STATE.md` sections, run the state and decision tests, commit
  `State: #<PR> merged ...`, push to `main`, remove the worktree; seen 3 times (#137, #139, #140); effort S
- **R4** proposal 2026-10-15, harness/evals-runner - CLI command or skill: one Codex review round of a PR - prompt
  from the issue text, `REVIEW_CHECKLIST.md` questions, the diff range and the review class; `codex exec -s read-only`;
  the findings table posted as a PR comment with the fix commit; seen 5 rounds in this session (#137 x1, #139 x1,
  #140 x3); effort M

## Harness and organization (default owner Codex)

- **H1** Validate the Codex PreToolUse hook (`.codex/hooks.json` → guard.py): payload
  fields, "ask" support. Record the result in `CAPABILITIES.md`.
- **H2** SketchUp MCP route: own venv for `adapters/sketchup/` (the old one stayed in the
  former AGR folder) and re-verify.
- **H3** `revit-twin` MCP: its source was on unmerged DT branch `feature/revit-workflow`
  (in `data/archive/DigitalTwinProject-Claude-all.bundle`); recover or drop the user
  registration that points at a removed worktree.
- **H4** Translate `docs/agr/` (brief, rules, ADRs, cases, case template) and Russian
  comments/READMEs in `technical_library/`, `tools/`, `jobs/` to English. Owner: Antigravity.
- **H5** CI: GitHub Actions failed with `startup_failure` (billing) in the old AGR repo.
  Decide hosted CI vs a local pre-push check.
- **H6** Herdr: re-point the Herdr workspace and plugin to this repo; verify the HUD.
- **H7** Tidy `tools/` by `docs/agents/NAMING.md`: stage subfolders, `<verb>_<subject>` names
  without versions or object codes (`git mv`, update `CAPABILITIES.md`, skills, tests); move
  one-off job scripts into `jobs/<JOB>/`; delete nothing that an accepted case cites.
- **H10** Shared VPM/NPM pipeline from `jobs/KPP1/scripts` and `jobs/PSU275/scripts` (duplicated
  `export_npm`, `make_npm_atlas`, `package_vpm`, `vpm_ucx`, `qa_master*`, `run_all`) into
  `tools/<stage>/`, parameters in `jobs/<id>/object.json`; regression: both objects give the same
  outputs and QA. Then rename job folders to object ids and tag `pipeline/vpm-npm-v1`.
- **H8** Machine-specific MCP paths in `.codex/config.toml` / `.agents/mcp_config.json`:
  document the install steps so another machine can reproduce them.
- **H9** Git LFS budget of the GitHub account is exhausted (push rejected 2026-10-06):
  raise the budget, move binaries to another store, or drop LFS patterns. Heavy data: legacy job outputs and Revit sources live in `jobs/*/outputs` and
  `data/` (local only). Decide backup (external disk / NAS / LFS) before deleting the old
  folders' last copies.
- **H11** Former projects, moved here on 2026-10-06: DigitalTwinProject (Claude,
  `C:\Users\artsafro\DigitalTwinProject`, archive `data/archive/DigitalTwinProject-Claude-all.bundle`) and
  AGR_Project (Codex, `C:\Users\artsafro\.AGR_Project`, archives `AGR_Project-all.bundle`,
  `AGR_Project-uncommitted-2026-10-06.zip`). The user plans to delete both folders; before that check the
  user-level configs that still point at them (H2, H3) and re-create the bundles if work continued there
  after 2026-10-06 23:24. Dropped on purpose: AGR process history, the Cursor verifier, the KPP1-VPM task,
  Codex `agent_monitor` (kept in the uncommitted-files archive).
- **H12** Branches not merged on purpose (user, 2026-10-07 [D006]): `claude/npm-models-school-kpp-ec9ced`
  (BUTOVSKAYA-NPM, work in progress), `claude/modest-ptolemy-684fb7` and `feature/kpp1-ground` (TEC26
  ground, adds `ezdxf`). Owner: user decides when to resume.
- **H13** (Claude) Rerun the merged `fix/export-safety` scripts on real data: KPP1 full `run_all.sh` on a new
  version, PSU275 v003/v004 re-assembly with `assemble_body_roof.py`; so far only synthetic tests pass.

# Backlog — unsolved decisions and missing stages

Each item names its default owner (`ROLES.md`). Take one item per branch; move finished
items out of this file in the same merge. `C<N>` = conflict N in `docs/domain/conflicts.md`.

## Decisions for the user (block production)

- **C1–C34** — open source conflicts and 5 dubious rules (`docs/domain/conflicts.md`).
  Decided on 2026-10-07: C1, C2, C3, C5, C6, C12, C13, C14, C19, C20, C21, C26. Owner: Claude
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

## Markup helpers (after the terrace; owner Claude, code parts Codex)

Plan: `docs/HARNESS_PLAN.md` §14 (user decision 2026-10-10). One PR each, in this order, each with
the pattern `markup-helpers` (written or extended) and its test.

- **MH1** Blender route: Empty → FBX Null. Record in the pattern: export `Up Z` or read `UpAxis`
  from the FBX; `Unit Scale 1.0` + `Apply Scalings: FBX Units Scale`; `.001` suffixes. Name regex
  in the pattern; a checker flags suffixes (`.001`, `001`, spaces) and duplicates. Test: rebuild
  B01 by hand in Blender, run the chain, 8/8 closes the route. Later: a script that places
  `LEVEL_*` Empties in a Blender scene from `spec.json`.
- **MH2** Revit route, levels: generate `LEVEL_<name>` (elevation) from `Levels` through TwinPack.
  Test: on KPP1 the Revit helpers match the ones taken from mesh v022 within the level tolerance.
- **MH3** Axes and anchors: generate `AXIS_<name>` (line) from Revit `Grids` through TwinPack; the
  extractor reads the `AXIS_<letter>` / `AXIS_<digit>` grid and binds openings to axes, not absolute
  coordinates; named anchors `TERRACE_<n>`, `ENTRANCE_<name>` as hints to patterns (smaller gray zone).

## QA (default owner Codex)

- **Q1** Validator: NPM embedded atlas pixel rules (PNG inside FBX), units.
- **Q2** Texel density V009.
- **Q3** Merge `src/dt_ai/validate/bundle.py` (C001–C004) and `src/twinqa` (V001–V017)
  into one validator and one report format.
- **Q4** Clearance hits: classify embed vs defect automatically where possible.
- **Q5** SINTEZ AGR Checker integration (AGR INT-001): coverage map vs the regulation,
  run in an isolated Blender 4.4, import findings.

- **Q6** Encode conflict #20 (decided 2026-10-07): `_NNN` address index only with more than one
  OKS; GeoJSON field types/required/decimals as the checker table and lengths from reg p.53-55;
  alpha-plane offset 0.003-0.01 m; Light FBX rules (point/spot, `_Omni`/`_Spot`, numbering).
- **Q7** Convert accepted GLB RGBA NPM atlases to RGB + `_o_` opacity (conflict #21); fix the 3ds Max
  placeholder tool to write 128x128 for NPM (conflict #5). Owner: Claude (DCC), Codex (tool).

## Unreal and IFC

- **U1** Unreal import rules (UE 5.5/5.7): scale, pivots, materials, collisions, LODs.
- **U2** Interactive experience project in `Unreal/`.
- **U3** IFC export route.

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

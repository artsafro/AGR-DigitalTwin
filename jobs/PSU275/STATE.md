# PSU275 — main building No 1

Sources, decisions and derived values: `docs/sources/psu275.md`. Profile: NPM + VPM.

## Done (2026-10-07)

- S1 PDF, S2 Revit (detached 2025 copy `…_modified_1644`), S3 FBX, S4 PPTX inspected read-only.
- 0.000 = 169.65; first floor = 0.000 … +13.060; finishes from the S4 schedule.
- Chimney: take from S3 (user).
- `scripts/clip_floor1.py` → `outputs/psu275_floor1_src_v001.blend` (local): 254 meshes,
  3.54 M tris, band −0.150 … +13.060, context dropped.
- S3 ↔ Revit fit from facade planes (`scripts/facade_planes.py`), residual ≤ 0.02 m:
  `FBX = (Y_rvt + 142.55, 204.86 − X_rvt, Z)` (−90° rotation, no mirror).
  Outer faces: main 94.24 × 108.56 m, annex 18.66 × 56.58 m (L-shaped footprint).

- BODY (exterior surface, pre-Shell) v002: `scripts/build_floor1_grid.py` → `outputs/grid-v003`
  (54 openings ray-measured on the S3 opaque wall layer, edges snapped to S3 vertices,
  stacked curtain strips merged, edges consolidated within 12 mm, max move 2.3 mm) →
  `tools/run_exterior.py --config jobs/PSU275/exterior-adapter.json` → `outputs/exterior-v002`.
  2072 quads, 6 facade runs, height 13.060, min edge 40 mm. Checks pass: geometry QA,
  NPZ readback, Blender readback (max error 2.3e-6 m), `check_exterior_surface.py`
  (no inward faces, no opening fill, no overlap, profiles exact). Preview `preview_*.png`.
- Frame: local = Revit − (37.17, 54.00) m, Z = 0.000 (= 169.65). Earlier tries kept as
  evidence: grid-v001/v002, exterior-v001 (float32 readback 8.6e-6 m at S3 coords, 2 mm faces).

- Shell v001 (C23 decided by the user: Shell 0.4 m inward, no inner faces):
  `body-shell-adapter.json` → `outputs/shell-v001/BODY_SHELL.blend`, 3260 quads, min edge 40 mm.
  Checks pass: geometry, JSON readback, Blender readback (max error 1.9e-6 m). Visual review open.

- Approach changed (user, 2026-10-07): no typical floor in an industrial building → whole
  building as massing → one stitched surface with openings → one Shell. First-floor band
  results above stay as intermediate evidence.
- Full-height source: `outputs/psu275_full_src_v001.blend` (713 meshes, z −0.15…66.20).
  Masses: `masses.json` (8 boxes from `wall_planes_v001.json` + `heightmap_v001`).
- `massing-profiles-v002` (15 profiles, 23 040 m²) → `wall-masks-v001` → `massing-surface-v004`:
  130 openings, 2537 quads, 0 T-junctions, 20 corner lines (5 iterations), edges consolidated
  ≤ 12 mm (max move 2.3 mm), corner clearance 0.41 m (20 trims). Audit passes.
- Shell `body-shell-full-adapter.json` → `shell-full-v001` (3701 quads; 10 coplanar overlaps at
  junctions) → `drop_step_bottom_rims.py` → **`shell-full-v002/BODY_SHELL.blend`**: 3668 quads,
  33 step-bottom rims removed. Checks pass: geometry, JSON readback, Blender readback (3e-6 m).

- Roofs and parapet wells: `scripts/roof_wells.py` → `outputs/roof-wells-v001` (7 regions,
  211 quads: 127 roof, 61 parapet inner, 23 well faces closing the step-face gaps). Flat roofs
  at the roof level (hall 38.32, annex 13.56, boiler 62.20, inserts/superstructure at top);
  slopes not modelled. Audit alone passes; merged with BODY: 0 overlaps, 0 crossings.
- `scripts/assemble_body_roof.py` → **`outputs/building-v002/PSU275_BODY_ROOF.blend`**
  (BODY 3668 quads + ROOF 211 quads), Blender readback in `readback.json`.

- Portals: S3 faces outside the masses (`scripts/outside_clusters.py` → `outside_faces_v002.npz`),
  source check by `scripts/render_region.py`: portals are U/L frames around recessed doors or
  floating canopies (doors stay in BODY openings). `scripts/portal_frames.py` → `portals-v003`:
  15 portals (11 frames, 4 canopies; vestibule = 2 frames), front silhouette on the measured
  outer plane extruded to the facade (depth 1.60–1.68 m), coords consolidated ≤ 12 mm,
  185 quads, min edge 0.49 m. Audit alone passes; with BODY+ROOF: 0 overlaps, 0 crossings.
  (Trying portals as masses was dropped: it removed the recessed doors.)
- **`outputs/building-v003/PSU275_BODY_ROOF_PORTALS.blend`**: BODY 3668 + ROOF 211 + PORTALS 185 quads.

- Opening merge fix: chained merges had produced three ~31 m "openings" mostly over wall;
  merges now need ≥ 85 % void (`massing-surface-v006`: 152 openings, 2809 quads, 0 T) →
  `shell-full-v003` → `shell-full-v004` (4048 quads, 31 step rims dropped; all checks pass;
  re-audited with ROOF + PORTALS: 0 overlaps/crossings).
- Opening fills (user: both variants): `scripts/sample_openings.py` (first-hit class + depth,
  2.5 cm rays) → `opening-samples-v002` → `scripts/opening_fills.py` → `fills-v003`:
  116 windows, 35 doors/gates (2 sectional gates 5.0 × 5.8 classed "other" → door), 1 void.
  NPM: 152 planes at the frame depth, 10 mm reveal embed. VPM: frame/leaf minus 2446 panes,
  glass 2–4 cm deeper with pane sides, 23 144 quads, min edge 15 mm. Window-contract audit with
  BODY passes for both (embeds documented, 0 unapproved crossings, 0 T, 0 duplicates).
- **`building-v004-npm/PSU275_NPM.blend`** and **`building-v004-vpm/PSU275_VPM.blend`**: BODY +
  ROOF + PORTALS + WINDOWS_NPM / WINDOWS_VPM with preview materials (glass, frame RAL 9016,
  door RAL 7004, louvre, void).

## Open

- Visual/user review of `shell-full-v002` against S4 facades; louvres counted as openings.
- Roof slopes (hall 38.32…39.35), skylight lantern details, roof equipment not modelled.
- External steel stairs/ladders (5 clusters) → exterior equipment from S3.
- Opening IDs are S3 measurement IDs, not Revit IDs. Minimum rim edge 10 mm.
- Generalization of the massing builder → backlog P12 (Codex).

## Next

VPM cuts (< 4 × 4 m), UV/atlases and final materials from the S4 schedule; NPM atlas; exterior stairs, chimney and site parts from S3; FBX export + readback.


## Export safety trial (Codex, 2026-10-07)

User authorized trying fixes in a new branch; no push or merge to main. Task branch:
fix/export-safety. Base main ffa67e38, with frozen PSU275 6d67e8b and KPP1 41669a3
as local dependencies. Lead owns assembly and contract; bounded KPP1 executor owns
its runner/export safety; independent verifier reviews actual diff and evidence.

Acceptance: new output paths only; repeated runs preserve existing files; changed
finish specifications cannot reuse an obsolete NPM atlas; missing atlas regions
stop export; BODY and ROOF provenance survives save/reopen with unchanged geometry,
UV, materials and transforms. Real object comparison and visual/user acceptance
remain separate gates. Inputs and accepted outputs remain read-only; test outputs
live only under task-owned tmp/export-safety. Stop on provenance ambiguity, failed
required checks or source/output aliases; never weaken a check to pass.

Plan: preflight guards and scoped fixes, negative/happy-path regression checks,
isolated Blender save/reopen and object comparison where inputs exist, project
checks, independent review, task-owned commit and local handoff. No production
geometry redesign, standards changes or source asset cleanup is included.

Status: technical safety trial verified; visual/user delivery gates remain open. PROJECT_STATE on main is not
edited by this task. Evidence and remaining gates will be recorded below.

### Safety trial verification

Implementation and technical safety checks passed in the task branch. Compact
cross-job evidence: `export-safety-evidence.json`. All 349 project tests passed;
profiles (3) and schemas (8) passed. Real PSU275 assembly saved/reopened with BODY
and ROOF provenance preserved; mesh/UV/material/transform/property snapshots match
the prior building-v002. Inputs were rehashed unchanged. Imported standalone
Blender Text requires fake users; the initial failed attempt is retained locally.

No production geometry changed. Task-owned native files and detailed logs remain
under tmp/export-safety; previous production outputs and failed attempts retained.
Visual/user acceptance remains open. No push or merge to main. Next action:
review the local changes and, if requested, have the production owner inspect the
new versions before publication. Direct KPP1 stage-launcher overwrite compatibility
is retained; the new-version guarantee applies to run_all.

### Merge note (Claude, 2026-10-07)

Merged with the later portals/fills work: `assemble_body_roof.py` now takes
`<BODY.blend> <out.blend> <readback.json> <mesh.json>...` (several meshes, preview
materials from `material_names`) and keeps every export-safety check per mesh; each added
mesh stores `<name>_PROVENANCE.json`. Synthetic Blender save/reopen test passed; the real
v003/v004 assemblies were not rerun with the merged script.

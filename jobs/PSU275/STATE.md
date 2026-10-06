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

## Open

- Visual/user review of `shell-full-v002` against S4 facades; louvres counted as openings.
- Roof slopes (hall 38.32…39.35), skylight lantern details, roof equipment not modelled.
- Portals and vestibules (1.2–1.7 m out of the facade) not modelled yet.
- Opening IDs are S3 measurement IDs, not Revit IDs. Minimum rim edge 10 mm.
- Generalization of the massing builder → backlog P12 (Codex).

## Next

Portals and vestibules; then windows/doors into openings, VPM cuts/UV, materials.

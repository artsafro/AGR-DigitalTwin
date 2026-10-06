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

## Open

- User review of BODY v002 openings against the S4 facades (manual gate).
- Opening IDs are S3 measurement IDs, not Revit door/window IDs.
- Plinth, portals and entrance canopies stand out of the panel plane; not in BODY.

## Next

Windows/doors into the 54 openings (`tools/build_shell_windows.py`), then VPM cuts/UV.

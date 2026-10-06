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

## Open

- BODY route: `exterior.py` needs an occupancy grid (`body-grid.npz`) + opening bounds.

## Next

Split S3 openings (glass, doors, gates) into per-opening bounds, rasterize the L-shaped
footprint 0.000 … +13.060 into `body-grid.npz`, run `extract_exterior`, read back.

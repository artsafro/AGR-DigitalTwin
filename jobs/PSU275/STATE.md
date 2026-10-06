# PSU275 — main building No 1

Sources, decisions and derived values: `docs/sources/psu275.md`. Profile: NPM + VPM.

## Done (2026-10-07)

- S1 PDF, S2 Revit (detached 2025 copy `…_modified_1644`), S3 FBX, S4 PPTX inspected read-only.
- 0.000 = 169.65; first floor = 0.000 … +13.060; finishes from the S4 schedule.

## Open

- Chimney +99 (S4) vs 120 m (S3).
- Fit S3 → Revit transform on grid intersections (S3 is offset ≈ +140, +109 m).

## Next

Clip the S3 main building to 0.000 … +13.060 in Blender 4.4 (5.1.2 crashes on S3), check
against Revit axes 108 × 93 m and S4 marks, then build BODY (`src/dt_ai/geometry/exterior.py`).

# bench-k01-kpp1

First real building: object `tec26-kpp1` (`jobs/REGISTRY.md`, `jobs/KPP1/`), 27.66 x 11.66 m, levels 0 / 3.9 / 7.7 / 8.65.

Patterns: all patterns that pass B01-B03.

Checks (`npm_min`, starting thresholds, final values in `tolerances.json`): bounding box
±5 cm; level heights ±3 cm; floor area ±2 %; silhouette IoU ≥ 0.97 (4 sides + top); mesh
manifold, no n-gons, no overlapping faces; triangles within the profile budget; an opening
plane with ID in every spec opening; material IDs in their ranges (ADR 0001).

The etalon is KPP1 v005 finished to 100 % by hand (v005 is ~90 %; an etalon with defects teaches defects). Sources stay in the object's job; this folder links to them, it does not copy them. Spec comparison Revit vs mesh: issues #9-#11.

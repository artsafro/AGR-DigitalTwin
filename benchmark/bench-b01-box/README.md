# bench-b01-box

Box 10 x 10 m, 2 storeys, 2 windows, flat roof with a parapet.

Patterns: wall-from-contour, opening-plane, typical-floor-repeat, parapet.

Checks (`npm_min`, starting thresholds, final values in `tolerances.json`): bounding box
±5 cm; level heights ±3 cm; floor area ±2 %; silhouette IoU ≥ 0.97 (4 sides + top); mesh
manifold, no n-gons, no overlapping faces; triangles within the profile budget; an opening
plane with ID in every spec opening; material IDs in their ranges (ADR 0001).

Helpers: `LEVEL_L0`, `LEVEL_L1`, `LEVEL_roof`. Etalon: issue #12; spec: #13; checkers: #14.

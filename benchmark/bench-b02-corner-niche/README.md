# bench-b02-corner-niche

One corner that is not 90°, one niche given by contour points, roof on two levels.

Patterns: non-90-corner, contour-niche (plus the B01 patterns).

Checks (`npm_min`, starting thresholds, final values in `tolerances.json`): bounding box
±5 cm; level heights ±3 cm; floor area ±2 %; silhouette IoU ≥ 0.97 (4 sides + top); mesh
manifold, no n-gons, no overlapping faces; triangles within the profile budget; an opening
plane with ID in every spec opening; material IDs in their ranges (ADR 0001).

Etalon not made yet.

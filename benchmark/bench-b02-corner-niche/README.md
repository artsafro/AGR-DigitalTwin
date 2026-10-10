# bench-b02-corner-niche

One oblique wall (two 135° corners), one contour niche, roof on two levels: a one-storey block with
a terrace at 3.3 m and a two-storey block with a parapet over X 6-12.

Patterns: non-90-corner, contour-niche (plus the B01 patterns).

Brief (Claude Docs): https://claude.ai/code/artifact/e332aa9d-b0ae-4084-b70b-735eda67f741 — contour
points, windows in the niche and on the oblique wall, IDs as B01. Etalon files outside git in
`data/benchmark/bench-b02-corner-niche/`, hashes in `etalon.json`; `spec.json` extracted from it.
The roof covering is an inset plane 5 mm above the parapet inner faces' foot (6.605 m): a roof as a
separate element is normal (pattern `roof-inset-plane`): it sets no height, the parapet reads 0.6 m
from `LEVEL_roof`, and its outline with the parapet foot under it is the one allowed open joint.

Status 2026-10-10 (run-v003): spec equal to the brief (parapet 0.6), 0 questions; etalon against itself 8/8
(open loops: bottom ring, roof plane outline, parapet foot — all allowed). The
engine builds floor steps (pattern floor-step) but not oblique walls yet: the run stops at the model
step until it does.

Run and checks: as `benchmark/bench-b01-box/README.md`, with this folder's `object.json` and
`tolerances.json`.

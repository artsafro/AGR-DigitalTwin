# Walls from a level contour (`wall-from-contour`)

Status: draft. Source: `docs/HARNESS_PLAN.md` §3–§4, §7; terms Level contour, Spec in `GLOSSARY.md`.

## Signs in the spec

- `floors[].contour`: closed counter-clockwise points `[x, y]`, or `[x, y, {"r": r}]` for a rounded
  corner; wall N runs from point N to point N + 1. Openings refer to walls by this index.
- The contour is the wall over the full storey height; anything shorter is in the object's
  `questions.md`, never in the contour.

## How to build

- One wall per contour edge, from the level elevation to the next level (engine function to come
  with `src/dt_ai/geometry/from_spec.py`; until then this is the rule, not a call).
- Rounded corner: an arc of radius `r` tangent to both walls; kinks over 5° are kept as given.

## Profiles

- `npm_min`: planar walls, openings as recessed planes (`opening-plane`).
- `mid`: same walls; detail goes to openings and attachments, not to the contour.

## Check

- Benchmark checkers (§5): level heights ±3 cm, floor area ±2 %, bounding box ±5 cm, silhouette.

## Traps

- **Plinth at the bottom of a storey (or a cornice at its top) is the typical case for
  `contour_at_m`.** The extractor stops with "no section shape is both at the two storey ends and
  the tallest" and lists the shapes with their heights. Do not wait: propose to the user
  `contour_at_m.<level>` = a height inside the plain wall band (above the plinth, below the
  windows) taken from that list. The plinth then becomes a question, as it should.
- Never give `contour_at_m` inside a window band: the contour then follows the window notches and
  breaks into many short walls. Pick a band without openings.
- A door from the floor or any wall break up to 8 m is an opening, not an open storey end.
- A door recess (not a through hole) cut by the contour height is not a notch of the contour
  (user decisions 2026-10-08, #31): a recess open from the storey floor (within 5 cm), at least
  1.9 m high and 0.7-3 m wide at its mouth, is an opening and the contour runs straight over it;
  depth is no criterion. Its mouth must be one straight segment with the facade continuing beyond
  both ends; anything else (a block in an inner corner, an outward band) stays a question.
- Size (spec v0.3, user decision 2026-10-08): an opening is the hole in the wall with its frame;
  the glass is `glass_w` / `glass_h` and `panes`; depth is `opening_depth_default_m` with
  exceptions. How the extractor reads it (rules of #36 / PR #39; the 0.20 m frame and the 0.10 m
  depth threshold were kept by the user 2026-10-09 and live in `spec_extract` of the benchmark's
  `tolerances.json`):
  the reveal around the glass when all glass on that wall covers the reveal's rectangle jointly,
  each pane grown by a frame of 0.20 m (glass of the next storey counts, so a frame through a
  level line is read; an L-shaped set of panes or a tall recess with a short window is no frame);
  panes of one accepted reveal are one opening; without such a reveal the glass places the opening
  and its size is a question; `depth_m` is written when the reveal is more than 0.10 m off the
  default.
- Kind: an opening filled with glass over its whole height (no stretch without glass over 0.20 m,
  a frame member) is a `window`, from the floor or not; a `door` has no glass or glass over part
  of its height.
- Relief is not a kink: a bump or notch with both sizes <= 10 cm (frame profiles, e.g. 7.5 x 9 cm)
  is taken off the contour. The same holds in section (user decision 2026-10-09): a projection or
  groove not over the full storey height whose depth and height are both <= 10 cm (a frame rail)
  is relief, counted as `section_relief_parts` in the report, not a question.
- Panes of one frame — side by side or a transom above, gap <= 0.15 m, aligned, and covering the
  joined rectangle — are one opening with `panes: N`; a curtain wall is one opening, the unit of
  the window library.
- An opening across a level (one frame through the slab line) is one record in the lower floor
  with `level_from` / `level_to` (spec v0.2), not two openings.
- Small kinks (≤ 5°) are removed from the contour on purpose; elements on them are still measured
  on the real facet.

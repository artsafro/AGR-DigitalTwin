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
- Small kinks (≤ 5°) are removed from the contour on purpose; elements on them are still measured
  on the real facet.

# Floor step (`floor-step`)

Status: draft. Source: B02 etalon and user decisions 2026-10-10 (engine order step -> oblique wall
-> terrace; the ledge is part of the step; a soffit takes the facade ID); patterns
`wall-from-contour`, `typical-floor-repeat`.

## Signs in the spec

- Two consecutive floors with different contours (`floors[].contour`; a typical run repeats one).
- Where the floor below reaches out past the floor above: a ledge at the upper floor's level.
- Where the floor above overhangs the floor below: a soffit at that level.

## How to build (`src/dt_ai/geometry/from_spec.py`)

- Walls of each floor by its own contour, from its level to the next level (the top floor to the
  parapet top); walls of two floors on one line meet on the level line with the same cuts.
- At each level line, over the contour difference: a ledge facing up with the roof ID where the
  floor below reaches out, a soffit facing down with the facade ID where the floor above overhangs
  (user 2026-10-10). Both on the shared cut grid, quads, welded to the walls.
- An opening belongs to its wall line, so a frame across a level cuts both floors' walls.

## Profiles

- Same in `npm_min` and `mid`.

## Check

- `floor_areas` per storey, `silhouettes`, `mesh` (no open loop at the step: only the bottom ring and
  an inset roof joint are allowed, pattern `roof-inset-plane`).

## Traps

- A walkable ledge (terrace: parapet or upstand, inset covering) is the pattern `terrace`, next.
- Walls must be axis-parallel until `non-90-corner` is built; an oblique wall is a BuildError.
- A step that is only part of a storey high is no contour step: it is a question (pattern
  `contour-niche`, Level contour).

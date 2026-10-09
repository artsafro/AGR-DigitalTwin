# Typical floor — build once, repeat (`typical-floor-repeat`)

Status: draft. Source: `docs/HARNESS_PLAN.md` §4, §7; issue #8 (PR #25); `src/dt_ai/spec/floors.py`;
`docs/domain/geometry.md` (repeated floors).

## Signs in the spec

- A floor entry `{"level": <second>, "typical_of": <first>, "repeat_to": <last>}`: the floors from
  `level` to `repeat_to` are copies of the full floor `typical_of`. The entry carries no openings.
- The extractor writes it only when storey height, contour (vertex by vertex, radii included) and
  openings (relative to their own level) match the neighbour and the run's first floor within
  1 cm. Anything unclear stays a unique floor; unique floors are written in full.
- `Spec.expanded_floors()` gives every floor in full, for building and for checks.

## How to build

- Build the template floor once (walls, holes, reveals, opening planes), then place it at every
  level of the run, moved up by the level difference (engine function to come with `from_spec.py`).
- Identical floors share one mesh with instance matrices; joins at level lines are welded on the
  shared Z cut, never left as a seam or a T-junction.
- Bottom floors, transition floors and the top floor (with the roof and parapet) are built on
  their own.

## Profiles

- Same in `npm_min` and `mid`: repetition is a property of the spec, not of the detail level.

## Check

- `levels`, `floor_areas` per storey, `opening_planes` for every expanded floor, `mesh` at the
  level joins (no non-manifold edges, no overlapping faces).

## Traps

- Never repeat what the spec does not repeat: no "looks the same" instancing.
- Alternating facades (A/B, a 3.3 m step on a 6.6 m cycle) are not typical of the neighbour; they
  stay unique until a cycle rule exists.
- A floor stops below the top level; the roof storey is never part of a run.
- The template's openings across levels (`level_to`) belong to the template only; ask before
  copying such a frame up a run.

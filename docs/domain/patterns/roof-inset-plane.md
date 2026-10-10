# Inset roof plane (`roof-inset-plane`)

Status: draft. Source: user rule 2026-10-10 (B02 etalon); patterns `parapet`, `wall-from-contour`.

## Signs in the source

- The roof covering is a separate flat element with its own outline, set a few millimetres above
  the foot of the faces around it (parapet inner faces, shaft walls): no edge-to-edge joint with
  them and no overlap. B02: plane at 6.605 m over `LEVEL_roof` 6.600 m, parapet foot at 6.600 m.
- It is a technological element, not a height of the building.

## What the spec takes from it

- Nothing. Every height comes from the input levels: the roof is `LEVEL_roof`, the parapet is
  measured from `LEVEL_roof` to the parapet top. The plane only confirms the roof level within the
  extractor's ±10 cm (pattern `parapet`).

## How to build

- In a hand-made etalon: the plane outline inset in the parapet faces, +5 mm, one plane per roof.
- The engine (`from_spec.py`) welds its roof plane to the parapet foot instead; both are allowed.

## Profiles

- Same in `npm_min` and `mid`.

## Check

- `mesh`: open edges are allowed only as (a) the bottom ring at the model's lowest point and (b) per
  roof level, the inset joint: one horizontal loop of roof-group faces facing up, more than 0 and at
  most `roof_inset_max_m` (0.01 m) above that level's `LEVEL_<name>`, plus at most one loop of the
  upright roof-group faces at that level under it. Every other open loop fails.

## Traps

- A plane lifted further (B02 first had 6.800 m) is no inset: it moves the roof level; fix it.
- Two planes on one roof, or an inset on walls that are not roof-group faces, fail the check.
- Never read a height (parapet, roof) off the plane.

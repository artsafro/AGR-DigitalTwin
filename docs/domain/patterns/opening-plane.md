# Opening plane with window ID (`opening-plane`)

Status: draft. Source: `docs/HARNESS_PLAN.md` §3, §6, §7; `docs/domain/geometry.md` (window rules);
spec v0.3 (#36); window library `library/windows/window_types.json` (#4).

## Signs in the spec

- `floors[].openings[]` with `kind` `window`, `door` or none: `wall`, `x_m` along the wall from its
  start point, `sill_m` from the floor's level, `w_m` x `h_m` = the hole with its frame (v0.3).
- Depth = `opening_depth_default_m` unless `depth_m` is given; `window_type` = library type;
  `material_id` = plane ID read from the source (null with `plane_conflict`).
- `level_from` / `level_to`: one frame through a slab line — one opening, one plane.

## How to build

- Hole: cuts only at the opening edges, on the facade's shared Z cuts (floor, sill, head, top);
  reveals end at the plane seat of the profile (C24; `src/dt_ai/geometry/from_spec.py`).
- One plane per opening, facing out along the wall's outward normal, ID from group `opening`
  (11-15, ADR 0001) by window type; identical types share one mesh with instance matrices.
- Corner window: two planes at the corner angle with a shared welded corner edge.

## Profiles

- `npm_min`: the plane only; the window look is the atlas region of its ID.
- `mid`: library window: plane -> inset frame profile + mullions -> infill (recess open, C25).

## Check

- `opening_planes` (`twinqa.geometry`): group `opening` faces facing out, at the profile's seat
  within `opening_plane_offset_m` (2 cm), covering >= 95 % (a proposal of PR #47, tuned after B01).
  Also `material_ids`, `mesh`.

## Traps

- Seat (C24 final, 2026-10-10): `npm_min` back polygon at full depth; `mid` half, detailed window from it.
- Edges from the wall faces, never from frames or sills; a plane that does not close its reveal
  (a gap to the reveal's end) leaves visible slits: weld it to the reveal.
- A long plane must not cross a belt or another window row.
- `window_type` is the library type, not the ID; no guessed ID under `plane_conflict`; a grille gets no plane.
- Window instance front goes to the opening's outward normal; a blanket 180° flip was an error.

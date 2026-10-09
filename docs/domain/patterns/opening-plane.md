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

- Cut the hole in the wall: cuts only at the opening edges, on Z cuts shared by the facade
  (floor, sill, head, top); reveals from the wall face to the depth (engine function to come
  with `from_spec.py`).
- One plane per opening, facing out along the wall's outward normal, ID from group `opening`
  (11-15, ADR 0001) by window type; identical types share one mesh with instance matrices.
- Corner window: two planes at the corner angle with a shared welded corner edge.

## Profiles

- `npm_min`: the plane only; the window look is the atlas region of its ID.
- `mid`: the library window in the hole: plane -> inset frame profile + mullions -> infill.

## Check

- `opening_planes`: group `opening` faces facing the wall, inside the reveal, cover >= 95 % of
  every window / door / untyped opening. Also `material_ids`, `mesh` (overlaps).

## Traps

- Seating depth is open (conflict C24): mid-reveal with 10 mm past the edges vs measured per
  window. Do not pick one; the checker accepts any seat inside the reveal.
- Infill recess behind the frame (`mid`) is open too (conflict C25).
- Take the opening edges from the wall faces, never from frames or sills.
- Plane at the back of the reveal was rejected: visible slits.
- A long plane must not cross a belt or another window row.
- `window_type` is the library type, not the material ID. Never guess an ID under `plane_conflict`.
- A grille gets no plane (`vent-grille`).
- Window instance front goes to the opening's outward normal; a blanket 180° flip was an error.

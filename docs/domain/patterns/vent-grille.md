# Vent grille (`vent-grille`)

Status: draft. Source: `docs/HARNESS_PLAN.md` §3 (inset elements); user decision 2026-10-09.

## Signs in the spec

- An opening with `kind: "grille"`: position and size only — `wall`, `x_m`, `sill_m`, `w_m`,
  `h_m`, no glass (`glass_w` / `glass_h` / `panes` absent). It is an inset element in the wall
  plane, not a contour point and not an attachment.

## How the extractors read it

- Revit path: an element of the window category with no transparent material is a grille; its
  opening is the family box along its host (point ± hand × width / 2, family box heights). Glass is
  told by material transparency, never by a family or type name.
- Mesh path: a grille is read only when the source carries it as geometry (a hole with louvres);
  an `npm_min` source carries it as texture, so the mesh path has no grille there.

## Profiles

- `npm_min`: texture on the wall (the atlas), no geometry; the spec opening places it.
- `mid`: geometry — a shallow recess or frame with louvres inside the opening's rectangle.

## Check

- Spec comparison: grilles are reported per level but are not in the verdict when the benchmark's
  `tolerances.json` lists `grille` in `spec_compare.opening_kinds_not_in_verdict` (an `npm_min`
  mesh source cannot show them).

## Traps

- A grille is no window: never give it glass or a window type.
- Do not cut a grille through the wall in `npm_min`: it stays a texture.

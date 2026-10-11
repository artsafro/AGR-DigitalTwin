# Facade decor inset (`facade-decor-inset`)

Status: draft (user decisions 2026-10-11; spec block PR 2, engine and checker PR 3, benchmark
`bench-b03-decor` PR 4). Source: the user's NPM decor technology, recorded from a real job.

## Signs in the spec

- A `decor` block (spec, PR 2): `[{kind, level_z, profile, extent, id}]` — `kind` one of `band`
  (belt / cornice), `pilaster`, `column`, `tile-band`; `profile` the cross-section (height and
  projection); `extent` the wall run or the footprint; `id` from the attachment group 26-30
  (`standards/material_id_ranges.yaml`).
- Projection over 0.10 m: geometry. 0.10 m or less: texture (`texture: true`, nothing built) — the
  same threshold as facade relief.

## How the extractor reads it

- Many source pieces of one element (tiles of a belt, segments of a cornice) are one entry: tiling
  and seams are texture, never geometry.
- A piece it cannot assign to one element, kind or wall is a question, never a guess.

## How to build it

- One simple solid per element (a box along the wall for a belt or a pilaster).
- Embedded into the body by `decor_inset_m` = 0.02: the solid runs 0.02 m into the wall and its face
  inside the body is deleted.
- The body mesh is not cut: the wall under the decor stays as without decor.
- A decor face that would coincide with an opening face (a window head, a reveal) is shifted away by
  `plate_gap_m` (5 mm): no shared face, no edge-to-edge joint.
- A free-standing column: its own ID and UV island, a separate part attached to the body in the
  final mesh (not welded). A column or pilaster touching the wall follows the inset rule above.

## Profiles

- `npm_min` and `mid`: the same solids; `mid` may add profile detail later (not decided).

## Check (PR 3)

- No decor face within 5 mm of an opening face; no body edge cut by decor; decor ids in 26-30;
  nothing of 0.10 m or less built as geometry.

## Traps

- Tile-by-tile decor (thousands of boxes) is the source, not the model.
- A decor box with its back face kept doubles the wall face (overlap).

# Facade decor inset (`facade-decor-inset`)

Status: draft (user decisions 2026-10-11; spec block PR 2, engine and checker PR 3, benchmark
`bench-k02-decor-fragment` PR 4, synthetic `bench-b03-decor` later). Source: the user's NPM decor technology,
recorded from a real job; catalogue `benchmark/bench-k02-decor-fragment/decor-catalog.json`.

## Signs in the spec

- A `decor` block (spec, PR 2): `[{kind, level_z, profile, extent, id}]` — `kind` one of `band`
  (belt / cornice), `pilaster`, `lesene`, `spandrel`, `fin`, `column`, `tile-band` (list open until PR 2); `profile` the cross-section (height and
  projection); `extent` the wall run or the footprint; `id` from the attachment group 26-30
  (`standards/material_id_ranges.yaml`).
- Threshold (user 2026-10-11), the same as facade relief: **projection <= 0.10 -> texture; > 0.10 ->
  geometry; the boundary is included** (exactly 0.10 is texture). Decided by the projection alone, never a
  question: a texture entry has `texture: true` and nothing is built.

## What real decor looks like (catalogue of one building, 2471 pieces)

- 85 % of the pieces project more than 0.10 m (geometry): 0.18 (1229), 0.30 (472), 0.60 (224), 0.80,
  0.14, 0.12, 0.20. At or under 0.10 m (texture): 347 glass inserts 0.02 m and 27 pieces at exactly 0.10 m.
- Kinds by shape: spandrel panels between windows (about 2.16 x 1.16, 0.18; one piece per bay and storey);
  vertical strips — lesenes and pilasters (0.35-1.2 wide, several storeys high, 0.18-0.30); horizontal belts
  over a whole wall (0.30, a stepped profile in two pieces); deep panels 0.6-0.8; thin vertical fins 0.05 x
  0.20 at a 0.20 m step (screens).
- Grouping in the source: pilaster strips are split per storey (388 pieces in 62 strips, joints 0.02 / 0.06
  m) — one element each; spandrels and inserts repeat per storey on a 3.3 m rhythm and per bay on 3.4 m
  (typical-floor repeat, not one element).

## How the extractor reads it

- Many source pieces of one element (tiles of a belt, segments of a cornice) are one entry: tiling
  and seams are texture, never geometry.
- **Merging a split element** (user 2026-10-11; the main thing `bench-k02-decor-fragment` checks, with its
  own extractor test in PR 2): source pieces with the same cross-section (width and projection), on one axis
  (same wall, same line along the strip) and with gaps of at most `plate_gap_m` x N between them are one
  element. N = 4 gives 0.02 m, the seam of a pilaster cut per storey. The seam is texture.
- Pieces repeated on the storey / bay rhythm (gaps far over the seam) are separate elements of one typical
  floor, not one element.
- A question only where these rules do not cover the case (a piece that fits no element, kind or wall) —
  never for a number at a threshold.

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

# Facade decor inset (`facade-decor-inset`)

Status: draft (user decisions 2026-10-11; spec block PR 2, engine and checker PR 3, benchmark
`bench-k02-decor-fragment` PR 4, synthetic `bench-b03-decor` later). Source: the user's NPM decor technology,
recorded from a real job; catalogue `benchmark/bench-k02-decor-fragment/decor-catalog.json`.

## Signs in the spec

- A `decor` block (spec v0.5): `[{kind, level, wall, x_m, w_m, z_m, h_m, projection_m, texture,
  material_id, pieces}]` — position as an opening's: `wall` of the contour of the floor `level` (the storey of
  its bottom), `x_m` along it, `z_m` from the level; `projection_m` off the wall face. A free-standing column
  has `footprint: [x0, y0, x1, y1]` instead of a wall. `material_id` only when the source gives one id of the
  attachment group 26-30 (`standards/material_id_ranges.yaml`); `pieces` = source pieces merged.
- `kind` by shape in the wall plane: `band` (width >= 3 x height: belt, cornice, tile band), `strip`
  (height >= 3 x width: pilaster, lesene), `panel` (spandrel and the rest), `column`.
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
- Grouping in the source: pilaster strips are split per storey (388 pieces in 62 strips; joints 0.01-0.06 m,
  all within the 0.06 m seam below, so the same 62 strips under the merge rule; the catalogue groups with
  joints up to 0.10 m and finds no joint over 0.06) — one element each; spandrels and inserts repeat per storey on a 3.3 m rhythm and per bay on 3.4 m
  (typical-floor repeat, not one element).

## How the extractor reads it (`src/dt_ai/spec/decor.py`)

- Candidates: the parts other than the body. Wall decor lies on one contour wall of the storey of its bottom:
  back at the wall face (5 mm) or embedded up to 0.05 m, inside the wall's span, faces axis-aligned in the
  wall frame. A free-standing column: at least 2 m high, 0.05-1.5 m a side, standing on a level, clear of
  the walls. Everything else stays an attachment.
- **Merging a split element** (user 2026-10-11/12; the main thing `bench-k02-decor-fragment` checks): pieces
  with the same cross-section (width and projection), on one axis (same wall, same line along the strip) and
  with gaps of at most `plate_gap_m` x 12 = 0.06 m between them are one element (stacked or in a row). The
  seam is texture. Pieces repeated on the storey / bay rhythm (gaps far over the seam) stay separate elements.
- Questions only where these rules do not cover a piece: `decor-shape` (on a wall, not a box) and
  `decor-deep` (projection over 0.8 m, the deepest common decor of the catalogue: canopy, porch or decor?;
  proposed threshold, to be confirmed) — never for a number at a threshold.

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
- A decor piece sharing a vertex with the body is welded into the body by the extractor (positions are
  welded globally) and is not read as decor: in a source, decor must not share vertices with the walls.

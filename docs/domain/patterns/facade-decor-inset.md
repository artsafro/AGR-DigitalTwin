# Facade decor inset (`facade-decor-inset`)

Status: draft (user decisions 2026-10-11; spec block PR 2, engine and checker PR 3, benchmark
`bench-k02-decor-fragment` PR 4, synthetic `bench-b03-decor` later). Source: the user's NPM decor technology,
recorded from a real job; catalogue `benchmark/bench-k02-decor-fragment/decor-catalog.json`.

## Signs in the spec

- A `decor` block (spec v0.5): `[{kind, level, wall, x_m, w_m, z_m, h_m, projection_m, texture,
  material_id, pieces}]` — position as an opening's: `wall` of the contour of the floor `level` (the storey of
  its bottom), `x_m` along it, `z_m` from the level; `projection_m` off the wall face. A free-standing column
  has `footprint: [x0, y0, x1, y1]` instead of a wall. `material_id` only when the source gives one id of the
  decor group of its material (`standards/material_id_ranges.yaml`): **metal 16-20** (flashing, metal belt,
  bracket), **plaster / stone / tile 26-30** (user 2026-10-12); `pieces` = source pieces merged.
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
  back at the wall face (5 mm) or embedded up to 0.05 m, inside that wall's span (on a concave contour the
  wall that holds it), and on a wall of the same line in every storey it crosses. It must be a box: faces
  axis-aligned in the wall frame, two depths only (no stepped profile) and its front face covering the whole
  front rectangle at full projection.
  A free-standing column: an axis-aligned box (rectangular footprint) at least 2 m high, 0.05-1.5 m a side,
  its bottom on a `LEVEL_*` (user 2026-10-12; one starting mid-storey is a `decor-column` question, not a
  column), clear of the body in every storey it crosses. Everything else stays an attachment.
- **Projection over 0.8 m is no decor** (user 2026-10-12): an attachment candidate — balcony, canopy, bay
  (group attachments, backlog EG2). Never written to `decor`; listed in the report
  (`decor.attachment_candidates`: projection, height, count, positions).
- **Merging a split element** (user 2026-10-11/12; the main thing `bench-k02-decor-fragment` checks): pieces
  with the same cross-section (width and projection), on one axis (same wall, same line along the strip) and
  with gaps of at most `plate_gap_m` x 12 = 0.06 m between them are joinable (stacked or in a row), never
  across the 0.10 m texture boundary. A group of joinable pieces that fills one rectangle up to the seams (a
  row, a stack, a full grid) with one cross-section over the whole group is one element; the seam is texture. Any other group (an L of tiles) stays apart
  and is a `decor-merge` question — the result never depends on the order of the source. Pieces repeated on the storey / bay rhythm (gaps far over the seam) stay separate elements.
- Questions only where these rules do not cover a piece: `decor-shape` (on a wall but no box, or off a wall
  of a storey it crosses), `decor-merge` (above), `decor-column` (a column off a level) and `decor-deep` (the
  attachment candidates, to confirm their kind) — never for a number at a threshold.
- **One question per type** (user 2026-10-12, general rule of the gray zone, HARNESS_PLAN §7): one kind and
  one cross-section (projection and height within 5 mm), repeated on the facade, is one question with its
  count and all positions — never one question per piece.

## How to build it (`src/dt_ai/geometry/from_spec.py`, mesh `decor`)

- One simple solid per element (a box along the wall for a belt or a pilaster), in a mesh of its own.
- Embedded into the body by `decor_inset_m` = 0.02: the solid runs 0.02 m into the wall and its face
  inside the body is deleted.
- The body mesh is not cut: the wall under the decor stays as without decor.
- A decor face that would come closer than `plate_gap_m` (5 mm) to an opening face (a window head, a
  jamb) is moved back to that clearance: no shared face, no edge-to-edge joint. Decor over an opening is a
  build error.
- **Two decor elements meet by a run-in, not a gap** (user 2026-10-12): the subordinate element runs
  `decor_inset_m` (0.02) into the main one through its end, the hidden end face is deleted, the main one's
  mesh is not cut - the same rule as into the wall. Horizontal (band: belt, cornice; panel: spandrel) is
  main, vertical (strip: lesene, pilaster) is subordinate; of one rank (a belt into a belt) the longer
  continues and the other runs into it. Ends closer than `plate_gap_m` meet (an end moved off an opening
  still meets). The 5 mm gap stays only against an opening face.
- **At a convex building corner** (a belt into a belt): the main element runs on past the corner by the
  other's projection and keeps its whole end face. General rule (user 2026-10-12): a back face is deleted
  only where it is set into the wall (or closed by another element); past the corner, outside the wall, the
  main one keeps its back above and below the other. The other, of any height within the main one's, runs in
  without its end: it starts on the main one's back plane (`decor_inset_m` from the corner; a deeper run-in
  would put its front in the plane of the main one's end face). The other higher than the main one (its
  part beyond is closed by nothing): a build error, the `decor-corner` question. The extractor reads a part
  wrapped round a corner as one arm per wall (the corner block to the longer arm), each with its source
  extent to the corner, and asks `decor-corner` when the other arm is higher.
- Build errors (the rule does not cover them): side by side or crossing, one rank and one length, a
  subordinate standing out of the main one, a corner meeting at a concave or an oblique corner.
- ID: the element's `material_id`, else the object's decor ID (`object.json` build ids `decor`).
- A free-standing column: its own ID and UV island, a separate part attached to the body in the
  final mesh (not welded). A column or pilaster touching the wall follows the inset rule above.

## Profiles

- `npm_min` and `mid`: the same solids; `mid` may add profile detail later (not decided).

## Check (`twinqa.geometry.checks.check_decor`, thresholds `decor_tol_m`, `weld_m`)

- The model's decor is read back by the extractor itself and matched one to one with the spec.

- Per spec element: built (front covers `decor_cover_min` of its rectangle at its projection); ids in
  the decor group of its material, metal 16-20 or 26-30, one group per element (its own id when given); at least `plate_gap_m` off every opening of its wall line; the body not
  cut (no body vertex on its outline on the wall face); a texture element has nothing built over it; a
  column covers its four sides; two elements: no face of one in the plane of a face of the other (no butt
  joint) and a run-in of at most `decor_inset_m` + `decor_tol_m`; nothing outside the body that the spec
  does not list. Decor parts are open at the back: `open_part_groups` lists `attachment`.
- The extractor reads a run-in element back with its extent clipped at the main element's face (the
  source's extent), not with the run-in.

## Decor ids by material (user 2026-10-12)

- The id says the material: metal (a flashing, a metal belt, a bracket) 16-20, plaster / stone / tile 26-30;
  the finish behind an id comes from the object's materials table. Case K01: a strip 0.074 x 0.30 m, 0.22 m
  out, on the east wall at 3.6 m, id 17 = `Metal_RAL5015` - a metal bracket, so id 17 is right (it failed the
  first rule, 26-30 only).

## Traps

- Tile-by-tile decor (thousands of boxes) is the source, not the model.
- A decor box with its back face kept doubles the wall face (overlap).
- A decor piece sharing a vertex with the body is welded into the body by the extractor (positions are
  welded globally) and is not read as decor: in a source, decor must not share vertices with the walls.

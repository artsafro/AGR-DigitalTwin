# bench-b03-decor

**Deferred** (user decision 2026-10-11): the first decor benchmark is the real fragment
`bench-k02-decor-fragment`; this synthetic box stays as a later regression (`docs/backlog.md` EG1), mainly for
the free-standing column, which the fragment does not have.

Facade decor by the user's technology (pattern `facade-decor-inset`, draft; user decisions 2026-10-11): one
simple solid per element, embedded into the body, the body mesh untouched, decor ids of the attachment
group 26-30, relief of 0.10 m or less as texture. Both files are made by hand by the user in 3ds Max; the
engine never makes an etalon (HARNESS_PLAN §5).

Two files, because the etalon is the correct result, not the source (user decision 2026-10-11):

| File | What it is | Who reads it |
|---|---|---|
| `source.max` | the building as an architect delivers it: decor as many separate pieces, the tile band as relief | the extractor (`dt spec extract`) |
| `etalon.max` | the same building modelled for NPM by the rules: one solid per element, the band as texture | the checkers (the engine model is compared with it) |

Chain: `source` -> extractor -> `spec.json` (with its `decor` block, PR 2) -> engine (PR 3) -> model ->
checks against `etalon`. The etalon is also checked against itself.

## Base (as B01, both files)

- Box 10 x 10 m, levels `LEVEL_L0` 0.000, `LEVEL_L1` 3.300, `LEVEL_roof` 6.600 (Point helpers).
- Parapet 0.6 m high, 0.3 m thick; roof inset: a hole at 6.600, a plate at 6.605 overlapping the hole by
  20 mm under the parapet (pattern `roof-inset-plane`).
- One window 1.5 x 1.5 m per storey on the south wall (y = 0), x 2.0-3.5, sills 0.9 and 4.2, heads 2.4
  and 5.7; opening depth 0.4 m (the new default, user 2026-10-11): reveals 0.4 m deep, plane at their back
  (npm_min, C24).
- IDs: facade 1, reveal 6, opening plane 11, roof 21. Quads only, welded; open edges only the bottom ring
  and the roof inset joint.

## `source.max` — as from the architect

1. **Belt**, south facade, x 0.0-10.0, z 2.405-2.705, projecting 0.15 m: **not one box** — ten separate
   tiles 1.0 m long each (closed boxes, every one with its back face, sitting on the wall face y = 0,
   not embedded), gaps 0 between them.
2. **Pilaster**, east facade (x = 10), y 4.5-5.0, z 0.000-6.600, projecting 0.12 m: one closed box on
   the wall face (back face kept).
3. **Free-standing column**, 0.4 x 0.4 m at x 5.8-6.2, y -1.60 ... -1.20, z 0.000-3.300: a separate
   object, closed top and bottom.
4. **Tile band**, west facade (x = 0), z 0.90-1.20 over y 0.0-10.0: relief 0.05 m proud, modelled as
   separate tiles 0.30 x 0.30 m (closed boxes on the wall face).
5. Decor material: one material per element (belt, pilaster, column, band), names free; the body as B01.

## `etalon.max` — NPM by the rules

1. **Belt** (`band`), ID 26 — one box over the whole south wall, x 0.0-10.0, z 2.405-2.705 (5 mm above
   the L0 window head 2.400: `plate_gap_m`, no face coincident with the opening), projecting 0.15 m
   (> 0.10 m: geometry). Embedded 0.02 m: the box runs y -0.15 ... +0.02, its back face (inside the wall)
   is deleted. The wall faces under it are **not** cut: the body mesh stays as without decor. Tile
   seams are texture.
2. **Pilaster** (`pilaster`), ID 27 — one box, x 9.98 ... 10.12, y 4.5-5.0, z 0.000-6.600; embedded
   0.02 m, back face deleted, body not cut; open bottom at 0.000 like the body.
3. **Free-standing column** (`column`), ID 28 — 0.4 x 0.4 m as in the source, closed top, open bottom;
   its own UV island; a separate part of the same object (attached to the body in the final mesh, not
   welded to it).
4. **Tile band** — **no geometry**: projecting 0.05 m (<= 0.10 m), so it is texture on the west wall
   (ID 1 faces untouched). The spec still lists it (`decor` entry of kind `tile-band`, `texture: true`),
   the engine builds nothing for it.

## Delivery

Save `data/benchmark/bench-b03-decor/source.max` and `etalon.max` (3ds Max 2024, metres, Z up); the agent
exports both FBX and records their SHA256 in `etalon.json`. The repo keeps spec + hashes only.

## Checks (after PRs 2-4 of the decor plan)

Etalon against itself: the 8 checks of §5 plus the decor checks — no decor face coincident with an opening
(5 mm clearance), no body edge cut by decor, decor ids in 26-30, nothing of 0.10 m or less built as
geometry. Extractor on the source: the `decor` block names belt, pilaster and column as geometry, the band
as texture, the ten belt tiles as one element; anything it cannot decide is a question. Then the engine
model against the etalon.

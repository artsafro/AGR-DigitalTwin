# Inset slab (`roof-inset-plane`)

Status: proven on benchmark (`bench-b01-box`, `bench-b02-corner-niche`, `bench-b02t-terrace`). Source:
user rules 2026-10-10 (B02 etalon; the inset is universal and required — a solid slab is an error, an
etalon that differs is fixed, the rule is never relaxed); patterns `parapet`, `terrace`.

## Signs in the source

- Every horizontal slab surrounded by faces is a separate flat plate: the roof inside a parapet and the
  walkable part of every terrace. Its outline is embedded into the faces around the hole (parapet inner
  faces, walls of the floor above, shaft walls) and it sits a few millimetres above their foot — no
  edge-to-edge joint and no overlap. Etalons: plate 5 mm above the level, embedded 20 mm.
- It is the technology of the joint, not a height of the building.

## The rule (user, 2026-10-10)

1. Per slab exactly two open loops, both closed simple cycles:
   - contour A, the hole in the body: the foot of the upright faces around the slab at its level;
   - contour B, the plate outline at the level + gap.
2. In plan B lies outside A — A grown by one even embed (mitred) into the faces around it, so the
   outlines never cross (`roof_inset_embed_m` 10-50 mm; etalons 20 mm; user: as in the etalons).
   Vertical gap 2-10 mm (`roof_inset_gap_m`; etalons 5 mm). A level may hold several slabs (a ledge in
   parts): each A pairs with exactly one B around it.
3. No height of the spec comes from contour B: levels are the `LEVEL_` helpers; the parapet is measured
   from the level.
4. Required, not only allowed: the roof with a parapet and every terrace must carry the joint; a solid
   slab fails. Any other open loop except the bottom ring is an error. A roof without a parapet has
   nothing to inset into and stays solid.

## How to build

- Hand-made etalon: as above; the foot of the faces around the slab stays open, it is contour A.
- The engine (`from_spec.py`): the slab is left out of the body (the hole) and built as a separate
  quad plate at the level + `slab_gap_m`, outline the hole grown by `slab_embed_m` (object.json
  `build.slab_inset`, no default); one plate per part of a split terrace.

## Profiles

- Same in `npm_min` and `mid`.

## Check

- `mesh` (`twinqa.geometry.checks`): the slabs the spec implies (`slabs(spec)`: the roof level when
  the parapet is > 0, every terrace level) each need a paired A + B (`slabs_not_inset` lists the
  missing); a lone A or B, a third loop, a loop that is not one simple cycle, an uneven embed or a gap
  outside 2-10 mm fails.
- Extractor: a terrace's walkable part is read from the body at the level or from a plate 2-10 mm above
  it (`_inset_plate`), where no cap covers it.

## Traps

- A plate lifted further (B02 first had 6.800 m) is no inset: it moves the roof level; fix it.
- A roof without a parapet keeps parapet 0, whatever the roof plate's offset from `LEVEL_roof`.

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
   - contour B, the plate outline at the level + `plate_gap_m`.
2. The plate is `plate_gap_m` above the level and overlaps the hole by `plate_overlap_m` all round: it
   runs under the parapet / terrace wall by that much (mitred at corners), so the outlines never cross.
   Both are building parameters of the spec (user 2026-10-10), default 5 mm / 20 mm as in the etalons;
   the pattern allows a gap of 2-10 mm (`roof_inset_gap_m`) and an overlap of 10-50 mm
   (`roof_inset_embed_m`). A level may hold several slabs (a ledge in parts): each A pairs with exactly
   one B overlapping it. A shaft through a slab stands in the hole as a part of its own: its foot is an
   inner outline of A, and the plate's hole around it an inner outline of B, shrunk by the same overlap
   (loops of a level read as regions by even-odd).
3. No height of the spec comes from contour B: levels are the `LEVEL_` helpers; the parapet is measured
   from the level.
4. Required, not only allowed: the roof with a parapet and every terrace must carry the joint; a solid
   slab fails. Any other open loop except the bottom ring is an error. A roof without a parapet has
   nothing to inset into and stays solid.

## How to build

- Hand-made etalon: as above; the foot of the faces around the slab stays open, it is contour A.
- The engine (`from_spec.py`): the slab is left out of the body (the hole) and built as a separate
  quad plate at the level + the spec's `plate_gap_m`, overlapping the hole by `plate_overlap_m`; one
  plate per part of a split terrace; a plate that would reach out of the building outline is an error.
- The extractor reads `plate_gap_m` / `plate_overlap_m` from the source's plates (roof and terraces);
  plates of one building that disagree by more than 0.5 mm are a question.

## Profiles

- Same in `npm_min` and `mid`.

## Check

- `mesh` (`twinqa.geometry.checks`): the slabs the spec implies (`slabs(spec)`: the roof level when
  the parapet is > 0, every terrace level) each need a paired A + B (`slabs_not_inset` lists the
  missing); a lone A or B, a third loop, a loop that is not one simple cycle, an uneven embed or a gap
  outside 2-10 mm fails; each plate's gap and overlap equal the spec's `plate_gap_m` / `plate_overlap_m`
  within `plate_tol_m` (0.5 mm), else `plates_off_spec` fails.
- Extractor: a terrace's walkable part is read from the body at the level or from a plate 2-10 mm above
  it (`_inset_plate`), where no cap covers it.

## Traps

- A plate lifted further (B02 first had 6.800 m) is no inset: it moves the roof level; fix it.
- A roof without a parapet keeps parapet 0, whatever the roof plate's offset from `LEVEL_roof`.

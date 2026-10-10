# Inset roof plane (`roof-inset-plane`)

Status: draft. Source: user rules 2026-10-10 (B02 etalon); patterns `parapet`, `wall-from-contour`.

## Signs in the source

- The roof covering is a separate flat element: its outline is embedded into the faces around the
  hole (parapet inner faces, shaft walls) and it sits a few millimetres above their foot — no
  edge-to-edge joint and no overlap. B02: plane at 6.605 m over `LEVEL_roof` 6.600 m, embedded 20 mm.
- It is the technology of the joint, not an exception, and not a height of the building.

## The rule (user, 2026-10-10)

1. Per roof with an inset plane, exactly two open loops, both closed simple cycles:
   - contour A, the hole in the body: the foot of the parapet inner faces at `LEVEL_roof`;
   - contour B, the plane outline at `LEVEL_roof` + gap.
2. In plan B lies outside A — A grown by one even embed into the faces around it, so the outlines
   never cross (B02: 20 mm; `roof_inset_embed_m` 10-50 mm). Vertical gap 2-10 mm
   (`roof_inset_gap_m`; B02: 5 mm).
3. No height of the spec comes from contour B: the roof is `LEVEL_roof`, the parapet is measured
   from `LEVEL_roof`; the plane only confirms the roof level within the extractor's ±10 cm.
4. Any other open loop except the bottom ring is an error.

## How to build

- Hand-made etalon: as above; the parapet foot stays open, it is contour A.
- The engine (`from_spec.py`) welds its roof plane to the parapet foot: no loop; also allowed.

## Profiles

- Same in `npm_min` and `mid`.

## Check

- `mesh` (`twinqa.geometry.checks.open_loops`): bottom ring, and per roof level either no loop or
  exactly A + B as above; a lone A or B, a third loop, a loop that is not one simple cycle, an
  uneven embed or a gap outside 2-10 mm fails.

## Traps

- A plane lifted further (B02 first had 6.800 m) is no inset: it moves the roof level; fix it.
- A roof without a parapet keeps parapet 0, whatever the roof plane's offset from `LEVEL_roof`.

# OBJ03 — parts list for `primitive-first` (step 0, proposal v1, waits for the user)

Date 2026-10-14. Measured from the source dump (read only); pictures: `modules/png/lego-classes.png` (each class
orange on the grey slabs: SW, NE, top, close-up), `modules/png/pier-sections.png` (pier sections, edge lengths in
cm: red < 7, orange 7-10, green > 10). Counts are source pieces / runs; the build does not exist yet.

## Parts, primitive, joint

| # | Part | Source | Count (source) | Primitive (`build_as`) | Joint |
|---|---|---|---|---|---|
| 1 | Walls per storey | slab outline above, glass | 28 storeys | `shell` (quads, openings at OD1 0.4) | stand on slabs (seated), no shared vertex |
| 2 | Slabs | Shape211223725 | 28 + roof | `box` (quad fill) | walls stand on them |
| 3 | Terrace decks | Shape211223718 | 3 levels | `box`, 5 mm off the slab | inset plate |
| 4 | Storey bands round the storey | slots 12/13/15/16, h 0.5 m | L04, L08, L12, L16, L20, L24 | `frame` on the storey contour, one per band | superseded 2026-10-14: piers run through and are never cut; the frame is cut only where it shows with no source band |
| 5 | Roof cornice (two bands) | slots 12/13/15/16 + sheets | 96.06 (h 0.69), 99.0 (h 0.8) | `frame` (two-step profile `profile-extrude` if the step is > 0.10 m) | main element |
| 6 | Piers / pilasters | slots 12/13/15/16 | ~1 330 runs, ~22 types | `box` per run, running through; `profile-extrude` only if the silhouette test fails | through, never cut; bands stop 0.02 m inside piers (user 2026-10-14) |
| 7 | Short bands (window heads with returns, slot strip) | slots 12/13/15/16 | ~450 pieces | `box` / `instance` per type | inset into piers 20 mm |
| 8 | Thin plates 2 cm (sills, heads) | slot 15 | 2 976 pieces, depth 0.16-0.41 m | **question 2** | — |
| 9 | Small balconies | slots 12/13/15/16 + glass | 79 of one type (0.6 x 1.35, sloped underside) | `instance` of one `profile-extrude` + glass plates | inset into the wall 20 mm |
| 10 | Dark inserts | slots 70/72 | ~1 800 panels, few sizes | `instance` of `box` per size, inset, no back | 5 mm off openings |
| 11 | Glazing | slot 5 | 834 openings | opening plane at OD1 (in walls) | — |
| 12 | Glass railings (terraces, balconies) | Shape211223722 / slot 5 off the wall | 22 + 258 plates | `box` 20 mm per free side | 4 mm off the deck |
| 13 | Roof screen enclosure | RailClone2142 | 1 | `plane` on the footprint, no top | seated on the roof |
| 14 | Roof boxes | Shape211223700 | 3 | `box` | seated, 4 mm |
| 15 | Roof slat band | Shape211223719 | 1 | `frame` 40 mm, texture | — |
| — | Lamellas, logos, interior core, frames / trims, reveal sheets (slot 9) | | | texture / skipped (decisions 2026-10-13/14) | — |

## Type catalogue (repeats -> instances), first cut

| Type | Count | Where |
|---|---|---|
| balcony 0.6 x 1.35 (sloped) | 79 | east / west / south faces, every storey |
| pier 0.6 x 0.32 | ~350 | all faces |
| pier 0.8 x 0.82 | ~150 | corners |
| plate 2 cm x 0.18 | ~1 000 | window sills / heads |
| dark insert (sizes to be grouped) | ~1 800 | spandrels under the windows |
The full catalogue (94 section types) comes with the build report.

## Budget per module (NPM 150 000 per FBX), proposal

| Module | Budget | v008 (before) |
|---|---|---|
| walls | 24 000 | 21 472 |
| slabs + decks | 12 000 | 11 940 |
| storey bands + cornice (frames) | 4 000 | (inside decor) |
| piers (boxes) | 20 000 | (inside decor) |
| short bands, heads | 10 000 | (inside decor) |
| thin plates | 0 or 30 000 (question 2) | (inside decor) |
| balconies + their glass | 8 000 | (inside decor / parapets) |
| dark inserts | 18 000 | (inside decor) |
| parapets, railings, roof | 6 000 | 3 596 |
| reserve | 18 000 | — |
| **total** | **150 000** | **133 926** (decor 96 918) |

## Questions (pictures attached)

1. The parts list above: confirm, or correct a part / its primitive / its joint.
2. Thin plates 2 cm thick, 0.16-0.41 m deep (2 976, sills and heads): their height (2 cm) is under 7 cm but their
   projection is over 0.10 m. Geometry (one `box` instance per type) or texture?
3. Storey bands that do not run round the whole storey (L08: 74.7 of 103 m, L20: 72.8 of 103 m - interrupted by
   deeper piers and terraces): one frame on the whole contour, or a frame only where the source has the band?
4. Pier steps of 7-10 cm (`pier-sections.png`: 10 cm flats on piers 0.6 x 0.32, 0.6 x 0.52, 1.2 x 0.32): collapse
   (box) or keep (profile)?

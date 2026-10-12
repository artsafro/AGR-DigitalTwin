# case-alina-bld — the colleague case through the harness

Pipeline status: draft

Object id provisional (`case-alina-bld`; the real `<site>-<code>` is a question). Purpose (user 2026-10-12):
run the building of the colleague case (`docs/cases.md`, alina-bld) through the full chain - intake, extract,
spec, from_spec, checkers - in mixed mode (engine as far as it goes, balconies EG2 a question or a numbered
script, UV untouched) and compare with the colleague's scripted v001.

## Source (read only)

- `C:/Users/artsafro/Downloads/alina_bld.max` (3ds Max 2024, metres), layer `Геометрия исходная`: 12 meshes
  and 7 dummies (the user, 2026-10-12). Other layers (`BODY_v001`, `OPENINGS_v001`, `DECOR_v001`,
  `BALCONIES_v001`) are the colleague's results, not the source. Scene not saved.
- Exported: `data/sources/case-alina-bld/source-geometry-v001.fbx` (FBX 2014, Z up, metres), dump
  `dumps/source-dump-v001.json` (sha256 of the FBX b643a277…): 12 meshes, 452 k triangles, no `LEVEL_*`.
- Finishes are Corona sub-material slots: slot 5 is glass (refraction 1.0, split into `*_glass` by
  `materials.json`), slot 82 curtains, 16 brick, 15 dark brick, 12 light, others black / grey; mapped to 0
  until the user gives a finish table.

## Levels (user: "уровни сними с плит")

Tops of up-facing faces of slab object `Shape211223725`: L00 0.0 (bottom, no slab), 6.5, 9.8 ... 92.3 every
3.3, 95.75, roof 96.55. Open: 95.75 and 96.55 are 0.8 m apart (a storey or the roof build-up?); terrace decks
`Shape211223718` at 56.2 / 69.4 / 82.6 lie 0.2 above the slabs 56.0 / 69.2 / 82.4.

## Run 1 (2026-10-12): the extractor stops - no body

- The extractor takes the body as the largest connected part: `Shape211223721` (83 triangles, 318 m2, 0 to
  95.45 m) - an inner mass, not the envelope. The facade is `RailClone2146`: panels, 8884 separate parts,
  no closed shell. First stop: L00 has no wall shape over the full storey (`contour_at_m`), on that inner
  mass. Nothing was guessed; the provisional `contour_at_m` values tried to list the stops were removed.
- The slabs close per level: one polygon each, 611.0 m2 up to 56.0, 599.4 from 59.3, 582.1 from 72.5,
  522.2 from 85.7 (the setbacks under the terrace decks) - but with 104-221 vertices (the slab edge follows
  facade details), so a slab outline is not a wall line as it stands.
- The colleague took the contours from the slab tops (`body-outlines.json`: "Shape211223725 slab tops;
  Shape211223718 deck tops") and built the body by scripts.

Next: the user's decision on where the envelope comes from (see the questions in the session summary);
then intake files, extract, engine, checks.

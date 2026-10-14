# bench-k01-kpp1

First real building: object `tec26-kpp1` (`jobs/REGISTRY.md`, `jobs/KPP1/`), 27.66 x 11.66 m, levels 0 / 3.9 / 7.7 / 8.65.

Patterns: all patterns that pass B01-B03.

Checks (`npm_min`, starting thresholds, final values in `tolerances.json`): bounding box
±5 cm; level heights ±3 cm; floor area ±2 %; silhouette IoU ≥ 0.97 (4 sides + top); mesh
manifold, no n-gons, no overlapping faces; triangles within the profile budget; an opening
plane with ID in every spec opening; material IDs in their ranges (ADR 0001).

The etalon is KPP1 v005 finished to 100 % by hand (v005 is ~90 %; an etalon with defects teaches defects). Sources stay in the object's job; this folder links to them, it does not copy them. Spec comparison Revit vs mesh: issues #9-#11.

## K01 run v001 (2026-10-11): material IDs and geometry thresholds

User decisions 2026-10-11 [D053]: KPP1 material IDs from `jobs/KPP1/materials.json` (finish -> ID by the ranges of
ADR 0001; asphalt of the blind area = 0, Ground, a question); the checker reads them from the UDIM tile of
every triangle (the VPM FBX has one material, finishes are tiles: `measure_spec_blender.py` writes
`udim_tiles`, `object.json` `materials` names the table); `geometry` thresholds = the HARNESS_PLAN §5
starting numbers (as B01) with `open_part_groups` attachment and metal (railings, ladder, cage, alpha
planes may be open shells). `object.json`: frames, levels and contour heights of `jobs/KPP1/object.json`
plus build inputs (parapet 0.555 m). The runner takes the spec's levels when the source has no LEVEL_
helpers.

Etalon = KPP1 v007 VPM FBX (job scripts, option a). Etalon against itself: bbox, levels, storey areas,
silhouettes, triangle budget **pass**; the inset roof joint is recognised (slabs inset, plates as the spec);
**fail**:
- `mesh`: 88 open loops outside the allowed ones (decor parts that are not only attachment / metal, e.g.
  canopies in facade IDs) and 10 non-manifold vertices, real contacts at every weld down to 0.00001 mm:
  6 at the south window surrounds against the cassettes (y -0.07, z 4.97 / 6.53), 2 on the west facade
  (x -0.07) and 2 next to the south doors (z 2.70, x 13.01 / 14.09) (review 1 of PR #72);
- `opening_planes` 0.0: KPP1's openings are glass + frames (VPM), not an npm_min plane at the opening depth
  (C24 seat); with door (11) and glass (12) in the opening group the extractor also takes them as planes and
  asks 25 `wall-break-off-contour` questions;
- `material_ids`: 200 unassigned triangles (asphalt, by the table).
The engine stops on the KPP1 parapet (a face at 8.65 m between x 0.225 and 0.38 is no trapezoid).
Open: each of these needs a decision (K01 profile: npm_min or VPM rules for openings; decor IDs; the
asphalt; the engine's parapet strip) before K01 can be green.

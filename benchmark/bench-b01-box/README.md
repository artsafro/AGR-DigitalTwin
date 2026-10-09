# bench-b01-box

Box 10 x 10 m, 2 storeys, 2 windows, flat roof with a parapet.

Patterns: wall-from-contour, opening-plane, typical-floor-repeat, parapet.

Etalon: issue #12 (user); spec: #13; checkers: #14. Thresholds: `tolerances.json` (`geometry`
for the checkers, `spec_extract` for the extractor).

## What the etalon carries (#12)

The numbers are the user's; the extractor reads whatever is modelled. The synthetic test box
(`tests/qa/test_geometry_checks.py`, same numbers as `tests/fixtures/spec-b01-v0.3.json`) is one
choice: levels 0 / 3.3 / 6.6 m, parapet 0.6 m, one 1.5 x 1.5 m window per storey on one wall,
sill 0.9 m, recessed 0.2 m.

- 3ds Max, metres, on a grid; `etalon.max` plus `etalon.fbx` (large files by link).
- Level helpers `LEVEL_L0`, `LEVEL_L1`, `LEVEL_roof` (any object type; its world Z is the level);
  `LEVEL_roof` is the top of the roof covering, not the parapet top.
- Walls over the full storey height; each window a hole with reveals and an opening plane at the
  reveal depth; roof plane, parapet inner faces and cap. Quads only; separate meshes may meet on
  shared edges. Whether the shell must be closed is open: the checker reports open edges and
  judges them only when `boundary_edges_max` gets a number.
- Material IDs by group (`standards/material_id_ranges.yaml`, ADR 0001): facade 1-5, reveals
  6-10, opening planes 11-15, roof / parapet inner faces / cap 21-25. No face left at 0.

## Run

```
blender --background --factory-startup --python tools/source/measure_spec_blender.py -- etalon.fbx <dump.json>
uv run dt spec extract --dump <dump.json> --object <object.json> --output spec.json --tolerances tolerances.json
uv run python tools/qa/check_geometry.py <model-dump.json> <etalon-dump.json> --spec spec.json --tolerances tolerances.json --output <report.json>
```

The model dump comes from the same Blender script, run on the built model (engine `from_spec.py`,
HARNESS_PLAN §9); the model must carry the same `LEVEL_<name>` helpers. First run the etalon
against itself: every check must pass, or the etalon (or a threshold) is wrong.

## Checks (`twinqa.geometry`, starting numbers of HARNESS_PLAN §5)

| Check | Rule |
|---|---|
| `bbox` | every bound within `bbox_m` (5 cm) |
| `levels` | every etalon `LEVEL_<name>` present in the model, within `level_elev_m` (3 cm) |
| `floor_areas` | outer section area at `section_fractions` of each storey within `floor_area_rel` (2 %) |
| `silhouettes` | IoU of the x, y and top projections >= `silhouette_iou_min` (0.97); front/back outlines are mirror images |
| `mesh` | no edge of more than two faces; open edges reported (judged when `boundary_edges_max` is set, never on stand-alone opening planes); no n-gons; no near-parallel faces closer than `overlap_m` (5 mm) |
| `triangle_budget` | triangles <= `triangles_max` (NPM OKS 150 000) |
| `opening_planes` | each spec window / door / untyped opening holds group `opening` faces facing the wall, inside the reveal, covering >= 95 % |
| `material_ids` | every ID in a group range, none unassigned |

`passed` is true only when every check passes; a check that cannot be measured (for example a dump
without `polygon_sizes`) is an open gate, not a pass.

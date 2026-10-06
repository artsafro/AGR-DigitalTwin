# KPP1 (Центральная проходная) — VPM + NPM model, 2026-10-07

Status: **model and textures built, technical QA run; not passed for hand-over** (deferred items below).
User acceptance pending.

## Scope (user, 2026-10-07)

Model and texture KPP1 for VPM and NPM, stage by stage: body, windows, roof, plinth, decor and
attached parts, technical parts; then textures, then collision. Quads, 4 x 4 m max. Must pass the
SINTEZ checks, no gaps, no flipped normals. Deferred by the user: GeoJSON, Moscow coordinates,
district code.

## Sources

- Revit: `C:\Users\artsafro\Documents\26_КПП1_АР_МЭП_RVT25_artsafro.rvt` (Revit 2025 copy of
  `DigitalTwinProject\Revit\26_КПП1_АР_МЭП_RVT22.rvt`), opened detached through the RevitBridge pipe,
  **not saved**. Levels 0.000 / +3.900 / +7.700 / +8.650; plan 27.66 x 11.66 m.
- ИД: `Downloads\ТЭЦ26 на РР.pptx`, slides 25-30 (facades 1-4, A-B; plans; roof; section). Used for
  finish bands, cassette module (0.6 m; blue band 2.7-7.1 in 8 rows of 0.55 m), perforated panels,
  stair RAL 5015 / handrail RAL 1021.

## Pipeline (`scripts/`)

| Step | Script | Output (`outputs/`, local only) |
|---|---|---|
| Revit element ids | revit-http `revit_list_elements` (paged) | `census-v001/elements.json` |
| Revit FBX groups + sidecars | `export_revit_groups.mjs` (RevitBridge `agr_export_fbx`, RVT not saved) | `source-v001/` |
| Census / id match / openings | `dump_source.py`, `match_ids.py`, `extract_openings.py` | `census-v001/` |
| VPM textures (18 UDIM x D/ERM/N) | `make_textures.py` | `textures-v001/` |
| Build stages 1-6 | `run_stage.sh <n>` -> `build_kpp1.py` (+ `seal.py`, `vpm_uv.py`, `vpm_ucx.py`) | `build-v001/KPP1_VPM_v00N_*.blend` |
| Master QA | `qa_master.py` | `build-v001/qa_master_v006.json` |
| Everything after stage 6 | `run_all.sh <tag>` (VPM export/package, NPM atlas/export/zip, SINTEZ) | `package-*-<tag>/`, `sintez-<tag>/` |

Prior accepted cycle (2026-10-06, DigitalTwinProject `Scripts/kpp1`) is the base; changes in this run:
- `seal.py`: seam T-junctions split by edge-ring cuts inside each piece (quads kept), cuts clustered
  at 2.5 mm, one final 2.5 mm weld (> SINTEZ 2 mm doubles); triangles -> 3 convex quads;
- 3.9 m texel cuts on every finish (user: quads <= 4 x 4 m), not only on textured ones;
- east steel stair rebuilt from Revit parameters as closed quad solids (was raw Revit triangles);
  RAL 5015 per Revit material and ИД;
- concave roof quads (joined Revit triangles near the shaft) split before quadification;
- alpha strips mitred at corners; spout boxes closed;
- textures: cassette joints (blue 0.6 x 0.55, phase +2.70; grey and top band vertical joints only),
  perforated cassettes, yellow handrail; new finish `Cassette_RAL5015_Top`, unused `Steel_Stair` removed;
- NPM: `make_npm_atlas.py` (2048 atlas, region per finish = 4.096 m like the VPM tile, ~97 px/m,
  joints >= 1.5 px, separate `_o_` opacity map, no alpha, no normal, no m/r), `export_npm.py`
  (alpha back copies removed, UV remapped into the atlas, embedded PNG, `M_Glass_01` alpha 0.5).

## Results (v002, 2026-10-07)

Master `build-v001/KPP1_VPM_v006_ucx.blend`:
- Main 12 974 quads (100 %), 25 948 tris; MainGlass 38 quads; max edge 3.894 m; 0 concave/twisted quads;
- seams: 0 seam T-junctions, 0 vertex doubles within 2 mm, leak probe (rays aimed 1 mm past every
  open edge from 65 off-axis directions) 0 leaks;
- normals: 0 back faces seen from outside on opaque geometry (23 hits = edge-on ends of the 5 mm
  two-sided alpha strips, reg p.36 §12.3); 8 inward-looking faces are hidden faces covered within
  3 cm (porch top under door sills, aerator base, stair frame joints), 266 are embedded inside bodies;
- 33 UCX hulls, closed and convex, 396 tris.

VPM `package-vpm-v002/SM_Kpp_1.zip`: FBX + 54 PNG (18 UDIM 1001-1018), density 969-1032 px/m.
NPM `package-npm-v002/0000_Kpp_1.zip`: `0000_Kpp_1_01.fbx`, `SM_Kpp_1_001_Main` 25 910 tris +
`SM_Kpp_1_001_MainGlass` 76, atlas d 0.9 MB + o.

SINTEZ AGR Checker 1.6.1 (`sintez-v002/agr_check.json`):
- VPM (hp): 64 verified, 3 failed, 53 manual. Failed: 2.1.1 УКЭП signature (hand-over), 2.2.1 and
  2.10.4.1 GeoJSON missing (deferred by the user).
- NPM (lp): 38 verified, 5 failed, 29 manual. Failed: 2.1.1 УКЭП; 2.1.2 and 2.1.6 Ground FBX missing
  (Ground is a separate deliverable, not in this task); 2.10.3.1 district code `0000` placeholder and
  4.1.4 height outside 110-250 m (coordinates deferred by the user).

## Open

- User review of the model (fine details: grilles, slats, roof items; compare with Revit/ИД cameras).
- Deferred: GeoJSON, MSK-77 placement (NPM coordinates, VPM insertion point), district code, address
  (placeholder `Kpp_1`), УКЭП. Ground, GroundEl, Flora are a separate job.
- Cassette module 0.6 x 0.55 is read from the ИД drawing scale, not from a dimensioned album.
- Manual gates V015-V017 unsigned.

## Update v003 (2026-10-07)

- Same-camera Revit vs model close-ups: `scripts/compare_details.sh` -> `outputs/compare-v001/pair_*.png`.
  Revit door families carry 3D swing volumes (cylinders) — not geometry, correctly absent. Stair
  differences (railing layout, ladder cage hoops) left as is by the user.
- Added roof walkways (136 Logicroof tiles -> draped 25 mm strips, finish `Walkway_Logicroof`, UDIM 1019);
  aerators rebuilt to the Revit profile (flange cone, pipe, small hat).
- v003: 13 490 quads, 0 leaks/doubles/concave; SINTEZ VPM 64/3, NPM 38/5 (same deferred items).
  69 inward-looking faces = membrane covered by walkway strips (hidden).
- 3ds Max review file `outputs/max-v001/KPP1_VPM_NPM_quads_v001.max` (Max 2026): VPM at 0,0,0, NPM at
  +40 m X, both untriangulated (`KEEP_QUADS=1` exports, not deliveries); VPM UDIM shown with
  Andrew's `UDIM Viewer_V1.4.ms` (Blend: Multi/Sub per tile + MultiTile), NPM Physical d + cutout o.
- Open: 3ds Max xView reported 128 overlapping faces on NPM (canopy tops, porches, stair landing) —
  to classify (coplanar landing/frame tops suspected).

## Update v005 (2026-10-07): overlapping faces / vertices

User gate: 3ds Max xView Overlapping Faces (0.005 m) = 0 and Overlapping Vertices (0.002 m) = 0;
fix by embedding one part into another or by stitching with added edges.
- Cause of 238 Max overlapping vertices: welds that gave edges with 3+ faces (79); Editable Poly
  splits them on import. `seal.py` now splits/welds only open-border seams; parts that stand on or run
  into a surface are embedded instead (`columns()` EMBED 11 mm into the wall, piers 10 mm into porches
  and stepped back INSET 6 mm from flush porch faces, feature mullions 10 mm into the canopy).
- Stair: frame + stringer in one plane = one stitched prism; frame corners stitched (open cap + extra
  edge, welded edge to edge); other joints embedded with 6 mm step-back; decks 6 mm below frames.
- Alpha two-sided planes 8 mm apart (reg 3..10 mm).
- `scripts/qa_overlap.py` (xView rules incl. touching coplanar faces of different parts) runs in
  `run_all.sh`; `scripts/qa_checktoolbox.py` runs CheckToolBox_v1_5 (Blender 4.4) doubles/intersections.
- Result v005: Blender overlap 0 / non-manifold 0 / doubles 0 / leaks 0 / 100 % quads; 3ds Max 2026 xView
  on the quad FBX: Overlapping Faces 0 and Overlapping Vertices 0 on VPM and NPM Main + Glass.
  CheckToolBox intersections remain by design (embeds). SINTEZ VPM 64/3, NPM 38/5 (deferred items).
- Max review file: `outputs/max-v005/KPP1_VPM_NPM_quads_v002.max`.

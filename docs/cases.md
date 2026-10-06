# Accepted cases and lessons

Read the matching case before a similar task and respect its acceptance scope.
User praise, a passing test and a published file are different statuses. No case below
is an official delivery: nothing has passed the regulation check or AGR Checker yet.
Full write-ups (Russian originals) are in `docs/agr/case_studies/`; object state and
evidence in `jobs/<JOB>/`. Template for new cases: `docs/agr/case_studies/TEMPLATE.md`
(an English template is backlog item H4).

| Case | Accepted by the user | Still open | Write-up / job |
|---|---|---|---|
| Obr22 typical floor | BODY geometry, material scale, NPM v012, VPM UV v011 | full OKS delivery, Checker | `OBR22_ACCEPTED_WORKFLOW.md`, `jobs/OBR22-K02/` (`APPROVED_VERSIONS.json`) |
| SOSH1150 continuous wall UV + FBX v006 | UV / wall pattern, prepared package | native 3ds Max check | `SOSH1150_CONTINUOUS_WALL_UV_FBX.md`, `technical_library/UV_V006.md`, `jobs/UV-CONTINUOUS/` |
| GLB A_Main / B_Main atlases | current scene look; B: IDs/UV, pure-white glass | FBX, Checker; A v005 manual edits not reproducible | `GLB_A_MAIN_ATLAS.md`, `GLB_B_MAIN_ATLAS.md`, `technical_library/glb_atlas/` |
| GLB reference planes / window simplification | — (lesson) | — | `GLB_AB_REFERENCE_AND_PLANES.md`, `docs/agr/lessons/SKETCHUP_COMPOSITE_WINDOW_OPENINGS.md` |
| GLB SketchUp MCP read-only v001 | connection works read-only | write path | `GLB_SKETCHUP_CONNECTION.md` |
| Window frames — box lights v002 | layout on this node (247 sections), native readback | UV, FBX, Checker, second object | `WINDOW_FRAMES_BOX_LIGHTS.md`, `jobs/WINDOW-FRAMES/` |
| Facades atlas | tile v003 | brick (rejected in v003); v004/v005 need new acceptance | `FACADES_ATLAS_PARTIAL_ACCEPTANCE.md`, `jobs/FACADES-ATLAS/` |
| Ground contours → NPM | contours, 18 material IDs, materials (v003) | v003 mesh rejected; v008 shape acceptance | `GROUND_CONTOURS_AND_NPM.md`, `jobs/GROUND-PROJECTION/` |
| MASHI-LP scene audit | scene organization and audit | new master is a trial; intersections, visual acceptance | `MASHI_LP_SCENE_AUDIT.md`, `jobs/MASHI-LP/` |
| KPP1 VPM + NPM v005 (Revit → Blender) | full modelling cycle and models v005 as reviewed ("90 % ready", 2026-10-07): quads ≤ 4 m, no leaks, xView overlaps 0/0, SINTEZ only deferred fails | GeoJSON, MSK-77, district code, address, УКЭП, Ground; manual SINTEZ items, V015–V017 | `KPP1_VPM_NPM_V005.md`, `jobs/KPP1/` (`REPORT.md`) |
| SOSH1150 openings (REVIT-OPENINGS) | — (pilot) | approximate types/placements not accepted | `jobs/REVIT-OPENINGS/STATE.md` |

Rules distilled from these cases are already in `docs/domain/` with `local:` citations.

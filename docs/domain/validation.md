# Validation, QA checklists, checkers, pitfalls

Keys: `reg p.N` = `Rasporyajenies19012026trebovaniya(2).pdf` page N. `local:` relative to the repo root (AGR knowledge base; AGR `docs/` lives in `docs/agr/`).

## Delivery validator spec (V001-V017) - local: standards/DELIVERY_VALIDATOR.yaml (spec only, not implemented)
- V001 both: ZIP readable, no broken/extra files, size/composition per profile. reg NPM p.6-7, VPM p.26.
- V002 both: binary FBX 7.4/2014, 1 unit = 1 m. reg p.4, 24.
- V003 both: triangulated, triangle counts, object types, no empties/forbidden modifiers. reg p.6-8, 28-29.
- V004 both: duplicates, isolated elements, zero edges, applied transforms. reg p.7-8, 29.
- V005 both: allowed shaders; maps/slots/transparency per profile. reg p.8-9, 29-30, 32.
- V006 NPM: PNG embedded, allowed sizes, <= 3 MB, no alpha, 8 px padding, sets and names. reg p.9, 11-13.
- V007 VPM: external PNG, Diffuse+ERM+Normal for each used UDIM, 8 bit, sizes, DirectX normal, alpha rules, padding. reg p.23, 30-31, 34, 36.
- V008 VPM: one UV channel, UDIM 1001..1100 sequential, no mirrored islands, glass only in 1001. reg p.31, 39.
- V009 VPM: diffuse density 512..1706 px/m except allowed exceptions. reg p.31-32.
- V010 VPM: UCX per main FBX; convex closed non-intersecting, no slots, triangle limit. reg p.34, 36-37.
- V011 VPM: GeoJSON UTF-8, exact keys/types/values, imageBase64, Glasses, glass material names match. reg p.26-27, 51-55.
- V012 both: archive/FBX/mesh/material/texture names and continuous numbering. reg NPM p.11-13, VPM p.33-36.
- V013 VPM: local origin 0/0/0, shared pivot, rotation 0; GeoJSON MSK-77 matches insertion point. reg p.32-33, 55.
- V014 NPM: geometry in Moscow project coords/heights; angles match plan. reg p.10.
- V015 both (manual): silhouette, floors, facades, materials, window types, ground floor, roof, landscaping match approved project. reg p.4, 7-8, 24, 28-29.
- V016 VPM (manual): passages/arches/courtyards free; collision offsets per height zone. reg p.36-37.
- V017 both (manual): insertion point, zero mark, georef vs approved DWG/SPOZU; VPM tolerance 0.5 m. reg p.10, 32-33, 55.
- Order: ZIP/PNG/names/GeoJSON first, then FBX geometry/UV, then visual overlays and collision. Every fail returns path in archive, object/material, measured value, PDF page. Compare NPM vs VPM composition (OKS, Ground) but never require same topology/UV. local: standards/DELIVERY_VALIDATOR.yaml#implementation_order.
- Pass policy: passed=true only with 0 blocking errors, all mandatory machine checks run, manual checks signed; unknown data = review/not_run, never pass; customer addendum kept separate with own source/version. local: standards/DELIVERY_VALIDATOR.yaml#pass_policy.
- Manual gates: sources_confirmed (CRS/units), materials_approved, master_geometry_approved, facade_and_windows_approved, placement_approved, collision_review_approved (VPM), delivery_approved; each records author/date/input versions; changed dependency resets gate to review. local: docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md#9; local: docs/agr/workflow/pipeline.md.
- Pilot inputs needed: source FBX + units, facade/material/window album with sizes, DWG/SPOZU with insertion point/CRS/zero mark, reference accepted NPM/VPM package or screenshots, accepted GeoJSON sample, address naming, customer addendum. local: docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md#10; local: docs/agr/READINESS_REPORT.md#8.

## General QA procedure (project)
- Validate the actual exported files re-read from the ZIP (FBX/PNG/GeoJSON), in a separate clean process; scene-only checks insufficient. local: docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md#4 (project decision).
- Check the saved and reopened file after last Attach: groups, face degrees, duplicate/near verts, duplicate/overlapping/intersecting faces, connectivity, boundaries, normals; compare contour/openings/sizes with source; list problem IDs. local: docs/agr/GEOMETRY_RULES.md#Проверка (project decision).
- Never claim "done/clean/compliant" with unrun checks; report unverified criteria explicitly. Import/readback/Mesh.validate success and zero exact duplicates do not prove absence of partial overlaps. local: docs/agr/GEOMETRY_RULES.md (project decision).
- Distinguish allowed >= 10 mm embeds from defective overlaps; bbox/SAT overlap alone does not prove a defect; coplanar overlap confirmed by 2D polygon intersection area; non-parallel faces by intersection line. local: docs/agr/GEOMETRY_RULES.md; local: docs/agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md#math (project decision).
- Topology checklist used: quad %, degenerate faces, duplicate verts/faces, loose elements, edges with > 2 faces, T-junctions (20 um), coplanar partial overlaps (<= 2 mm plane distance, area > 1e-5 m2), interior crossings (> 20 mm, 3 mm border band excluded), normals/winding, open boundaries classified. local: jobs/MASHI-LP/MODEL_V002_REPORT.md (lesson).
- 5 mm near-parallel clearance check: |dot| > 0.999999, min projected area 1e-7 m2, both orientations; tests only parallel faces. local: jobs/GLB-NPM/CLEARANCE_RULES.md (lesson).
- Tight variant: intersection tol 5 um, area 1e-7 m2, surface vs source volume <= 0.005 mm; overlap < 1e-8 m2 per planar group = noise. local: jobs/OBR22-K02/STATE.md (lesson).
- Interior ray probe (e.g. 368 640 rays from inside, 0 front-face hits) proves no visible inner faces; not full QA. local: jobs/GLB-NPM/TOWER_STAGE_V022.md (lesson).
- Atlas/ID check: sample pixels at island centers vs assigned ID; check padding, mirroring, accidental overlaps; read PNGs back from ZIP (size, RGB/RGBA mode, equal opposite edges, seam step). local: jobs/OBR22-K02/STATE.md; local: jobs/FACADES-ATLAS/STATE.md (lesson).
- NPM vs VPM scale check: compare saved UVs at identical physical points (phase error, scale ratio ~1) + same-camera renders. local: docs/agr/decisions/OBR22_NPM_SCALE_V012.md (lesson).
- Visual review at same camera from front and at angle (overlay on approved facades) is mandatory; numeric pass != visual acceptance. local: docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md#4; local: docs/agr/lessons/SKETCHUP_COMPOSITE_WINDOW_OPENINGS.md (project decision).
- Synthetic negative fixtures for validator: broken ZIP, extra file, PNG mode/size, swapped ERM, normal sign, UDIM 1001/1010/1011/1100 and out-of-profile, missing tile, material slots, FBX header, GeoJSON fields. local: docs/agr/inventory/INTEGRATION_PLAN.md (project decision).
- Near-threshold ZIP sizes -> manual review (MB/GB decimal vs binary undefined). local: docs/agr/decisions/ADR-0002-source-discrepancies.md#4.

## Checker tools - how to interpret
- SINTEZ AGR Checker (Blender addon, v1.6.1 seen; also 1.5.0, 2.6.1 mentioned): Python checks of ZIP/FBX/UV/UDIM/UCX/GeoJSON; its findings must be mapped to PDF pages/V-codes; installed checker is not the norm. local: docs/agr/inventory/README.md (project decision).
- AGR Checker run on an isolated NPM component: 53 records 2 pass/9 fail/42 review; fails in FBX/object/texture/material naming, transforms (2.3.14), material count (2.5.11), map presence (2.5.6), OKS file set/landscaping - whole-package gates fail for components; naming/maps/transforms must be met at export. local: jobs/ORCH-OBR22-NPM/cli-runs/cursor-20261001-004/verdict.md (lesson).
- Wrapper "pass" status only means the checker ran. `CheckUtils._calculate_td({1001:4096}, True)` spot-check reports td_less/td_greater/margin failures - not a full run. local: jobs/ORCH-OBR22-NPM/.../verdict.md; local: jobs/UV-CONTINUOUS/STATE.md (lesson).
- SINTEZ `ucx_polycount_limit` implements its own 15k/5%/100k combination; agreement of two tools does not resolve the PDF ambiguity. local: docs/agr/decisions/ADR-0004-reuse-installed-toolchains.md.
- Blender CheckToolBox 1.5: doubles distance 5 mm applies to vertices; Intersection epsilon hard-coded 0.01 mm (1e-5 m); flags allowed embeds and unwelded source, cannot be green on embedded NPM; classify hits, don't claim pass. local: docs/agr/case_studies/GLB_AB_REFERENCE_AND_PLANES.md#v006; local: jobs/GLB-NPM/CLEARANCE_RULES.md (lesson).
- GeoAGR `ucx_check.exe`: exit 0 even with findings; misses fully nested volumes; treats face contact as finding; outputs names only. Check convexity/closure/coverage/gap/nesting separately. local: docs/agr/inventory/GEOAGR_13_63_REVIEW.md#GEN-11 (lesson).
- Max `Collizii.ms` precise test is bbox-only (returns true without tri test); `isConvex` true for < 4 verts; `UCX_Check.ms` misses nested volumes and doesn't measure gap; `UDIM Viewer` detects ERM/ORM but doesn't wire them, clamps negative UVs; MatID by average face UV. local: docs/agr/research/max-workbench/REVIEW.md; local: docs/agr/inventory/ZAVOD_AND_MAX_PLUGINS_REVIEW.md (lesson).
- Generic DirectX check of arbitrary normal map is not possible without context; RGB-only tests don't cover alpha/glass branches. local: docs/agr/READINESS_REPORT.md#4; local: docs/agr/decisions/ADR-0002-source-discrepancies.md#7.

## Pitfalls (lessons)
- Zero face-clearance audit != no visible gaps (v006 0 pairs but light slits from wrong window depth). local: jobs/GLB-NPM/CLEARANCE_RULES.md.
- Volumetric embedding fixed horizontal coplanar contact but 523 side coplanar pairs remained. local: docs/agr/case_studies/GLB_AB_REFERENCE_AND_PLANES.md#v004.
- Simple remove_doubles left inner joint faces; delete both inner mating faces before welding. local: docs/agr/case_studies/GLB_AB_REFERENCE_AND_PLANES.md#v003.
- Renaming UV map after Attach without updating material node broke opacity mapping. local: docs/agr/case_studies/GLB_AB_REFERENCE_AND_PLANES.md#v022.
- Ground density check wrongly applied to NPM-OKS and reported as pass. local: docs/agr/decisions/OBR22_NPM_SCALE_V012.md.
- Wrong composition (full Revit interior) fails regardless of clean mesh. local: docs/agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md.
- Material ID selection by old number after renumbering selects nothing; check actual face counts per ID first. local: docs/agr/case_studies/GLB_A_MAIN_ATLAS.md.
- Save over a file erased previous readback evidence; snapshot versions, approved files frozen, new iterations to new paths. local: docs/agr/case_studies/GLB_A_MAIN_ATLAS.md; local: jobs/OBR22-K02/STATE.md.
- User praise/% ratings and renders are not QA metrics; ray coverage vs Revit is a completeness gauge, not tolerance. local: jobs/GLB-NPM/STATE.md; local: jobs/MASHI-LP/AUDIT_AND_PLAN.md.

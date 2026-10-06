# Geometry, naming, coordinates, collision

Keys: `reg p.N` = `Rasporyajenies19012026trebovaniya(2).pdf` page N (see npm-vpm.md header). `local:` relative to the repo root (AGR knowledge base; AGR `docs/` lives in `docs/agr/`). Tags: (project decision) = user/project instruction, not regulation; (lesson) = only source is a lesson/case study.

## Regulation geometry rules (both profiles unless noted)
- No empty objects, animation/keys, deformers, cameras, sounds, bones, extra layers, helpers, interior structures, underground/internal utilities, people, vehicles, animals. reg p.6 §1.3 (NPM), p.28 §3.1, p.29 §3.11 (VPM; also no extra modifiers).
- VPM: all objects in the single default layer/collection; no more than one layer. reg p.28 §3.2.
- Minimal triangle count for silhouette, except extra splits needed for UV optimization; minor non-shape-forming details go to texture. reg p.7 §3.1, p.28 §3.3.
- VPM: bake decorative/minor details protruding or recessed up to 5 cm into texture; exception: curb projections. reg p.32 §7.
- OKS (free-standing buildings, sections, korpus, structures, stylobates) are separate objects inside FBX, never merged (NPM). reg p.7 §3.3.
- Geometry, translucent parts and usable-roof landscaping of one model go into one FBX. reg p.7 §3.2, p.28 §3.5.
- No hierarchy/groups between geometry objects. reg p.7 §3.5, p.28 §3.8.
- Ground perimeter polygons extruded down >= 1 m (VPM: textured with placeholder of averaged color of source polygons). reg p.7 §3.4, p.28 §3.7, p.44.
- VPM: OKS perimeter polygons also extruded down >= 1 m to sink into Ground. reg p.28 §3.6.
- Max 100 duplicates/self-intersections of vertices/edges/polys (distance tolerance 0.002 m); no isolated verts/edges/polys; no zero-length edges. reg p.8 §3.7, p.29 §3.11.
- Normals of visible objects face observer; no missing polygons visible from any reachable view (incl. through glass); no shading defects. reg p.8 §3.8, p.29 §3.15.
- Co-directional overlapping polygons spaced 5 mm..2 cm (anti z-fight). reg p.8 §3.9, p.29 §3.13.
- Window-type glazing not seen from back: no thickness, single plane. reg p.8 §3.10, p.32 §8.3.
- Triangulate before FBX export. reg p.8 §3.11, p.29 §3.17.
- NPM: simplified interior walls/ceiling/floor only where visible through translucent parts. reg p.8 §3.12.
- VPM: interiors replaced by solid walls and floors; complex/invisible inner walls removed; wall thickness >= 10 cm. reg p.29 §3.12.
- NPM: geometry with opacity map gets NO thickness (no duplicated offset polys with inverted normals). reg p.8 §3.13.
- VPM: alpha-cut polygons visible from both sides -> duplicate with uniform offset 0.003-0.01 m along local normal and flipped normal. reg p.36 §12.3.
- Reset/apply all transforms (VPM: including collision geometry). reg p.8 §3.14, p.29 §3.18.
- Smoothing groups set by designer per project, assigned per polygon only. reg p.8 §3.15, p.29 §3.14, p.43 (fig. 4.1-4.3: missing smoothing, smoothing vs real angle mismatch, unwelded verts).
- VPM: glazing geometry is a separate object from facade; all glazing of one model merged into one object. reg p.28 §3.4, p.32 §8.1.
- VPM: vegetation realistic, no stylization; model trunk + main branches, small twigs/leaves as planes with alpha texture. reg p.29 §3.16.

## Units, coordinates, pivots
- 1 unit = 1 m, scale 1:1. reg p.4, 24.
- NPM: geometry in MSK Moscow coordinates + project heights; no arbitrary coords; rotations after reset = plan rotation of OKS. reg p.10 §8.
- VPM: origin 0,0,0 per FBX; pivot at geometric center X/Y, Z = project zero; same pivot for all meshes in FBX; rotation 0 after reset; insertion point MSK-77 in GeoJSON (3 decimals, <= 0.5 m from SPOZU plan position). reg p.32-33 §9, p.55.
- Keep work placement near local zero; store transform + source georef; apply profile-specific placement at publish; never mix Moscow coords with local FBX units. local: docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md#4 (project decision).
- Local frame for orthogonal facades: `p_local = R^T (p_world - origin)`; contour noise merged within 1 mm, checked by Hausdorff distance (source-specific budget, not construction tolerance). local: docs/agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md#math (lesson).
- Verify units on import: a Ground FBX came in 100x too large; real site size (116x164 m) confirmed with user before rebuild. local: docs/agr/case_studies/GROUND_CONTOURS_AND_NPM.md (lesson).
- Large DWG offsets lose DCC precision; DWG may use other units/UCS != WCS/nested blocks: keep raw coords + explicit matrices + control points. local: docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md#11; local: docs/agr/inventory/INTEGRATION_PLAN.md#INT-004.

## Naming - NPM (reg p.10-13)
- Suffixes: geometry `Main`, `MainGlass`, `Ground`, `GroundGlass`, `GroundEl`, `GroundElGlass`, `Flora`; maps `d` diffuse, `n` normal, `o` opacity, `m` metallic, `r` roughness. reg p.10-11 §9.
- Max 254 chars incl. address and all affixes; Latin, digits, `_` only. reg p.11 §10.1-10.2.
- ZIP `{prefix4}_{Address}.zip`, prefix = 4-digit code from the all-Moscow classifier of territorial units (reg p.2 term), e.g. `0313_ProezdNansena_ZU_8.zip`. reg p.11 §3.1.
- OKS FBX `{prefix}_{Address}_{NN}.fbx`, NN 01-20, step 1, no gaps, ascending; single FBX = `_01`. Ground FBX `{prefix}_{Address}_Ground.fbx`. reg p.11 §3.2.
- Objects: `SM_{Address}_{NNN}_Main` (NNN 001-020 = OKS number across whole project, not per FBX), `SM_{Address}_{NNN}_MainGlass`, `SM_{Address}_Ground`, `SM_{Address}_GroundGlass`, `SM_{Address}_GroundEl`, `SM_{Address}_GroundElGlass`, `SM_{Address}_Flora`. reg p.11-12 §3.3.
- Textures: OKS `T_{Address}_{NNN}_{GeomSuffix}_{map}_{Slot}.png` (e.g. `T_ProezdNansena_ZU_8_001_Main_d_1`); Ground/El/Flora `T_{Address}_{GeomSuffix}_{map}_{Slot}.png`. Slot starts at 1. Texture names inside editor identical to PNG filenames. reg p.12-13 §3.4.
- Materials = texture name with `M` prefix and without map suffix (`M_ProezdNansena_ZU_8_001_Main_1`, `M_..._Ground_1`). reg p.13 §3.5.
- NPM translucent materials: `M_Glass_01`..`M_Glass_07` project-wide, same names reused. reg p.13 §3.5. (Not in NPM YAML - local: docs/agr/decisions/ADR-0002-source-discrepancies.md#9.)

## Naming - VPM (reg p.33-36)
- Each word capitalized, incl. inside address elements; every element/affix/number/letter separated by `_`; UV-map names inside 3D editor need only be Latin. reg p.33 §10.2-10.3.
- FBX/GeoJSON/ZIP share stem: OKS `SM_{Address}`, Ground `SM_{Address}_Ground`, lights `SM_{Address}_Light`, `SM_{Address}_Ground_Light`. reg p.33 §4.1.
- Objects: `SM_{Address}_Main`, `SM_{Address}_MainGlass`, `SM_{Address}_Ground`, `SM_{Address}_GroundGlass`. reg p.33 §4.2.
- Collision: `UCX_SM_{Address}_Main_{001..999}`, `UCX_SM_{Address}_Ground_{001..999}`. reg p.34 §4.2.
- Textures: `T_{Address}_{Diffuse|ERM|Normal}_{Slot}.{UDIM}.png`, Ground `T_{Address}_Ground_{Type}_{Slot}.{UDIM}.png` (dot before UDIM is the only allowed dot exception). reg p.34 §4.3, p.36.
- Materials: `M_{Address}_Main_{Slot}`, `M_{Address}_MainGlass_{Slot}`, `M_{Address}_Ground_{Slot}`, `M_{Address}_GroundGlass_{Slot}`; Slot 1-7. reg p.34 §4.4, p.35 §11.

## Collision / UCX (VPM only; NPM has none unless customer spec)
- Each geometry FBX has its own collision (except lighting FBX). reg p.36 §13.3.
- Collision = array of Mesh objects, each convex, closed, no holes, no material slots, named per mask. reg p.36 §13.1, p.47.
- Built for: Ground surface (not MAF, lighting, vegetation); existing OKS inside the site; every OKS incl. arches, courtyards ("wells"), large facade projections, volumetric elements. Not for canopies/fences/railings <= 5 cm thick. reg p.36 §13.2.
- Pieces must not intersect each other; recommended gap 0.02-1 cm (recommendation). reg p.36 §13.4.
- Shape tolerance: Ground (esp. perimeter) <= 10 cm; OKS lower floors reachable by pedestrian (1st floors, stylobates, 2nd floors next to bridges/platforms) <= 30 cm; rest of OKS <= 1 m. reg p.36 §13.5.
- Entrance stairs collision = truncated pyramid. reg p.36 §13.6.
- Triangle budget: model < 50 000 tris -> 15 000; else ceil(model_tris x 0.05) (e.g. 1 243 374 -> 62 169); model limit does not apply to collision, may add up to 100 000 when model reaches its limit. reg p.36-37 §13.7-13.8. (Ambiguous - conflicts.md.)
- Do not close arches/courtyards/openings with one hull; split volume by functional voids; verify passages by overlay. local: docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md#5, #11 (project decision).
- Do not add collision polys just to pass the percent limit. local: docs/agr/inventory/INTEGRATION_PLAN.md#INT-006 (project decision).
- Andrew `UCX_Tools.ms` default gap 2 mm (tool default, not norm). local: docs/agr/research/max-workbench/REVIEW.md#3.

## Project modeling rules (user decisions, not regulation)
- Editable master: 100% quads; no tris/n-gons, no degenerate/twisted/self-intersecting quads; triangulate only in a derived export copy; keep both and check both. local: docs/agr/GEOMETRY_RULES.md (project decision).
- Separate meshes per logical group (body/walls, windows, roof, doors...) allowed; Attach/Join does not create clean topology; no artificial bridging faces. local: docs/agr/GEOMETRY_RULES.md (project decision).
- BODY = exterior shell only from outer contours; do not model Revit interiors/partitions. local: docs/agr/GEOMETRY_RULES.md (project decision).
- Order: outer quad surface (cuts only at corners and opening width/height) -> delete opening faces -> check zero-thickness surface -> Shell inward 0.4 m keeping outer contour -> delete inner back faces, keep reveals -> windows into openings. local: docs/agr/GEOMETRY_RULES.md; local: docs/agr/geometry-quality.mdcc (project decision; 0.4 m is this project's value, not universal).
- No ultra-thin strips or unjustified through-cuts; do not propagate all source coordinates across the facade. local: docs/agr/GEOMETRY_RULES.md (project decision).
- VPM texel cuts: logical quads < 4x4 m via Connect on opposite edges, propagated through shared edges, no T-junctions; preserve shape/openings/material. Adapter default max side 3.9 m; Connect: n = ceil(L/Lmax), bilinear interpolation of new points, merge shared points. local: docs/agr/GEOMETRY_RULES.md#Итоговая; local: docs/agr/ADAPTER_EXTRACTION.md; local: docs/agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md#math (project decision).
- Shared surfaces share vertices/edges; no split seams or T-junctions; no blind Merge-by-Distance (collapses thickness/openings). local: docs/agr/GEOMETRY_RULES.md (project decision).
- Constructive embedding of one mesh into another >= 10 mm allowed and must be labeled; 10 mm is embed depth, not weld tolerance. After final Attach: no duplicate/coplanar-overlapping faces, no accidental self-intersections. local: docs/agr/GEOMETRY_RULES.md (project decision).
- Before Attach choose per joint: Weld (continuous surface: match boundary, delete inner mating faces, weld that joint only; weld tolerance from coordinate precision) or embed >= 10 mm (both ends, incl. adjacent repeated floor); delete end caps fully hidden inside receiving part, keep partially hidden ones. local: docs/agr/GEOMETRY_RULES.md#Выбор стыка (project decision).
- Extend posts only along height, keep straight planar sides; no chamfers/inset/slanted strips; split coplanar mating faces in their common plane. local: docs/agr/GEOMETRY_RULES.md (project decision; lesson: chamfers rejected in v010->v022, local: docs/agr/case_studies/GLB_AB_REFERENCE_AND_PLANES.md).
- NPM with opaque window textures: remove inner shells, back walls, hidden parts of reveals/sills; trim partially visible faces to outer shell; keep outer soffits of projecting belts (do not delete whole floor slabs). local: docs/agr/GEOMETRY_RULES.md (project decision).
- Min gap between overlapping parallel faces 5 mm (project GLB), both orientations. local: docs/agr/GEOMETRY_RULES.md (project decision; matches reg p.8 §3.9 lower bound).
- Keep Revit ID/type/material per face via face attributes + external mapping; never invent layers/finish from color/name. local: docs/agr/GEOMETRY_RULES.md (project decision).
- Identical window types = shared mesh + instance matrices, not independent copies. local: docs/agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md (project decision).
- Windows: start from opening plane/outline, frame outline, recessed seating, then divisions per source type; seating depth measured from source (10 mm embed does not define seating depth). local: docs/agr/GEOMETRY_RULES.md (project decision).
- Frame topology: frame = outer rectangle minus panels with 4 convex quads around each panel; avoid propagating panel grid across frame (removed 47% of window quads). local: docs/agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md#3 (lesson).
- NPM window planes: two planes (corner windows at 90 deg, shared welded corner), 10 mm beyond opening edges on 4 sides, seated mid-depth of reveal (e.g. 240 mm reveal -> 120 mm); reveals = color/ID of existing opening faces, no extra geometry; sills = simple sliced plate with thickness. local: docs/agr/case_studies/GLB_AB_REFERENCE_AND_PLANES.md (project decision).
- NPM AC baskets: one-sided planes without top, perforation via opacity only, no Solidify/modeled holes. local: docs/agr/case_studies/GLB_AB_REFERENCE_AND_PLANES.md (project decision).

## Job-level rules and lessons (jobs/*; mostly one project each)
- Raw Revit import (5% quads, 440 duplicate faces) is not a model; Join/Dissolve is not retopology. Revit FBX: no Material nodes, matrices carry 0.3048 (feet) factor, Blender truncates names - restore full names/Revit IDs first. local: jobs/OBR22-K02/STATE.md (lesson).
- Revit section export: level heights from API; top cut = next level - 1 mm; bottom = real slab underside; unloaded links give no geometry; check categories (ceilings named like walls). local: jobs/OBR22-K02/STATE.md (lesson).
- BODY quad layout: U cuts only at opening edges/corners; shared Z levels (floor, sill, head, top); propagate opposite-edge splits until converged; no fans. local: jobs/OBR22-K02/STATE.md (lesson).
- Loop removal only between coplanar faces at valence 4 with collinear remaining edges; protect corners/opening contours. Faces with side ratio > 100 and edges ~0.2 mm flagged as defects (accepted versions min edge ~20 mm). local: jobs/OBR22-K02/STATE.md (lesson).
- Contour orthogonalization: cap vertex shift (0.25 mm used); reject non-orthogonal walls instead of silently flattening. Do not auto-round source groups 5-10 mm below nominal level. local: jobs/OBR22-K02/STATE.md; local: jobs/GLB-NPM/AUDIT_AND_PLAN.md (lesson).
- Repeated floors: verify real geometric identity before instancing; facades may alternate A/B (e.g. 3.3 m step, 6.6 m cycle); build lower/transition floors and unique tops separately. local: jobs/GLB-NPM/AUDIT_AND_PLAN.md; local: jobs/GLB-NPM/LOWER_FLOORS_SCOPE.md (project decision).
- Shell only on new clean exterior surfaces; never re-thicken parts that already have volume; Shell baked, no live modifier. local: jobs/MASHI-LP/AUDIT_AND_PLAN.md; local: jobs/OBR22-K02/STATE.md (project decision). Shell policy varies per deliverable (see conflicts.md).
- Mid-poly master: Connect so quads < 3.8 m per side; profile simplification 8 mm (trial budget); small fittings excluded. local: jobs/MASHI-LP/MASTER_DIRECTIVE.md (project decision).
- Revolved/cylindrical detail: delete thin posts (~51 mm dia) at NPM, reduce 12 -> 6 sides by removing every 2nd edge (12 -> 8 needs resampling); keep height rings/steps; no global Decimate; test on representative copies. Two rings at same height with different radii = step, not duplicate. local: jobs/MESH-OPT-AUDIT/AUDIT.md (project decision / lesson).
- Open boundaries (sections, facade shells, open caps) may be intentional: classify, don't auto-flag. local: jobs/MESH-OPT-AUDIT/AUDIT.md (lesson).
- Separate narrow levels by 5.1 mm not exactly 5 mm (float guard). local: jobs/GLB-NPM/TOWER_STAGE_V022.md (lesson).
- Window plane hidden 10 mm top/bottom strips trimmed to outer shell at final assembly so no front face is visible from inside; long planes must not cross belts or other window rows. local: jobs/GLB-NPM/TOWER_STAGE_V022.md, TOWER_STAGE_V023.md (lesson).
- Window planes: take opening edges from wall faces, not from frames/sills; place per opening at mid reveal depth (behind-reveal seating rejected: visible slits). local: jobs/GLB-NPM/CLEARANCE_RULES.md (project decision).
- NPM sills: plates one mesh per floor, 60 mm (source 40 + 10 top/-10 bottom embed), 20 mm XY outline to avoid back-face coincidence with windows. AC baskets width -20 mm (10/edge). local: jobs/GLB-NPM/CLEARANCE_RULES.md (project decision).
- Simplified window/door library: plane -> inset profile + mullions -> extrude infill; exactly 2 material IDs (1 frame, 2 infill); no hardware; 50-100 mm size differences may share a type only with same division/leaf count. Infill recess 30 mm behind frame face. local: jobs/REVIT-OPENINGS/STATE.md; local: jobs/REVIT-OPENINGS/outputs/openings-v003/README.md (project decision).
- Window instance orientation: align local front (-Y) to each opening's outward normal; validate dot(normal, facing) = 1; blanket 180 deg flip was an error. Depth from source part mid-thickness is approximate only (151.8 mm off on a 303.5 mm curtain wall). local: jobs/REVIT-OPENINGS/outputs/body-v005/README.md, placements-v004/README.md (lesson).
- Do not invent parts cut off by a section boundary (e.g. lower window); get full source. local: jobs/OBR22-K02/STATE.md (lesson).
- Slab soffits: never delete a whole slab bottom; rebuild exterior overhang soffits from real sections; constrained Delaunay keeps area of complex contours. Mass boundary-vertex insertion created micro-faces (rejected). local: jobs/GLB-NPM/TOWER_STAGE_V022.md (lesson).
- Fix source duplicates surgically, no global Merge by Distance. Rebuilding Revit planes: merge exterior planes by contour; selecting only visible tris left gaps; full Revit planes bring overlapping patches. local: jobs/MASHI-LP/MODEL_V002_REPORT.md, MASTER_TRIAL_REPORT.md (lesson).
- Facade signs: all-quad, manifold, positive volume; thickness 30 mm (user-confirmed). Box-light housings: open-top shell, planar bases, >= 10 mm embed. local: jobs/FACADE-SIGNS/STATE.md; local: jobs/WINDOW-FRAMES/BOX_LIGHTS_STATE.md (project decision).

## Ground modeling (NPM, project)
- Ground NPM: <= 50 000 polys (quad FBX), ~3 m quads, finer at contours/slope breaks; ignore 10-20 cm steps, keep >= 30 cm if needed, as smooth slopes; smoothed height field (2.5 m median, 25 cm quantization, Gaussian sigma 1.6 m used). local: docs/agr/case_studies/GROUND_CONTOURS_AND_NPM.md; local: jobs/GROUND-PROJECTION/NPM_RESULT.md (project decision). Within reg p.7 §3.6 180k total.
- Dense adaptive projection (720k quads) and exact vertical cut-in of steps (micro-strips, twisted faces) rejected; keep material contours on 1 mm lattice (<= 0.715 mm after FBX); beyond relief continue nearest slope without moving XY. local: jobs/GROUND-PROJECTION/RESULT.md, NPM_RESULT.md (lesson).
- Ground UV: one channel, 0-1 tile, regions reused per finish; atlas from source colors only. local: jobs/GROUND-PROJECTION/NPM_RESULT.md (lesson).

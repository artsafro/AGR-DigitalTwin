# UV, UDIM, texel density, textures

Keys: `reg p.N` = `Rasporyajenies19012026trebovaniya(2).pdf` page N. `local:` relative to the repo root (AGR knowledge base; AGR `docs/` lives in `docs/agr/`). (project decision) = user/project rule, not regulation; (lesson) = from case study only.

## NPM textures (App.1)
- Textures delivered as PNG atlases embedded in FBX. reg p.9 §5.1.
- Allowed sizes only 256, 512, 1024, 2048 px square; max 2048. reg p.9 §5.2.
- Max file size 3 MB per texture map. reg p.9 §5.3. 3 MB = 3 MiB (conflict #12, decided as the checker).
- Padding >= 8 px between neighboring islands with unique images. reg p.9 §5.4.
- Alpha channel forbidden. reg p.9 §5.5.
- Diffuse mandatory; optional: normal, opacity, roughness, metallic; roughness + metallic only as a pair. reg p.9 §5.6, p.17 fig.6. Project: no normal map in NPM (conflict #6, decided 2026-10-07).
- If roughness/metallic used but no variation -> use flat placeholders instead of full maps. reg p.9 §5.7.
- Opacity map only if transparent elements exist. reg p.9 §5.8.
- All maps in one set same size, except placeholders. reg p.9 §5.9.
- Placeholder (NPM): PNG 128x128, 8 bit/channel, filled with one averaged color of replaced texture; exempt from density. reg p.3-4. (VPM placeholder = 256x256 - see conflicts.md.)
- Opaque glass in atlas: glass areas white on diffuse and metallic maps, black on roughness; no opacity map, or opacity UV region filled white. reg p.9 §5.10.
- GroundEl: one set for all elements, <= 512x512. reg p.10 §5.12.
- Flora: one set for all vegetation, <= 2048x2048; only diffuse and (if needed) opacity. reg p.10 §5.13.
- Density applies ONLY to Ground relief surface within site: >= 10 and <= 40 "px per sq.m" (text example: 2048 px texture <-> 204x204 m square, i.e. ~10 px/m linear). Not applied to perimeter extrusion, Flora, OKS, GroundEl. reg p.10 §6.1-6.2. (Unit conflict - conflicts.md.)
- NPM-OKS: no density gate; key criterion = brick/tile/finish physical size identical to approved VPM; change atlas pixel size and UV scale together; px/m only diagnostic. local: docs/agr/UV_RULES.md#Приоритетное; local: docs/agr/decisions/OBR22_NPM_SCALE_V012.md (project decision, regulation-consistent with p.10).
- Ground NPM example approaches: "baking" vs "slicing" for relief/atlas. reg p.18 fig.7-8.
- Normal map definition NPM: X -1..+1 -> R 0..255, Y -1..+1 -> G 0..255, Z 0..-1 -> B 128..255 (convention not named). reg p.3. (Differs from VPM - conflicts.md.)
- Example PBR map colors (fig.6): mirror glass D255 M255 R0; copper D231,?,188 (G garbled) M255 R135; gold/brass D255,238,171 M255 R110; aluminium D245,246,246 M255 R177; chrome D230,232,232 M255 R110. reg p.17 (OCR of figure; values partially garbled - verify on image before use).

## VPM textures (App.2)
- PNG separate from FBX, not embedded; all texture paths removed from materials in FBX. reg p.30 §4.2, §5.1.1.
- Sizes only 2048x2048 or 4096x4096. reg p.30 §5.1.2.
- Diffuse resolution >= ERM and Normal resolution. reg p.30 §5.1.3.
- Mandatory set: Diffuse, ERM, Normal. Opacity may be encoded in Diffuse alpha. reg p.30 §5.1.4.
- ERM = RGB: R Emissive (glow strength, grayscale; color from diffuse; does not light surroundings), G Roughness, B Metallic; R = black if no emissive surfaces. reg p.23, p.37 §14.
- Padding between unique-image islands on one tile: >= 16 px @2048, >= 32 px @4096. reg p.30 §5.1.5.
- ERM and Normal strictly without alpha. reg p.30 §5.1.6.
- Normal maps DirectX convention (Y +1..-1 -> G 0..255). reg p.30 §5.1.7, p.23.
- Every map must project onto >= 1 polygon (no unused maps). reg p.30 §5.1.8.
- 8 bit per channel (RGB 24 bit, RGBA 32 bit). reg p.30 §5.1.9.
- Holes/cut-outs: B/W 0-255; 0-127 = void, 128-255 = solid; baked into Diffuse alpha. reg p.36 §12.1-12.2.
- Placeholder VPM: 256x256, no alpha, single averaged color; may mix with full-size maps within one UDIM set; only on surfaces without pronounced texture (smooth, chrome) or where texture is modeled; forbidden for marble, brick, tile etc. reg p.22, p.31 §3.1-3.5.
- Do not convert normal in files: keep DirectX; invert green only in Blender preview nodes; ERM/Normal as Non-Color. local: docs/agr/inventory/INTEGRATION_PLAN.md#INT-003 (project decision, based on SINTEZ build_udim_material).
- Do not substitute ERM with ORM/IRM; ORM conversion stays outside normative exporter. local: docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md#5; local: docs/agr/inventory/NPM_VPM_MAP.md (project decision).
- VPM maps are not valid NPM maps without converting alpha/normal/packing and glass rules. local: docs/agr/READINESS_REPORT.md#2.

## VPM UV / UDIM
- Main and Ground: UDIM only, single UV set on one channel. reg p.31 §2.1.1.
- Geometry larger than one tile (at required density) must be split; repeating/similar islands placed by overlap. reg p.31 §2.1.2.
- Tiles filled from 1001 strictly sequential, no gaps, 10x10 grid (1001-1100), numbered left->right, bottom->top. reg p.23, p.31 §2.1.3, p.39. UDIM = 1001 + U + 10*V. local: docs/agr/decisions/ADR-0002-source-discrepancies.md#5.
- Mirrored islands forbidden; rotating islands not recommended. reg p.31 §2.1.4.
- Keep margin from tile borders. reg p.31 §2.1.5.
- Avoid visible seams/shifts/pattern mismatch between maps. reg p.31 §2.1.6.
- Glass (*_MainGlass, *_GroundGlass): all UVs in tile 1001, max fill, margin from border, overlaps allowed, single channel. reg p.31 §2.2.
- Texel density applies only to Diffuse; ERM/Normal/placeholders exempt. reg p.31-32 §6.1.
- Density 512..1706 px/m; formula rho = L_t / L_p (texture side px / polygon length m) - OCR shows "+", image shows division. reg p.32 §6.2 (image-verified). Examples: 4096 -> squares 7.8..2.5 m = 525..1638 px/m; 2048 -> 3.9..1.3 m = 525..1575 px/m. reg p.32.
- Maps using alpha: prefer higher density in range. reg p.32 §6.2.
- More than 100 UDIM maps on Main -> extra material slots (up to 7), SlotNumber from 1 sequential; do not split Main by slots below 100. reg p.30 §4.3-4.4.

## Project UV rules (user decisions)
- Group faces by finish/texture ID first, then lay out UVs; stack identical/similar islands of one finish in a shared region; keep physical scale, proportions, pattern direction and joint phase; no stretching of "similar" sizes. local: docs/agr/UV_RULES.md#Раскладка (project decision).
- NPM: one atlas with regions per texture type (3 tile types -> 3 regions reused). VPM target: one UDIM per texture ID (4 IDs -> 4 UDIMs, not 19 from unique packing). local: docs/agr/UV_RULES.md; local: docs/agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md (project decision; lesson: unique packing bloated VPM to 19 UDIMs).
- If a region doesn't fit at required density + padding, split into logical sub-islands in the same region/tile; do not add UDIMs or lower density by default. local: docs/agr/UV_RULES.md (project decision).
- UV seam inside a big face requires real quad cuts per geometry rules; not a UV-only operation. local: docs/agr/UV_RULES.md (project decision).
- Overlap only identical textures/purpose; never overlap unique signage/local details; never mirror pattern. local: docs/agr/UV_RULES.md (project decision).
- Texture ID is a semantic finish group, not a shader slot; keep explicit `finish_id -> atlas_region/UDIM`; unknown ID0 never auto-assigned (keep highlighted, e.g. pink). local: docs/agr/UV_RULES.md; local: docs/agr/decisions/OBR22_FACADE_PDF_UV_TRIAL.md (project decision).
- Glass pixels on color atlas = pure white RGB 255,255,255 (#FFFFFF), no gray/blue tint; frames/mullions/spandrels placed by their own finish. local: docs/agr/UV_RULES.md; local: docs/agr/case_studies/GLB_B_MAIN_ATLAS.md (project decision; consistent with reg p.9 §5.10).
- Repeat shift: move island by integer number of pattern periods keeping `coord mod period` + common phase; choose phase over all faces of the material so long faces fit with padding. local: docs/agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md#math.
- Material scale: texture_px = physical_m x sampling_px_per_m; UV = px / image size + region/UDIM offset; change pattern and UV together when resolution changes. local: docs/agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md#math.
- Reference finish modules used (user-confirmed for one project, not universal): brick 250x65 mm + 10 mm joint (pitch 260x75, half-bond), tile 600x1200 mm + 5 mm joint (pitch 605x1205, long side vertical). local: docs/agr/decisions/OBR22_PROCEDURAL_TEXTURES_V010.md (project decision).
- Achieved references: VPM 4x4096 ~1024 px/m (one 4096 tile = 4x4 m), pad 32 px; NPM 2048 atlas pad 8 px at 96 px/m chosen for readability (39.9 px/m blurred brick joints). local: docs/agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md; local: docs/agr/decisions/OBR22_NPM_SCALE_V012.md (lesson).
- Sub-pixel joints vanish: 5 mm joint at 80 px/m < 1 px; numeric QA passed but user rejected brick readability; widen joint raster to >= 1 px on atlas only (12.5 mm) and darken panel joints. local: docs/agr/case_studies/FACADES_ATLAS_PARTIAL_ACCEPTANCE.md (lesson).
- Upscaling a small sample does not create detail; rebuilding joints gives size, not photo detail. local: docs/agr/case_studies/OBR22_ACCEPTED_WORKFLOW.md#Что пришлось (lesson).
- Continuous diagonal pattern across walls: one shared vertical scale, per-wall horizontal charts, phase matched at corners; a fixed density (1500 px/m) left closure conflicts and 0 padding - allow a density range (550-1500) to solve closures. Wrap-padding for periodic maps; check 2 neighbor texels at edges for bilinear continuity. local: docs/agr/case_studies/SOSH1150_CONTINUOUS_WALL_UV_FBX.md (lesson).
- Re-projecting near-planar triangles changed phase; keep shared chart mapping when cutting; dedupe near-coincident cut points to avoid broken faces/area loss. local: docs/agr/case_studies/SOSH1150_CONTINUOUS_WALL_UV_FBX.md (lesson).
- Changing a face's material ID under a single atlas material does not change its texture - move its UVs into the target finish region too; check no shared UV verts between IDs before moving. local: docs/agr/case_studies/GLB_A_MAIN_ATLAS.md (lesson).
- Padding tools: GeoAGR `uvdilate.exe` drops alpha (RGBA -> RGB), rejects RGB input, overwrites input without `-o`, no radius control - preserve alpha/mask separately; do not treat ERM/normal as color. local: docs/agr/inventory/GEOAGR_13_63_REVIEW.md#GEN-12 (lesson).
- Tooling caveats: `density.ms` assumes 4096 and scene units without meters conversion; Andrew importer accepts UDIM 1001-1999 (wider than norm). local: docs/agr/research/max-workbench/REVIEW.md; local: docs/agr/decisions/ADR-0004-reuse-installed-toolchains.md (lesson).

## Job-level UV/texture lessons
- Continuous facade pattern: project world coords onto shared facade directions (not per-face normals - small normal differences broke phase); shift polygons by whole modules; UV = (band_origin + px_per_m*(proj - shift)) / atlas_size; horizontal faces use long-edge direction. Phase check tolerance 0.01 mm on shared verts. local: jobs/FACADES-ATLAS/STATE.md (lesson).
- Fixed-scale rigid unwrap cannot close complex corner loops; local horizontal scale deformation (0.84-1.05) only after user permits a density range. local: jobs/UV-CONTINUOUS/STATE.md (lesson).
- Out-of-band texel density caused by twisted/complex geometry: fix geometry, not UV scale. local: jobs/MASHI-LP/MASTER_TRIAL_REPORT.md (lesson).
- 0 px tile margin produced 12 196 AGR Checker margin failures. local: jobs/UV-CONTINUOUS/STATE.md (lesson).
- Facade atlas bands: 5 finish bands per 2048 atlas with 16 px guard margins; raster 80 px/m chosen (not a norm). local: jobs/FACADES-ATLAS/STATE.md (project decision).
- Map policy (one project): patterned finishes 4096, flat-color IDs as 256 placeholders; Diffuse = base color sRGB, no baked light; do not invent ERM/Normal without sources; legend colors are not exact RAL/NCS. local: jobs/REVIT-OPENINGS/outputs/diffuse-v001/README.md (project decision).
- Periodic textures: build with native procedural generator; AI image generators changed line counts/periodicity and output size (1254 instead of 2048 - keep true size, never upscale); check opposite edges pixel-equal and a 2x2 repeat; lines must continue across cassette joints. local: jobs/UV-CONTINUOUS/STATE.md; local: jobs/WINDOW-ATLAS/STATE.md; local: jobs/REVIT-OPENINGS/STATE.md (lesson).
- Having a UV channel does not prove the unwrap is finished. local: jobs/MASHI-LP/AUDIT_AND_PLAN.md (lesson).

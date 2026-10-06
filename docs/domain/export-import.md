# FBX export / DCC import

Keys: `reg p.N` = `Rasporyajenies19012026trebovaniya(2).pdf` page N. `local:` relative to the repo root (AGR knowledge base; AGR `docs/` lives in `docs/agr/`).
Note: the reference project has NO Unreal Engine import rules; delivery target is Moscow city information systems, DCCs are 3ds Max 2024/2026, Blender 4.4, SketchUp 2026, Revit.

## Regulation (delivery FBX)
- FBX 7.4 (2014) binary; 1 unit = 1 m, 1:1. reg p.4, 24.
- Triangulated before export; transforms reset/applied (VPM incl. collision). reg p.8 §3.11, §3.14; p.29 §3.17-3.18.
- NPM: PNG atlases embedded in FBX. VPM: PNG external, texture paths removed from FBX materials. reg p.9 §5.1; p.30 §4.2, §5.1.1.
- No empty/helper objects, cameras, animation keys, modifiers, extra layers (VPM single default layer); exception: lighting FBX has root helper empty. reg p.6 §1.3, p.28 §3.1-3.2, p.29 §3.11, p.38 §15.8.
- Texture names inside the editor identical to PNG files (NPM). reg p.12 §3.4.

## Project export practice
- Triangulate only a derived export copy; editable master stays quad; check both files. Optional separate triangulated FBX, quad FBX is the editable main hand-off. local: docs/agr/GEOMETRY_RULES.md; local: jobs/GROUND-PROJECTION/NPM_RESULT.md (project decision).
- Export-prep actions (new Standard material, rename, pivot, layer, Reset XForm, Triangulate, metadata cleanup) only on a managed export copy, never on the working object. local: docs/agr/research/max-workbench/REVIEW.md#Что требует (project decision).
- Export preset must be explicit per profile; installed presets are not delivery presets (BMAX Max-side preset = FBX2012; stock Max FBX = 2014, triangulate=true, embed=false; RizomUV bridge transport = ASCII, Y-up, no embed, units commented out). local: docs/agr/inventory/README.md; local: docs/agr/decisions/ADR-0004-reuse-installed-toolchains.md; local: docs/agr/inventory/MSE_REVIEW.md (lesson).
- Blender FBX used for Max hand-off: selection-only mesh, no triangulate/modifiers/animation, Z-up, FBX_SCALE_UNITS, path_mode=COPY, embed_textures=true, material simplified to diffuse. local: docs/agr/case_studies/SOSH1150_CONTINUOUS_WALL_UV_FBX.md (lesson; working hand-off, not a VPM delivery preset).
- Blender headless runs: `--background --factory-startup --disable-autoexec --python-exit-code 1`; never touch user's open scene. local: docs/agr/case_studies/SOSH1150_CONTINUOUS_WALL_UV_FBX.md; local: docs/agr/inventory/INTEGRATION_PLAN.md (project decision).
- Blender -> Max: final UV in FBX channel 1 so bitmaps use mapChannel 1; keep material IDs. local: jobs/FACADES-ATLAS/STATE.md (lesson).
- Large world coordinates through FBX gave up to 0.489 mm error and lost faces in thin regions; use local origin for float stability, keep world placement as transform. local: jobs/FACADES-ATLAS/STATE.md; local: jobs/GROUND-PROJECTION/RESULT.md (lesson).
- FBX UnitScaleFactor metadata for AGR not verified; check by re-import. finish_id face attributes and instancing do not reliably survive FBX; slot order, atlas hash and UVs survived Max round-trip. local: jobs/ORCH-OBR22-NPM/cli-runs/cursor-20261001-004/verdict.md (lesson).
- Max FBX export/prepare UI can modify meshes. local: docs/agr/inventory/ZAVOD_AND_MAX_PLUGINS_REVIEW.md#4 (lesson).
- Blender byte-identical FBX across runs not guaranteed (timestamps/IDs); compare geometry/UV invariants on re-import instead. local: docs/agr/decisions/ADR-0001-synthetic-scope.md (lesson).
- When saving appended Blender data, don't overwrite the used library file ("Cannot overwrite used library"); save under new name. local: docs/agr/case_studies/WINDOW_FRAMES_BOX_LIGHTS.md (lesson).
- Keep PNGs next to .blend with relative paths; pack/embed diffuse for FBX hand-off and also ship externally. local: jobs/OBR22-K02/STATE.md; local: jobs/UV-CONTINUOUS/STATE.md (lesson).

## Import pitfalls by source
- Revit FBX: no Material nodes; 0.3048 feet factor in matrices; names truncated by Blender; raw material-index warnings. local: jobs/OBR22-K02/STATE.md; local: jobs/REVIT-OPENINGS/STATE.md (lesson).
- Max -> Blender: duplicate Max names, some shapes import as Empty or vanish - an import discrepancy, not proof elements don't exist; object scales differ between imports. local: jobs/MASHI-LP/AUDIT_AND_PLAN.md; local: docs/agr/case_studies/MASHI_LP_SCENE_AUDIT.md (lesson).
- SketchUp: bitmap paths point to foreign machines - extract embedded pixels; unique maps may be fewer than materials; AABB of rotated nested groups is not a contour - walk vertices through matrix chain; disk SKP may differ from live unsaved scene; source inches -> meters. local: jobs/GLB-NPM/AUDIT_AND_PLAN.md; local: docs/agr/case_studies/GLB_AB_REFERENCE_AND_PLANES.md (lesson).
- SketchUp face persistent ID belongs to the definition and may be used outside target instance - exclude by hierarchy branch, not by face ID; recurse nested definitions (found 52 windows, not 50 direct children). local: docs/agr/case_studies/GLB_AB_REFERENCE_AND_PLANES.md (lesson).
- SketchUp composite window bbox spans lower window + spandrel + upper window: never replace a component by one plane over its full AABB; derive each visible opening from faces/instance matrices, one trial node first. local: docs/agr/lessons/SKETCHUP_COMPOSITE_WINDOW_OPENINGS.md (lesson).
- Ground FBX arrived 100x scale; confirm real dimensions. local: docs/agr/case_studies/GROUND_CONTOURS_AND_NPM.md (lesson).
- After geometry ops, verify raw FBX LayerElementMaterial per face (material contours preserved). local: docs/agr/case_studies/GROUND_CONTOURS_AND_NPM.md (lesson).

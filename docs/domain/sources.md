# Sources

Machine-readable layer: `standards/` (YAML profiles, validator spec, traceability) mirrors these
human-readable rules; `docs/domain/conflicts.md` numbers are referenced from `standards/*.yaml` `conflicts:`.

Origin: the rules were extracted on 2026-10-06 from the former AGR project (Codex), whose
knowledge base now lives in this repo. `local:` paths are relative to the repo root: AGR
`docs/` is in `docs/agr/` (Russian originals), `jobs/` and `standards/` keep their paths,
job `outputs/` are local-only (git-ignored). Full AGR history: `data/archive/*.bundle`.
The "Files read" list below keeps the original AGR paths.

## Regulation PDF
- `standards/source/Rasporyajenies19012026trebovaniya(2).pdf` (plain Git blob) - 56 pages, SHA-256 933f6b700c074d0db6b82030fc79d1dbe9db4a0067495ca716e0636acd544222 (per local: standards/source/source-lock.json). Order of Moscow DIT + Moskomarkhitektura 19.04.2023 No 64-16-192/23/769, App.1 NPM pp.1-19, App.2 VPM pp.20-50, App.3 GeoJSON pp.51-56.
- Byte copies exist under jobs/REVIT-OPENINGS/outputs/diffuse-v001/pytest-tmp/ and tmp/*/pytest-run-*/ (test fixtures; not used).
- Verification: text of all 56 pages extracted with poppler `pdftotext -enc UTF-8` (OCR text layer, noisy) and read for pp.1-14, 20-56 (pp.15-19 are figures with captions only). Pages 32 and 40 rendered with `pdftoppm` and checked visually (density formula = division; pivot = geometric center X/Y; fig.2.1 limits 800k/3M, 1-700 texture sets, 2-21 ZIPs). Every `reg p.N` citation in this folder refers to a page I read.

## Files read
- Root: README.md, AGENTS.md (process only), STATE.md, CURRENT_INDEX.md.
- standards/: NPM_STANDARD.yaml, VPM_STANDARD.yaml, DELIVERY_VALIDATOR.yaml, source/source-lock.json, project_overrides/README.md.
- docs/: DIGITAL_TWIN_AI_PROJECT_BRIEF.md, GEOMETRY_RULES.md, UV_RULES.md, BODY_SHELL_ADAPTER.md, EXTERIOR_ADAPTER.md, READINESS_REPORT.md (sections 1-4, 8, addenda), workflow/pipeline.md; grep-only: TASK_CONTEXT.md, EXPERIENCE_CAPTURE.md, ADAPTER_EXTRACTION.md, AGENT_WORKFLOW.md.
- docs/decisions: ADR-0001..0004, OBR22_FACADE_PDF_UV_TRIAL.md, OBR22_NPM_SCALE_V012.md, OBR22_PROCEDURAL_TEXTURES_V010.md, OBR22_SHARED_UV_V011.md.
- docs/lessons: SKETCHUP_COMPOSITE_WINDOW_OPENINGS.md.
- docs/case_studies: README.md, CASEFILE_INDEX.md, OBR22_ACCEPTED_WORKFLOW.md, SOSH1150_CONTINUOUS_WALL_UV_FBX.md, GLB_A_MAIN_ATLAS.md, GLB_B_MAIN_ATLAS.md, GLB_AB_REFERENCE_AND_PLANES.md, GLB_SKETCHUP_CONNECTION.md, FACADES_ATLAS_PARTIAL_ACCEPTANCE.md, GROUND_CONTOURS_AND_NPM.md, MASHI_LP_SCENE_AUDIT.md, WINDOW_FRAMES_BOX_LIGHTS.md.
- docs/inventory: NPM_VPM_MAP.md (full); GEOAGR_13_63_REVIEW.md, ZAVOD_AND_MAX_PLUGINS_REVIEW.md, MSE_REVIEW.md, INTEGRATION_PLAN.md, README.md (keyword grep + relevant sections).
- docs/research/max-workbench/REVIEW.md (sections 2-5, fixes list).
- .cursor/rules: geometry-quality.mdc, uv-reuse.mdc (others are process); .agents/skills/* grep-only (process).
- jobs (via a read-only sub-agent, all listed .md): A-MAIN-ATLAS, FACADE-SIGNS, FACADES-ATLAS, GLB-NPM (AUDIT_AND_PLAN, CLEARANCE_RULES, LOWER_FLOORS_SCOPE, STATE, TOWER_STAGE_V022/V023), GROUND-PROJECTION (NPM_RESULT, RESULT, STATE), MASHI-LP (AUDIT_AND_PLAN, MASTER_DIRECTIVE, MASTER_TRIAL_REPORT, MODELING_DIRECTIVE, MODEL_V002_REPORT, STATE), MESH-OPT-AUDIT/AUDIT, OBR22-K02/STATE (skimmed), ORCH-OBR22-NPM (STATE, cli-runs/cursor-20261001-004/verdict.md), REVIT-OPENINGS (STATE, outputs/*/README.md), SYNTH-001, UV-CONTINUOUS, WINDOW-ATLAS, WINDOW-FRAMES (README, STATE, BOX_LIGHTS_STATE). Job-derived bullets were not re-verified line-by-line by me.

## Deliberately skipped
- Source code (src/, tools/, adapters/, jobs/*/scripts, max/), schemas/*.json, tests/, .venv, tmp/.
- standards/traceability.json and docs/traceability.html (rule->page index of YAML fields; duplicative of YAML + PDF).
- docs/organization/*, docs/history/*, docs/examples/*, inventory JSON/CSV catalogs, .github, git/PR/agent-harness/MCP/Codex-workflow content (process, not domain).
- Large binary outputs (.blend/.max/.fbx/.png) - not inspected.

## Notable gaps for a new project
- No Unreal Engine import rules exist in the reference project (target = Moscow city IS); export-import.md covers FBX/DCC only.
- No real package ever passed official validation; coordinates/GeoJSON/UCX/lighting never produced on a real object.

# AGR knowledge base — index

The AGR knowledge base in `docs/agr/` (Russian originals, read-only). Open a document only through this index:
find the line for your question, then read that file. One line per tracked file.

## Root

| File | What it is | Read it when |
|---|---|---|
| `README.md` | English overview of the folder; `docs/domain/` wins on conflict | Orienting in the AGR archive or tracing a `local: docs/agr/...` citation |
| `DIGITAL_TWIN_AI_PROJECT_BRIEF.md` | Original production brief v0.1: goals, pipeline, architecture, stages DT-001…DT-033, risks | Needing the original requirements, stage IDs or intended architecture |
| `GEOMETRY_RULES.md` | User's mandatory modeling rules (2026-09-27): exterior-only BODY, clean quads, Shell, windows | Building or reviewing BODY/window geometry |
| `UV_RULES.md` | UV/texture reuse rules for NPM and VPM; NPM OKS exempt from Ground texel density | Laying out atlases/UDIM or judging NPM texture scale |
| `geometry-quality.mdc` | Short always-apply rule card summarising GEOMETRY_RULES | Quick reminder of clean-quad BODY rules |
| `uv-reuse.mdc` | Short always-apply rule card summarising UV_RULES | Quick reminder of atlas/UDIM reuse rules |
| `ADAPTER_EXTRACTION.md` | Connect-quads operation (`dt_ai.geometry.connect`) extracted from Obr22: API, checks, transfer limits | Subdividing quads by max side length or reusing connect code |
| `ADAPTER_REPORT.md` | AdapterReport contract: fields, required_checks_passed logic, delivery_passed always false | Writing or reading an operation report |
| `EXTERIOR_ADAPTER.md` | Exterior-surface prototype (`extract_exterior`): job contract, parameters, reproduction | Extracting exterior facade quads from a prepared grid |
| `BODY_SHELL_ADAPTER.md` | BODY/Shell adapter: exterior quads → inward Shell with reveals, no inner faces; Obr22 only | Building a shelled BODY from an exterior surface |
| `EXPERIENCE_CAPTURE.md` | Rule for recording a user-accepted result as a case study | User praises/accepts a result and a case must be written |
| `READINESS_REPORT.md` | Readiness audit 2026-09-26: NPM vs VPM, norm conflicts, app readiness, skills registry | Checking historical readiness, NPM/VPM differences or source contradictions |
| `traceability.html` | HTML table rule → PDF page → verification method (single-line file) | Tracing a profile rule to its regulation PDF page |

## decisions

| File | What it is | Read it when |
|---|---|---|
| `decisions/ADR-0001-synthetic-scope.md` | ADR: independent core and synthetic first example (2 m cube fixture) | Questions about SYNTH-001 scope or fixture-only approvals |
| `decisions/ADR-0002-source-discrepancies.md` | ADR: open discrepancies in source profiles (GeoJSON, UCX limit/gap, MB/GB, UDIM, origin, alpha, NPM density) | A regulation rule seems ambiguous or contradictory |
| `decisions/ADR-0003-contracts.md` | ADR: contract version 1.0.0, strict Pydantic validation, stable IDs, schema drift check | Changing data contracts or schemas |
| `decisions/ADR-0004-reuse-installed-toolchains.md` | ADR: reuse installed DCC toolchains (GeoAGR, SINTEZ Checker, BMAX…) instead of rewriting | Deciding whether to build or reuse an existing DCC tool |
| `decisions/OBR22_FACADE_PDF_UV_TRIAL.md` | Obr22 facade PDF legend, window instances, materials and VPM UV slicing trial | Mapping facade PDF materials or instancing windows (Obr22-like) |
| `decisions/OBR22_PROCEDURAL_TEXTURES_V010.md` | Obr22 v010 procedural brick/tile sizes and joints (user decision) | Choosing brick/tile module and joint sizes |
| `decisions/OBR22_SHARED_UV_V011.md` | Obr22 v011: user textures, shared NPM atlas and four VPM UDIMs | Building a shared NPM atlas plus per-texture UDIMs |
| `decisions/OBR22_NPM_SCALE_V012.md` | Obr22 NPM v012: scale matched to accepted VPM, no Ground density gate | Setting NPM texture scale relative to VPM |

## case_studies

| File | What it is | Read it when |
|---|---|---|
| `case_studies/README.md` | Registry of AGR accepted cases with short acceptance scopes | Looking for a prior case similar to the current task |
| `case_studies/CASEFILE_INDEX.md` | Index separating user acceptance from QA and publication; publication scope 2026-09-29 | Checking what a case's acceptance actually covers |
| `case_studies/TEMPLATE.md` | Template for a new case file | Writing a new case study |
| `case_studies/OBR22_ACCEPTED_WORKFLOW.md` | Accepted Obr22 typical floor workflow: geometry v008, VPM v011, NPM v012, scripts, math | Modeling a facade floor with clean quads, windows and UV |
| `case_studies/FACADES_ATLAS_PARTIAL_ACCEPTANCE.md` | Facades atlas: tile accepted, brick fix needed (v003/v004) | Building facade tile/brick atlases |
| `case_studies/GLB_SKETCHUP_CONNECTION.md` | GLB: SketchUp MCP read-only connection v001 | Connecting to SketchUp via MCP |
| `case_studies/GLB_AB_REFERENCE_AND_PLANES.md` | GLB towers A/B reference and window/basket simplification, v003–v006 additions | Simplifying windows/baskets from a SketchUp source |
| `case_studies/GLB_A_MAIN_ATLAS.md` | GLB A_Main in 3ds Max: accepted view, single RGBA atlas, ID/UV | Building a Max atlas from SketchUp textures |
| `case_studies/GLB_B_MAIN_ATLAS.md` | GLB B_Main: ID renumbering, UV per ID, white glass fix | Renumbering material IDs and atlas UV in Max |
| `case_studies/GROUND_CONTOURS_AND_NPM.md` | Ground: preserving contours, IDs and materials; mesh density not accepted; v008 iteration | Simplifying Ground terrain for NPM |
| `case_studies/MASHI_LP_SCENE_AUDIT.md` | MASHI-LP scene organisation and audit v001; later master TRIAL, QA not passed | Organising/auditing a large Max scene |
| `case_studies/SOSH1150_CONTINUOUS_WALL_UV_FBX.md` | SOSH1150 v006: continuous wall pattern UV and FBX package for Max | Continuous texture across walls or Blender→Max FBX handoff |
| `case_studies/WINDOW_FRAMES_BOX_LIGHTS.md` | Decorative frames: box lights on upper inner frame faces v002 (Blender) | Placing box lights on decorative frames |
| `case_studies/KPP1_VPM_NPM_V005.md` | KPP1: VPM+NPM from Revit v005, ~90% accepted; GeoJSON etc. open | Producing VPM/NPM from Revit with quads ≤4 m |
| `case_studies/PSU275_VPM_NPM_DELIVERY_V003.md` | PSU275 main building and OKS: VPM+NPM delivery-v003, mesh cleanup accepted | Cleaning/optimising quad masters for multi-OKS delivery |

## inventory

| File | What it is | Read it when |
|---|---|---|
| `inventory/README.md` | Tool inventory snapshot 2026-09-26: 73 tools, key findings (GeoAGR, SINTEZ, Octopus, BMAX) | Finding which installed tool already does a job |
| `inventory/catalog.json` | Machine-readable tool catalog: status definitions, 73 tools, 162 path evidences | Looking up a tool ID (MAX-01, BL-01…) programmatically |
| `inventory/catalog.csv` | Same tool catalog as CSV (id, application, purpose, status, limits…) | Filtering tools in a spreadsheet |
| `inventory/catalog.html` | Searchable HTML view of the tool catalog | Browsing tools interactively |
| `inventory/NPM_VPM_MAP.md` | Mermaid map of existing tools per NPM/VPM stage, with addenda | Choosing tools for a pipeline stage |
| `inventory/stage-map.json` | Proposed stage → DT tasks → tool IDs → gate mapping | Mapping stages to tools and gates programmatically |
| `inventory/INTEGRATION_PLAN.md` | Integration plan INT-001…INT-006 after inventory; proposal, not implemented | Planning integration of existing DCC tools |
| `inventory/GEOAGR_13_63_REVIEW.md` | GeoAGR 13.63 review: DLLs, ucx_check.exe, uvdilate.exe probes and limits | Using GeoAGR components, UCX check or UV dilation |
| `inventory/geoagr-13.63-evidence.json` | Hashes, comparisons and synthetic probe results for GeoAGR 13.63 | Verifying GeoAGR review claims |
| `inventory/MSE_REVIEW.md` | Static MSE decryption review; GeoAGR, RizomUV Bridge, Decal Projector, RappaTools notes | Questions about encrypted MAXScript or those Max tools |
| `inventory/mse-evidence.json` | QuickBMS decode evidence for installed MSE scripts | Verifying MSE review claims |
| `inventory/ZAVOD_AND_MAX_PLUGINS_REVIEW.md` | Review of zavod folder and Max plugin library: xView, Maf Tools, Collizii limits | Reusing Max scripts from zavod/plugin folders |
| `inventory/folder-followup-evidence.json` | Static scan evidence for zavod and Max plugin folders (files, archives, duplicates) | Verifying the zavod/plugins review |
| `inventory/coverage.json` | Inventory scan coverage: roots, file counts, exclusions, drives | Checking what the inventory did or did not scan |
| `inventory/duplicates.json` | 21 groups of byte-identical tool files | Checking whether two script copies are identical |
| `inventory/applications.json` | Installed DCC applications, versions and paths observed 2026-09-26 | Checking historical app versions/paths |
| `inventory/max-runtime.json` | 3ds Max 2024 runtime capabilities and loaded CUI/DLLs via MCP | Checking historical Max runtime setup |
| `inventory/fbx-runtime.json` | Max FBX exporter settings snapshot (FBX2014, triangulate on) | Checking default Max FBX export settings |
| `inventory/blender-preferences.json` | Enabled Blender add-ons parsed from userpref.blend (4.4, 5.0) | Checking which Blender add-ons were enabled |
| `inventory/autocad-menus.json` | AutoCAD 2025 CUIX menu containers and script references | Checking AutoCAD menu customisations |
| `inventory/octopus-bindings.json` | Octopus menu bindings in Max with command hashes | Finding Octopus buttons (A101LP, UCX, GeoAGR) |
| `inventory/packages.json` | Autodesk ApplicationPlugins packages (name, version) | Checking installed Autodesk plugin packages |
| `inventory/mcp-registrations.json` | MCP server registrations found in local client configs (2026-09) | Checking historical MCP server setup |

## research/max-workbench

| File | What it is | Read it when |
|---|---|---|
| `research/max-workbench/REVIEW.md` | Script review proposing a shared NPM/VPM Max tool, tab by tab | Designing a Max workbench or picking scripts per NPM/VPM step |
| `research/max-workbench/EXPANSION_2026-09-27.md` | Workbench expansion register: version 0.5 contents, next transfers, pipeline refinement | Continuing Max workbench development |
| `research/max-workbench/inventory.json` | Static index of 327 Max script/plugin files and 54 archives | Looking up a Max script file and its UI signals |
| `research/max-workbench/expanded-inventory.json` | Expanded index of 640 files across 12 roots | Finding script candidates beyond the first inventory |
| `research/max-workbench/scan-summary.txt` | Extension counts plus per-script rollout/button summary lines | Quick view of script UIs without opening them |

## examples

| File | What it is | Read it when |
|---|---|---|
| `examples/README.md` | Note on the SYNTH-001 reproducible example inputs and outputs | Running or understanding the synthetic example |
| `examples/readiness-evidence.json` | Evidence for the 2026-09-26 readiness audit: sources, tests, build, DCC | Verifying READINESS_REPORT claims |
| `examples/verification.json` | Recorded verification of the synthetic build (checks C001…, delivery_passed=false) | Seeing a sample verification record |

## lessons

| File | What it is | Read it when |
|---|---|---|
| `lessons/SKETCHUP_COMPOSITE_WINDOW_OPENINGS.md` | Lesson: a composite SketchUp window's bounding box is not an opening | Converting SketchUp window components to NPM planes/openings |

## local-orchestration

| File | What it is | Read it when |
|---|---|---|
| `local-orchestration/ENGINEERING.md` | Engineering practices for the AGR local harness (2026-10-03): module boundaries, skills, visual observation | Designing agent harness or workflow practices |
| `local-orchestration/RUN_EVIDENCE.md` | How to check a saved RunRecord with `tools/harness_status.py`; contract and limits | Resuming or reviewing a run from its RunRecord |

## workflow

| File | What it is | Read it when |
|---|---|---|
| `workflow/pipeline.md` | Flow of the first synthetic example (profiles → index-pdf → build → validate) and manual gates | Understanding the `dt` CLI pipeline steps or manual gate names |

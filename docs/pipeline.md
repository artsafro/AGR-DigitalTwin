# Pipeline stages

Status of each production stage. Rules: `docs/domain/`; tools: `docs/agents/CAPABILITIES.md`;
open work: `docs/backlog.md` (IDs in the last column).
Status: **proven** (accepted on a real object) · **partial** · **tool only** (no real
object yet) · **missing**.

## Building (OKS)

| # | Stage | Status | Where | Backlog |
|---|---|---|---|---|
| 1 | Register and analyze the source (Revit / FBX / SKP / DWG / PDF album) | tool only | skill `analyze-architectural-source`, Revit/AutoCAD/SketchUp MCP | P1 |
| 2 | Master building layer (elements, floors, openings, materials, sources) | missing | concept in `docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md` | P2 |
| 3 | BODY: exterior-only quad surface, cuts at corners/openings | proven (Obr22) | `src/dt_ai/geometry/exterior.py`, `connect.py`, `tools/build_exterior_surface.py` | — |
| 4 | Shell 0.4 m inward | proven (Obr22) | `src/dt_ai/geometry/shell.py`, `tools/run_body_shell.py` | C23 |
| 5 | Windows, stained glass, doors | partial | `tools/build_shell_windows.py`, `technical_library/window_atlas/`, REVIT-OPENINGS | P3 |
| 6 | Roof, decor, exterior equipment | missing | — | P4 |
| 7 | Materials registry and IDs | partial | `src/dt_ai/materials/registry.py` | — |
| 8 | NPM atlas (embedded PNG, shared regions by finish) | proven (Obr22 v012, GLB) | `technical_library/glb_atlas/`, `texture_tiles/` | C21 |
| 9 | VPM UV/UDIM + Diffuse/ERM/Normal maps | proven (Obr22 v011, SOSH1150 v006) | `technical_library/uv_continuous/`, `src/dt_ai/geometry/uv.py` | C27, C29, C33 |
| 10 | UCX collisions (VPM) | missing | probe `tools/probe_geoagr_ucx.py` | P5 |
| 11 | Lights FBX (VPM) | missing | — | P6 |
| 12 | Coordinates MSK-77, zero mark, pivot | missing | — | P7 |
| 13 | GeoJSON (VPM) | tool only (validator) | `src/twinqa/geojson.py` | P8 |
| 14 | FBX export + readback | proven | `tools/blender/fbx_readback.py`, `adapters/blender/bridge.py` | — |
| 15 | Package ZIP + validator V001–V017 | partial | `tools/qa/validate_package.py`, `src/dt_ai/validate/bundle.py` | Q1–Q4 |
| 16 | AGR Checker (SINTEZ) pass | missing | — | Q5 |

## Territory and environment

| Stage | Status | Where | Backlog |
|---|---|---|---|
| Ground (NPM-territory) | partial (contours/materials accepted) | `jobs/GROUND-PROJECTION/` | P9 |
| MAF (GroundEl) | missing | 3ds Max scripts inventory `docs/tools/max-scripts.md` | P10 |
| Flora | tool only | SpeedTree MCP | P11 |

## Beyond NPM/VPM

| Stage | Status | Backlog |
|---|---|---|
| Unreal import and interactive experience | missing (no rules yet) | U1–U2 |
| IFC | missing | U3 |

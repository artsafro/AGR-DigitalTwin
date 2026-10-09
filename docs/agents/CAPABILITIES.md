# Shared capabilities

What agents can rely on, across all worktrees. A tool or workflow counts as
available to other agents only after it is listed here **on `main`**.

Status:
- **WORKING** — validated end to end on the real application/data (date, by whom).
- **CONFIGURED** — installed and the server/tool starts; not yet validated on a live app.
- **IN BRANCH** — exists only in an unmerged branch; other worktrees do not have it.
- **BROKEN** — known not to work; see the backlog item.

## Publish a capability

1. Validate it on the real application (not only "server connected").
2. Commit the working solution in your branch.
3. Add or update its entry here: status, owner, branch, how to use, limits, date.
4. Ask for review and merge (`ROLES.md`: Codex integrates `main`; DCC tools are confirmed by Claude on real data).
5. Other worktrees pick it up with `git merge main` at the start of their next task.

## DCC / MCP

Rules for every DCC: confirm the MCP tools are present **and** the intended application and
document are live before work; start read-only; preserve source files and scenes. Saves,
exports, overwrites and other mutations need explicit task authorization and a versioned
output path. If the MCP or live session is missing, stop that application's work and report
the exact gap. An application not listed here has no MCP — do not claim live control or
substitute ad-hoc scripting.

### 3ds Max — `3dsmax-mcp`
- Status: CONFIGURED (server health check passed 2026-10-06; no live-scene operation validated)
- Owner: Claude (main) · scope: user (all projects)
- Server: cl0nazepamm/3dsmax-mcp v1.7.5, `C:\Users\artsafro\tools\3dsmax-mcp`; plugin in
  `C:\ProgramData\Autodesk\ApplicationPlugins\3dsmax-mcp`; `safe_mode = true`
- Use: 3ds Max 2026 (2024 is forced to run as administrator and may not connect from a
  non-elevated client). Skill: `3dsmax-mcp-dev`.

### Revit — `revit-bridge` (the live route)
- Status: CONFIGURED (Codex, 2026-10-06: `revit_status` answered from the running Revit 2025;
  a Revit API version query over the pipe timed out — needs a fresh read-only check)
- Server: `C:\Users\artsafro\tools\revit-bridge-mcp\src\index.js`, env `REVIT_BRIDGE_VERSION=2025`
  (copied 2026-10-06 from `Desktop\zavod\projects\revit-bridge`, which Cursor still uses;
  handshake lists 25 tools). Talks to the RevitBridge ("Cursor Bridge") add-in in
  `%AppData%\Autodesk\Revit\Addins\2025` over a named pipe — no TCP port.
- Registered for Codex and Antigravity (`.codex/config.toml`, `.agents/mcp_config.json`) from the
  `tools` path. Codex exported FBX from a QA fixture over the pipe (2026-10-06).
- Mutating tools (`open_document`, `export_fbx*`, `agr_export_fbx`, `load/unload/reload/repath`
  links) need explicit task authorization and versioned outputs.
- Sources are Revit 2022 files — open upgraded **copies**, never save over `data/sources/revit/*.rvt`.

### Revit — `revit-http-2025` (HTTP add-in route)
- Status: WORKING for inspection (Codex, 2026-10-06 18:38+): KenLP/RevitMCPServer v0.8.31 live on
  `127.0.0.1:7891`, 94 tools advertised; 20 calls across 19 tools passed on a separate fixture
  project, including a dry-run `create_level`. RVT persistence of edits not verified.
- Registered for Codex and Antigravity as `revit-http-2025` (port 7891). The Claude user
  registration `revit-2025` still sets 7891 — matches. Skill: `revit-mcp`.

### Revit twin — `revit-twin`
- Status: BROKEN (2026-10-06: connection closed). Its source was only on the former DT branch
  `feature/revit-workflow` (archive bundle); the Claude user registration points at that
  worktree. Not part of this repo — backlog H3.
- 2026-10-08 (Claude): still fails to connect (CONNECTION_CLOSED). The Revit spec extractor
  uses `revit-http-2025` instead (`docs/HARNESS_PLAN.md` §4).

### AutoCAD — `multiCAD`
- Status: WORKING (Codex, 2026-10-06, AutoCAD 2025): inspection on `flora.dwg`; on a fixture, seven
  entity types, edits, DWG/DXF save to a new path and reopen. Built-in screenshot is broken — use
  Computer Use for visuals.
- Server: upstream multiCAD in `%LOCALAPPDATA%\CodexMCP\MultiCAD\venv`, wrapped by
  `tools/mcp/multicad_stdio.py` (all COM calls on one thread). Install with
  `tools/mcp/constraints-multicad.txt`. Not a Revit connector. Skill: `autocad-mcp`.

### Blender — `blender`
- Status: WORKING on a fixture (Codex, 2026-10-06): official Blender Lab MCP 1.0.3, Blender 5.1.2,
  port 9877. Create/edit/material/UV, save/reopen, FBX export/import passed. MCP screenshots
  preceded an NVIDIA driver crash — use Computer Use for visuals. Runs arbitrary Python in the
  open scene: never on an unrelated production scene. Skill: `blender-mcp`.

### SpeedTree Modeler — `speedtree`
- Status: WORKING for file inspection and CLI FBX batch export (Codex, 2026-10-06, Modeler v10.0.1).
  Does not drive the GUI. Native geometry/scale/texture readback of exports still pending.
- Server: `tools/mcp/speedtree_server.py` (6 tools). Exports only to a new empty directory.
  Skill: `speedtree-mcp`. The 8-tool Antigravity variant (`harness/antigravity-support`) was
  not adopted.

### RizomUV — `rizomuv`
- Status: WORKING on a fixture (Codex, 2026-10-06, RizomUV 2024.1): load, unfold, optimize, pack,
  versioned OBJ/FBX save and readback. Cold `open_session` sometimes times out at the Link API
  limit. Server: `tools/mcp/rizomuv_server.py`. Skill: `rizomuv-mcp`.

### SketchUp
- Status: CONFIGURED (scripts only): Codex's Production extension worked on SketchUp 2026 from
  the former AGR folder's venv. Scripts are now in `adapters/sketchup/`; the venv was not moved
  — create one and re-verify before use (backlog H2).

Adapters and evidence log: `tools/mcp/README.md`, `tools/mcp/verification.txt`. All routes are
registered for Codex and Antigravity; Claude uses only its own user-scope registrations.

## Harness

### Guard hook — `.claude/hooks/guard.py`
- Claude Code: WORKING (PreToolUse in `.claude/settings.json`).
- Antigravity: CONFIGURED (`.agents/hooks.json` → `guard.cmd`; Antigravity-side run not validated).
- Codex: CONFIGURED (`.codex/hooks.json`; payload and "ask" support not validated — backlog H1).

### Skills sync — `tools/sync_skills.py`
- Status: WORKING (2026-10-06): `.agents/skills/` is canonical; the script regenerates
  `.claude/skills/` (vendored skills from `skills-lock.json` are skipped — Claude has user-level
  copies). `tests/test_skills_sync.py` fails when the copies drift.

### Herdr workspace tooling
- Status: CONFIGURED (moved from DigitalTwinProject; paths re-pointed, not re-run — backlog H6)
- `tools/herdr/` (layout repair, HUD, TOOLS/LOGS feeds for Claude and Codex, full refresh,
  pane swap, screenshot paste, cheat sheet); details in `docs/HERDR.md`.
- Herdr runs these from the main folder, so `main` must stay checked out there.
- Keys: Ctrl+B Shift+L layout · Shift+U refresh · I screenshot · Shift+H cheat sheet.

### Large files as links
- Status: WORKING (2026-10-06, Claude main; tested with a 60 MB file)
- `tools/git-hooks/link_large_files.py` via `.git/hooks/pre-commit`: new files over
  50 MB are committed as entries in `docs/sources/linked-files.json`. Toggle: Ctrl+B Shift+K.

## Pipeline core (src/dt_ai, technical_library, tools)

Environment: `uv sync`; tests `uv run pytest -q` — 284 passed, 1 skipped on 2026-10-06
(AGR + DT suites merged, incl. real Blender roundtrips).

### `dt` CLI — `src/dt_ai/`
- Status: WORKING on the synthetic job (`jobs/SYNTH-001`): `dt profiles check`, `dt schemas --check`,
  `dt build`, `dt validate`, `dt index-pdf`, `dt registry merge`. Real-object use goes through the
  accepted-case tools below. `passed` is always false in this version.
- Geometry adapters (Exterior, Shell, Connect) with `AdapterReport` and Blender readback:
  proven on Obr22 (`docs/cases.md`). RunRecord inspection: `tools/harness_status.py`
  (skill `run-evidence`).

### Spec extractor — `tools/source/measure_spec_blender.py` + `dt spec extract` / `dt spec merge-questions`
- Status: WORKING on synthetic data (Claude, 2026-10-08; issues #5, #16, #6, #7): Blender 5.1 dumps
  triangles and `LEVEL_<name>` helpers; `dt spec extract --dump --object --output` writes spec v0.1
  (`schemas/Spec.schema.json`), a report and `<spec>.questions.md`. Levels are input; roof confirmed at
  the top input level; strict full-height level contour (`contour_at_m` in object.json when it asks);
  kinks, rounded corners; typical floors written once (`typical_of` / `repeat_to`, `Spec.expanded_floors()`); openings from holes in the body or glass panes (`source`); door recesses from the floor are openings (`kind` door, or window when glass fills the height), relief <= 10 cm is no kink, panes of one frame are one opening with `panes`, an opening across a level is one record with `level_from` / `level_to` (spec v0.2, #31). Spec v0.3 (#36): opening = hole with frame (mesh: the reveal; Revit: frame or curtain wall, else the family box), glass as `glass_w` / `glass_h`, `depth_m` only as an exception. Vent grilles are openings of kind `grille` (Revit: window elements without a transparent material). `dt spec extract --tolerances` reads the `spec_extract` thresholds.
  `dt spec merge-questions --report --version --into jobs/<object>/questions.md` keeps one questions
  list per object with stable ids and kept answers.
- Limits: `window_type` is always null (no material ids in the dump; window library #4); no
  attachments; roofs: drainage slopes up to 10° are one roof
  (area-weighted height, ±10 cm), separate roof parts and caps are read (#9); steeper roofs are a question.
  First real run: KPP1 v005 spec v001 (`jobs/KPP1/STATE.md`). `object.json` may give `frames` per source. Pattern: `docs/domain/patterns/wall-from-contour.md`.
- Revit path, wall lines (Claude, 2026-10-08, #29; the bounding-box route of #10 was removed after it):
  `node tools/source/measure_spec_revit_twin.mjs <new-folder>` calls the TwinPack commands of the
  revit-http add-in (`twin_floor_manifest`, `twin_export_floor` with every wall function; not in the MCP
  tool list, called through `revitClient.callRevit`), writes `floor.json` + `reference.obj` per band and
  `twin-data.json`; `dt spec extract --dump <twin-data.json>` reads it (`dt_ai.spec.revit_twin`): walls as
  prisms on their location lines (any angle; curved walls from their real geometry), glass by material
  transparency, doors from records, attachments by the main-walls hull rule (user decision 2026-10-08). The
  document is not modified (flag checked before and after); files go only to the new folder.
  KPP1: contours equal to the mesh path (0.0 mm), `jobs/KPP1/spec-compare-v002.md`.
- Spec comparison (Claude, 2026-10-08, #11): `dt spec compare --a <spec> --b <spec> --tolerances
  benchmark/<id>/tolerances.json --output <cmp.json>` (+ `.md`): rows per criterion of HARNESS_PLAN §4
  with both values, threshold and reference side, contour difference regions; thresholds, reference
  sides and whether a verdict is given come from tolerances.json. KPP1: `jobs/KPP1/spec-compare-v001.md`.

### Operation library — `technical_library/`
- Status: WORKING per package README (Russian): `glb_atlas`, `uv_continuous` (UV v006),
  `window_atlas`, `texture_tiles`, `mesh_audit`. Scope of each = its accepted case.

## Delivery QA (tools/qa, src/twinqa, standards/)

### Standards layer — `standards/`
- Status: WORKING (2026-10-06; loader tests). One loader for both packages: `twinqa.profiles`.
- NPM/VPM profiles, validator spec V001-V017, 232-rule traceability, SHA-256 lock, regulation PDF
  (plain Git blob). Fields touched by `docs/domain/conflicts.md` carry `conflicts:` entries; checks
  report them as review. Machine-readable twin of `docs/domain/`.

### Package validator — `tools/qa/validate_package.py`
- Status: WORKING for archive composition, names, FBX header, VPM maps, UDIM sequence, GeoJSON
  (V001, V002 header, V007, V008 sequence, V011, V012); `--scene` adds V003/V004/V006/V008/V013 via
  Blender. Everything else is `not_run`; V015-V017 are manual.
- `py -3 tools/qa/validate_package.py <zip|fbx|geojson> [--profile npm|vpm] [--json] [--scene]`;
  exit 0 passed / 1 fail / 2 review or not_run left.
- Not yet: NPM embedded-atlas pixel rules (PNG bytes inside FBX), units, UCX (V010), texel density
  (V009), coordinates vs MSK-77 (V013/V014).

### FBX readback — `tools/blender/fbx_readback.py`
- Status: WORKING (2026-10-06; Blender 4.4 and 5.1 background, cube roundtrip tests)
- Triangles, polygon degrees, UV channels, UDIM tiles, mirrored UV, transforms, embedded images.

### Face overlap check — `tools/qa/check_clearance.py`
- Status: WORKING (2026-10-06; AGR boundary cases + FBX planes 3 mm apart)
- Near-parallel faces closer than 5 mm (profile), on faces JSON or FBX via
  `tools/blender/export_faces.py`. Hits need classifying (embed vs defect).

### 3ds Max production scripts (external)
- Status: CONFIGURED (inventory only, not run) — see `docs/tools/max-scripts.md` for which
  script serves Flora, Ground, MAF, UCX, lights, and their rule mismatches.

## Project workflows

### `analyze-architectural-source`, `validate-delivery` (project skills)
- Status: CONFIGURED (written against `docs/domain/`; not yet run on a real source)

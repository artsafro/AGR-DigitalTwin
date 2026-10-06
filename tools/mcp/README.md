# DCC MCP setup

> On `main` (merged 2026-10-06) the AutoCAD, RizomUV and SpeedTree routes run
> from `C:\Users\artsafro\AGR-DigitalTwin\tools\mcp`, not the task worktree.
> The SketchUp route and its scripts stay in `harness/dcc-mcp-routing`: they
> run from the old AGR project's venv, which `main` must not depend on.
> Current status per application: `docs/agents/CAPABILITIES.md`. The log
> below is the branch's verification record.

## Active scope correction, 2026-10-06

The user requests production-capable MCP routes for all listed DCCs, including
create/edit/save/export. Inspection is the connection prerequisite, not the
completion criterion. Lead owns application mutations. Verification may create
task-owned fixtures and versioned outputs under `tmp/mcp/`; preserve all open
production sources. Acceptance per app: identify session, exercise supported
write operations on a separate fixture, save/reopen and export/read back, native
visual evidence, actual Codex route verification, and agent instructions.
Do not disable permission controls globally or claim unsupported APIs.

Sequence: Blender production fixture (9877 live; Codex reload pending), then
replace SketchUp's restricted dispatcher with reviewed typed write support;
verify Revit and AutoCAD writes on independent fixtures; verify 3ds Max and
RizomUV; record SpeedTree's supported workflow/API gap. Stop a failing operation
after two repeats of the same cause and preserve evidence. MCP image capture in
Blender is pending stability after a driver crash; native Computer Use is the
current screenshot route.

This branch configures the local DCC routes in `.codex/config.toml` and
`.agents/mcp_config.json`. Paths under `C:\Users\artsafro` and `C:\Program
Files` are specific to this workstation. This script was exercised from the
task worktree; the SketchUp, AutoCAD and RizomUV adapter commands target this
worktree. Retain it until those routes are deliberately relocated and verified.
Codex reads project MCP routes only from a trusted project after restart.

### Production continuation, 2026-10-06

Latest reload/fix checkpoint (supersedes older pending entries below):
- Actual Codex SpeedTree tools loaded: all six called successfully; new FBX
  export passed exit/header/size/hash checks with unchanged source/preset.
  `tmp/mcp/speedtree-mcp-20261006/export-reload-v001/`; native geometry readback
  applies to the previous export, not this new file.
- Actual Codex Rizom first launch/version, OBJ/FBX loads, UV calls, saves and
  managed close passed; quad FBX readback matched packed OBJ geometry/UVs.
  Native screenshot showed quad in 3D and UV panes. Reopening hung before GUI
  launch. Its exact stalled Python server was stopped after its GUI was closed.
- Multi-island cube exposed semantic bugs: Unfold/Optimize defaulted to Edge,
  Pack omitted required Translate=true. Corrected these and moved native Link
  to a per-session main-thread helper with startup/request deadlines and bounded
  shutdown. Wait for the owned app's Link port before connecting. Operation
  timeout preserves GUI and reports uncertain completion; never repeat blindly.
- Corrected configured route passed all ten tools and three open/close cycles;
  cube stage outputs and FBX readback in
  `tmp/mcp/rizom-worker-20261006T190343Z/report.json`. Final check in
  `tmp/mcp/rizom-worker-20261006T190534Z/` also passed 23 calls. Cube visual
  checkpoint was interrupted by the user's Escape; it remains pending.
  After restart actual Codex status/open/version/load/pack/save/close/reopen
  succeeded: `tmp/mcp/rizom-reload-20261006/codex_restart_report.json`.
  Final managed session is connected with no mesh loaded. Reload gate passed.
  Timeout reconnect recovery, complex meshes/locks/multi-UV remain pending.


- Blender fixture create/edit/material/UV/bevel, save/reopen, FBX export/import
  and native visual inspection passed. Evidence:
  `tmp/mcp/blender-production-20261006T174642Z/recovery_report.json`.
- SketchUp Production extension installed with previous files backed up under
  `tmp/mcp/sketchup-production/installed-backup`; all 27 installed package hashes
  matched. Typed wrapper excludes eval and exposes versioned save/export. Four
  primitives, transforms/material/layer, SKP save and OBJ/DAE/STL exports passed:
  `tmp/mcp/sketchup-production/qa-v001/report.json`. Saved SKP opened in a
  separate native window; bridge readback there remains pending. Production
  source `ГЛБ для НПМ` stays open. Both QA/source bridges currently stopped.
- AutoCAD compatibility module fixes spline signature, output path reporting and
  genuine DWG/DXF SaveAs. Seven entity types, five edit operations, layer create,
  save and native reopen passed; entity property summaries matched both formats.
  `tmp/mcp/autocad-production-20261006/compat_report.json`; native screenshot
  confirmed reopened DXF and spline. Fixture INSUNITS=4. Original flora remained
  open; no operations targeted it. Property summaries are not complete topology.
- Rizom adapter now has ten tools including OBJ/FBX load and versioned save.
  Separate plane fixture load/UV operations/OBJ save/reload/FBX export passed;
  independent OBJ readback preserved XYZ/topology and confirmed UV changes.
  `tmp/mcp/rizom-production-20261006T175214Z/report.json`. FBX/native visual gates
  and broader island/lock coverage remain pending.
- Current client processes need Codex reload for changed SketchUp, AutoCAD,
  Blender and Rizom routes, then actual tool calls. Native Computer Use returned
  repeated `foreground window did not report a process id` during saved-SKP
  bridge switching; stop that input path until refreshed runtime works.
- 3ds Max fixture passed object/material/transform/UVW modifier, MAX save/reopen,
  FBX export and controlled import with a new node. Evidence:
  `tmp/mcp/max-production-20261006/report.json`. Imported mesh retained 8 vertices,
  12 faces, material and bounds within 0.00001 system units. `smart_import`
  recenters imported assets; do not use it to preserve architectural placement.
  UV coordinate comparison and native visual inspection remain pending; the
  agent viewport failed to redraw. Fixture system units are meters.
- SketchUp independent review requires opening a separate working copy and
  verifying its active path before edits: save_copy does not activate that copy.
  The wrapper now propagates upstream errors as MCP failures for typed calls.
- Reload check: actual Codex Blender call identifies the saved roundtrip scene;
  AutoCAD connect/status and new document-info operation succeed. SketchUp bridge
  remains stopped; Rizom managed session requires launch.
- Revit separate fixture passed 20 HTTP calls across 19 tools, plus named-pipe
  FBX export. Created level/grid/wall/floor/opening/views/schedule/sheet/note/line;
  moved/rotated wall, changed type/parameter, deleted QA line, exported PDF, and
  proved dryRun rollback by a subsequent level query. Evidence:
  `tmp/mcp/revit-production-20261006/report.json`. RVT v001 saved before later
  edits; current QA document retains later unsaved changes. User confirmed working
  behavior and deferred SaveAs/reopen on 2026-10-06. Do not claim persistence of
  later edits or all 94 tools tested. Original detached project remains open.
- SpeedTree now has a narrow six-tool file/batch adapter. Configured stdio
  inspection/export checks passed on builtin Broadleaf; existing-file and wrong
  extension guards passed. Evidence: `tmp/mcp/speedtree-mcp-20261006/report.json`.
  Local Blender 5.1.2 imported the FBX (10435 vertices, 12298 faces, two UV
  layers, one material) and saved a new readback blend. Report:
  `tmp/mcp/speedtree-mcp-20261006/native_readback_report.json`. Builtin sample
  normal/opacity paths are empty; texture/scale/visual acceptance remains pending.
  Blender MCP CLI timed out; separate direct local CLI import passed.
  It does not edit the active GUI or support ST/game exports. Actual Codex reload
  and visual verification remain pending. Use
  `.agents/skills/speedtree-mcp/SKILL.md`. Another worktree's broader adapter was
  reviewed, but its unsafe export-success and GUI-kill behavior were not adopted.
- Next: SpeedTree reload/readback, Rizom launch diagnosis and remaining app
  checks. User stopped Computer Use with Escape during the preceding turn;
  no further UI actions were attempted in that turn.

## Revit routes

- `revit-bridge` connects to the active Revit 2025 Cursor Bridge through a
  Windows named pipe; it does not use a TCP port. The project route points to
  `C:\Users\artsafro\Desktop\zavod\projects\revit-bridge`.
- `revit-http-2025` is the broad RevitMCPServer/RevitMCPAddin route on
  `127.0.0.1:7891`. The server's stdio handshake reports 94 tools. Use this
  route for broad read-only model inspection; use `revit-bridge` for its
  separate supported operations/fallback.
- Live verification on 2026-10-06 after rebuilding/reloading Cursor Bridge:
  `revit_status`, `get_revit_version`, `get_active_document_info`,
  `list_open_documents`, `list_views`, `list_3d_views`, `list_categories`,
  `list_revit_links`, `get_selected_elements`, and `get_model_statistics`
  returned successfully through the named pipe. `create_test_3d_view` with
  `confirm:false` was rejected by its safety gate. The bridge log recorded
  `external_event=Accepted`, `ExternalEvent.Execute entered`, and successful
  dispatch. These checks do not establish that every tool is verified.
- The Revit add-in source hotfix at
  `C:\Users\artsafro\Desktop\zavod\projects\revit-bridge` records the
  `ExternalEvent.Raise()` result and cancels requests that time out before
  execution. That external source folder has no Git repository. Its Release
  DLLs were copied to the installed add-in; the installed SHA-256 values match
  the built DLLs.
- Live verification on 2026-10-06 found the RevitMCPAddin responding on
  `127.0.0.1:7891`; the old project setting `7890` was incorrect. The MCP
  stdio route connected to RevitMCPServer v0.8.40 and listed 94 tools. Thirty
  distinct read-only calls succeeded across health/document info, worksets,
  views, categories, levels, wall/floor types, families/types, sheets, rooms,
  spaces, materials, phases, templates, links, tags, doors, model-health recipe,
  category-filtered elements, element info/geometry/parameters, and UniqueId
  lookup. An empty-ID room-containment request returned an error; it needs real
  family-instance IDs to verify. This does not cover every tool or any
  write/export operation; inspect schemas and guards before use.
- Integration check opened a workshared RVT through the bridge, which detaches
  it from central. Revit reported `isModified=true`; it was not saved. Close
  that diagnostic session without saving unless the user directs otherwise.

## SketchUp initial inspection record (superseded configuration)

The following records the earlier restricted installation. Current agents must
use the Production route and `.agents/skills/sketchup-mcp/SKILL.md`; the earlier
read-only menu and restrictions below are historical, not active instructions.

- `sketchup` is pinned in the project MCP config and points to the MCP adapter
  under `C:\Users\artsafro\.AGR_Project\adapters\sketchup`; its Ruby
  extension bridge is expected on `127.0.0.1:9876`. The prepared extension is
  the restricted read-only build for SketchUp 2026. Do not replace it with the
  unrestricted upstream RBZ.
- Live check on 2026-10-06: the installed bridge was started through Windows
  Computer Use. Codex MCP returned compatible Python/Ruby versions 0.3.1.
  Eight distinct inspection tools succeeded: `get_version`, `get_model_info`,
  `list_layers`, `list_components`, `get_component_info`, `find_components`,
  `get_selection`, and `get_viewport_screenshot`. The active architectural
  model had 18 root entities, 14 root groups/components, and 27 layers.
  The saved 1024x590 viewport PNG was read back visually. A repeatable stdio
  check made nine successful calls, including model readback; path, counts,
  layers, and bounds matched before/after inspection.
- The extension has no auto-start. After restarting SketchUp, choose
  `Extensions → MCP Server (Read Only) → Start Server` and verify `get_version`.
  Agents can use the Windows `@oai/sky` runtime in `node_repl` for this action.
  Run `probe_sketchup_readonly.py` with the configured SketchUp Python to save
  fresh report/PNG evidence under ignored `tmp/mcp/`.
- The Python server advertises write/eval tools although the installed Ruby
  extension is intended to reject them. Agents must use only the read-only
  methods listed in `.agents/skills/sketchup-mcp/SKILL.md`; do not use
  `eval_ruby`, edit, delete, material, transform, joint, or export operations.

## Installed components

### Blender connection continuation, 2026-10-06

The first actual Codex Blender inspection hit `localhost:9876` and returned an
invalid protocol response; this port belongs to the working SketchUp bridge.
Blender 5.1.2 was launched through Computer Use with its default unsaved scene.
The installed Blender Lab MCP 1.0.3 was enabled. Its preference port was changed
in the visible UI to 9877; both project MCP configs now set `BLENDER_MCP_PORT=9877`
and `BLENDER_MCP_HOST=127.0.0.1`, with the installed 5.1 executable for CLI tools.
The user approved Allow Online Access; it was enabled through Computer Use.
The configured stdio route returned 26 tools and ten successful calls covering
seven scene/object inspection tools and two image tools. Evidence:
`tmp/mcp/blender-20261006T173913Z/report.json` and PNGs. A subsequent native UI
action revealed a crash: `EXCEPTION_ACCESS_VIOLATION` in `nvoglv64.dll`.
The crash followed MCP screenshots; causality is not established. Preserve the
crash log in that evidence folder and use Computer Use for screenshots until
MCP screenshot stability is separately established.

After recovery, explicitly saved Preferences (port 9877, Online Access enabled,
Auto Start enabled). Seven distinct inspection tools passed again. Normal quit
and relaunch then confirmed automatic bridge startup and eight successful calls
through those seven tools: `tmp/mcp/blender-20261006T174305Z/report.json`.
The scene remained the unsaved default Cube/Camera/Light scene. No production
input was loaded, edited, saved or exported. Follow
`../../.agents/skills/blender-mcp/SKILL.md` for the agent workflow.

Pending: reload Codex to replace the currently loaded Blender port 9876, then
verify through actual Codex tools. Configured-route stdio checks do not close
that integration gate. Mutations, CLI variants and rendering remain untested.

### AutoCAD live check, 2026-10-06

Scope: connect the existing AutoCAD 2025 session, verify drawing/layer/block/entity
inspection, preserve the source, then document the route for agents. Lead owns
the live session; no drawing edits, save, or export were authorized for this check.

- Actual Codex `multiCAD` tools detected the running AutoCAD and connected.
  Status changed from disconnected to `autocad: connected`.
- Five distinct MCP tools succeeded in inspection modes: `manage_session`,
  `manage_files`, `manage_layers`, `manage_blocks`, and `export_data`.
  The open drawing was `flora.dwg`; results included 17 layers, seven block
  definitions, and property data for 158 model-space entities. A named block's
  definition and reference transforms were read; one reference had no attributes.
- Repeated JSON entity extraction matched the initial result exactly. No source
  edit/save or drawing export was requested. These results do not establish full
  geometry, drawing units, or write-tool correctness.
- The `screenshot` operation failed with `Could not find window for autocad`.
  Windows Computer Use independently found the AutoCAD window. Its first
  app-access approval timed out; after user confirmation, native capture
  succeeded and showed the same `flora.dwg` landscaping plan. The MCP capture
  operation itself remains faulty; use Computer Use for visual inspection.
- Agent workflow: `.agents/skills/autocad-mcp/SKILL.md`. Raw local evidence:
  ignored `tmp/mcp/autocad-20261006/report.json`. Native capture was inspected
  in this session. Connection and inspection are verified; drawing mutation
  and file exports remain untested.
- Final checks exposed a thread-related connection defect in the upstream
  server: its thread-local COM adapter could report disconnected on another
  FastMCP worker; reconnect also failed once on `AutoCAD.Application.Documents`.
  The project route now uses `multicad_stdio.py`, which registers the same seven
  upstream tools and serializes their execution on one COM thread. It does not
  start the optional web dashboard or write an installation-folder log.
- `probe_multicad_readonly.py` verified this configured route through a fresh
  stdio client: 22 successful calls, four connected-status cycles, concurrent
  read requests, and identical entity data before/after. Evidence:
  `tmp/mcp/autocad-20261006T165908586872Z/report.json`. The restricted shell
  could not see the COM session; authorized local COM execution passed.
- Restart Codex to load the changed project command, then confirm actual
  `manage_session` status after inspection calls. This integration gate passed
  after the user's restart: actual Codex calls completed three inspection/status
  cycles with `autocad: connected`, and process inspection confirmed the project
  wrapper command. Next: Blender connection check. Keep this worktree path until the
  route is deliberately relocated after integration.

- Blender 5.1.2 is installed alongside Blender 4.4.0. Its official MSI was
  signed by Blender Foundation; SHA-256:
  `7D1BB468057A3AC8FD19809E90544F6064CC215053B7732CC8A1CCC83B651AB5`.
- Blender Lab MCP add-on/server 1.0.3 comes from official tag
  `2cea8d566dde07fbac28a61d698909d69724e853`. The add-on is installed and
  enabled. The Python MCP server is in the isolated user environment
  `C:\Users\artsafro\AppData\Local\CodexMCP\BlenderLab103\venv`.
- RizomUV MCP is a narrow project adapter over the installed RizomUVLink API;
  see `rizomuv_server.py`. It exposes session status/open/close, version, OBJ
  load, unfold, optimize, and pack. It does not expose generic Lua or `Eval`.
- AutoCAD multiCAD MCP runs from the isolated user environment
  `C:\Users\artsafro\AppData\Local\CodexMCP\MultiCAD\venv`. The server's
  current imports require MCP SDK 1.x and the standalone FastMCP 3.x package;
  `constraints-multicad.txt` caps both major versions.

## Verification record

- Blender 5.1.2 and 4.4.0 version commands succeeded. Blender MCP stdio
  handshake listed 26 tools.
- RizomUV session safety smoke check: status was disconnected, `get_version`
  failed without launching an app, `open_session` returned version
  `2024.1.59.gbb13aa72`, `get_version` succeeded, and close returned the same
  managed PID. Two concurrent `open_session` calls returned the same PID.
  Subsequent cold-start attempts timed out at RizomUVLink's 10-second limit;
  those failures cleared MCP session state. Treat RizomUV launch as intermittent
  until a fresh native app session confirms it.
- During initial setup Blender's `bpy.app.online_access` was `False`; the add-on would not
  start its localhost socket until Blender Online Access is enabled. Port 9876
  was closed during verification. No scene was opened or changed.
- RizomUV 2024.1.59 MCP handshake listed 8 tools. A managed empty application
  session opened, returned its version, and the MCP closed that same process.
- AutoCAD multiCAD MCP stdio handshake listed 7 tools. It reported
  `disconnected` and no CAD process running. During setup, MCP SDK 2.3 failed
  because the server imports the removed `mcp.server.fastmcp` API. Pinning to
  MCP 1.30.0 and FastMCP 3.4.8 fixed startup. Its optional dashboard also
  reported port 8888 in use during the local smoke check; MCP stdio remained
  responsive.
- During initial discovery no supported SpeedTree Modeler MCP/API was found in the installed Modeler
  10.0.1 files or official docs. The official [SpeedTree documentation
  outline](https://docs.speedtree.com/doku.php?id=outline) describes the SDK
  and runtime integration; it does not establish direct Modeler automation.
  Subsequent local CLI export verification established the file/batch route
  recorded above; it does not establish an API for editing the active GUI model.

## Setup constraints and safety

- Blender's official MCP executes Python in Blender and its add-on declares a
  local network permission. Blender's own documentation warns that generated
  code can affect local data. Inspect the open file first, use a versioned copy,
  and require explicit task authorization before edits, saves, exports, or other
  filesystem/network operations.
- Rizom UV tasks modify the in-memory document. Save only to a new, versioned
  output after explicit task authorization and verify the saved result.
- Check `get_session_status`/CAD session status before working. An installed or
  configured server alone does not prove a live DCC connection.
- Blender Online Access was enabled with the user's approval on 2026-10-06.
  This setting alone does not establish a live bridge; inspect the scene first.

Temporary upstream verification copies were removed after installation and
readback; recovery provenance and exact paths are recorded in
`cleanup-manifest.md`.

Handshake outputs and commands are retained in `verification.txt`.

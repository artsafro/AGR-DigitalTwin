---
name: blender-mcp
description: Inspect the open Blender 5.1.2 or later scene through the project's official Blender Lab MCP route and diagnose connection gaps.
---

# Blender MCP for project agents

## Connect and identify

1. Use `blender`, the installed Blender Lab MCP 1.0.3 route. Project client
   configs set `BLENDER_MCP_HOST=127.0.0.1`, `BLENDER_MCP_PORT=9877`.
   Port 9876 belongs to SketchUp. CLI `--host`/`--port` bind the HTTP transport;
   they do not configure the Blender extension bridge.
2. Confirm Blender 5.1.2 or later and the intended open scene through the
   native app. Call `get_blendfile_summary_path_info`, then
   `get_blendfile_summary_datablocks` and `get_objects_summary`.
   These take no arguments. Confirm source path, saved/dirty state and objects
   before relying on the connection. A blank path means an unsaved scene.
3. Require outer MCP success and inner JSON `status="ok"`. Connection failure
   or a protocol response from SketchUp is not usable Blender data.
4. If disconnected, inspect Preferences > Add-ons > MCP: enabled, Host
   localhost, Port 9877, Auto Start checked. Online Access must be enabled in
   System preferences; changing that preference requires user authorization.
   Click Start MCP Bridge Server and confirm Server is running. Explicitly
   Save Preferences after setup. Changing client config requires Codex reload
   and a fresh actual Codex tool call, even if a separate stdio probe passes.

## Inspection tools

Seven scene inspection tools were verified on the default unsaved scene:
`get_blendfile_summary_path_info`, `get_blendfile_summary_datablocks`,
`get_blendfile_summary_missing_files`,
`get_blendfile_summary_of_linked_libraries`,
`get_blendfile_summary_usage_guess`, `get_objects_summary`, and
`get_object_detail_summary` with `name` from the live inventory.
Empty missing-file/library lists on that scene do not prove populated-source
coverage. Inspect fresh tool schemas before using other tools.

## Safety and recovery

- The extension executes Python with the app's rights; it has no effective
  sandbox. Prefer typed inspection tools. Review any Python before execution;
  require task authorization for edits, saves, exports, filesystem or network
  operations and save only to a versioned output. Setup permission does not
  authorize production-scene changes.
- `_for_cli` tools can launch another Blender process and are not substitutes
  for identifying the open scene. Inspect their behavior before use.
- The two MCP image tools returned images on 2026-10-06, followed by a native
  NVIDIA `nvoglv64.dll` access violation. Causality remains unknown. Use native
  Computer Use captures meanwhile; do not repeat that capture path on a source
  scene to establish coverage. Preserve crash evidence before recovery.
- Production fixture QA exercised Python creation, transforms, material, UVs,
  bevel modifier, native save/reopen, FBX export/import and saved roundtrip.
  Native Computer Use confirmed the imported blue beveled object. Evidence:
  `tmp/mcp/blender-production-20261006T174642Z/recovery_report.json`.
  Rendering and CLI variants remain untested; the catalog is not full coverage.
- After `open_mainfile`, a timer callback may have `bpy.context.window=None`.
  Select a real `bpy.context.window_manager.windows` entry and use
  `bpy.context.temp_override(window=window, scene=scene, view_layer=...)`
  for operators. Reidentify the loaded file before continuing after a failure.

Connection evidence and pending Codex reload are recorded in
`tools/mcp/README.md` and `tools/mcp/verification.txt`.

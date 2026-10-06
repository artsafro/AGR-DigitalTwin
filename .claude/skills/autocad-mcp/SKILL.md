---
name: autocad-mcp
description: Inspect and edit AutoCAD drawings through the project's multiCAD MCP route, then save and reopen versioned DWG/DXF outputs.
---

# AutoCAD MCP for project agents

## Connect and identify

1. Use `multiCAD`. Inspect its actual tool schemas before calling operations.
   The project route runs `tools/mcp/multicad_stdio.py`: upstream tools
   execute on one COM thread. After changing the route, restart Codex and
   verify the newly loaded route. The old server can report disconnected when
   a different worker thread checks its thread-local adapter.
2. Call `manage_session` with `operations=[{"action":"status"},{"action":"check_running"}]`
   encoded as a JSON string. If AutoCAD is running but disconnected, call
   `operations=[{"action":"connect"},{"action":"status"}]`.
   `connect` can launch an application when none is running; do not launch an
   unintended CAD application. Stop if the detected CAD type is unexpected.
3. Call `manage_files` with `operations="list"` and confirm the intended drawing.
   This returns names, not full source paths or units. With several drawings,
   do not infer the active document from list order; establish its identity
   through the native app before using current-document operations.
4. Every batch response has `total`, `succeeded`, and per-operation `success`.
   Require all intended operations to succeed. `isError=false` alone is not
   evidence of success; screenshot failed inside a nominal MCP response.

## Verified inspection operations

- `manage_files`: `list`.
- `manage_layers`: `list`, `info` (newline-separated operations).
- `manage_blocks`: `list`, `info|ACTUAL_BLOCK_NAME|both`,
  `get_attrs|ACTUAL_BLOCK_REFERENCE_HANDLE`.
  Obtain names/handles from the live results; do not invent them.
- `export_data`: `format="json", scope="all"` returns entity data without
  saving an export. Inspect count before retaining the complete response.
  The data is a property summary, not full CAD topology, nested geometry, or
  proof of units. Zero/absent measurements can reflect unsupported properties.
- Repeat relevant inspection and compare results after a task.

## Capture and limitations

- On 2026-10-06, `manage_session` action `screenshot` failed with
  `Could not find window for autocad` although the COM connection worked.
  Do not claim a screenshot exists from that response.
- Use Windows Computer Use (`@oai/sky` through `node_repl`) for native inspection:
  select a uniquely returned AutoCAD window, activate it if minimized, and
  capture its state. Respect runtime app-access approval; an approval timeout
  leaves visual verification pending.
  A retry after user confirmation succeeded for the actual AutoCAD 2025 window;
  Computer Use is the verified capture fallback for this workstation.
- Production fixture QA verified line, circle, rectangle, text, arc, polyline
  and open cubic spline creation; move/rotate/scale, color/layer assignment,
  layer creation, DWG/DXF save and native reopen. Seven entity property summaries
  matched before/after both formats; this is not full topology verification.
  Evidence: `tmp/mcp/autocad-production-20261006/compat_report.json`.
- Require an authorized task, confirmed document/units, a new versioned output
  and native readback. Do not test on a production source merely for coverage.
  Never undo user work as cleanup.

## Production file operations

The project wrapper imports `multicad_compat.py`; reload Codex after changes.
Use JSON strings for the added `manage_files` operations:

```json
[{"action":"info"}]
[{"action":"open","filepath":"C:/existing/fixture_v002.dwg"}]
[{"action":"save","filepath":"C:/project/output/fixture_v003.dxf","format":"dxf"}]
```

- `info` returns actual full path, saved state, INSUNITS and model-space count.
  The tested fixture had INSUNITS=4 (millimeters); check each source separately.
- Save supports DWG/DXF only, with explicit native SaveAs types. Use a new path
  under this worktree or configured export directory. Parent must exist and
  extension must match. Overwrite/symlink destinations are rejected; output
  returns actual path, size and SHA256. PDF needs a separate plot workflow.
- Upstream save discarded requested paths and used a DWG default for DXF. Do
  not use the old route's success/path as evidence of a valid file export.
- Spline supports open cubic fit-point curves with endpoint chord tangents;
  closed and noncubic requests are rejected before creation.

## Runtime and evidence

The configured isolated environment is under
`C:/Users/artsafro/AppData/Local/CodexMCP/MultiCAD/venv`.
Keep `mcp<2` and `fastmcp<4` using `tools/mcp/constraints-multicad.txt`.
See `tools/mcp/README.md` and `verification.txt` for scoped results.
Run `tools/mcp/probe_multicad_readonly.py` with the configured multiCAD Python
for connection continuity and data readback; it saves ignored `tmp/mcp/` evidence.
The shell probe needs access to the user's Windows COM session. A sandbox probe
can report no running CAD even when the native app is visible; preserve that
error and use the authorized local COM execution context.
The single worker cannot interrupt a hung COM operation. Restart the MCP server
for recovery; do not close AutoCAD, discard user work, or assume cancelling a
request cancels a running operation. Check the document again before retrying.
Report connection, drawing identity, successful operations, and pending gates
separately. Configuration and historical checks do not prove a fresh session.

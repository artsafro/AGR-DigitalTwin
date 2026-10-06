---
name: revit-mcp
description: Inspect and edit Revit BIM documents through the project MCP routes; verify authorized changes and versioned exports.
---

# Revit MCP for project agents

## Connect and verify

1. Use `revit-http-2025` for broad Revit model information. It is configured
   for Revit 2025 at `127.0.0.1:7891` and currently exposes 94 tools.
2. Before relying on the connection, call `revit_ping` and
   `revit_get_document_info`. Confirm that a document is active and report the
   document identity and whether Revit says it is modified.
3. If `revit-http-2025` is missing, ask the user to trust/reopen the project or
   restart Codex, then check `/mcp`. Do not silently substitute a guessed port.
4. Use `revit-bridge` only for operations supported by that separate named-pipe
   server. Do not assume its tools and `revit-http-2025` tools are interchangeable.

## Read model information

- Prefer read-only tools such as `revit_get_document_info`, `revit_get_views`,
  `revit_list_categories`, `revit_list_elements`, `revit_get_element_info`,
  `revit_get_parameter`, `revit_list_levels`, `revit_list_families`,
  `revit_list_sheets`, `revit_list_rooms`, `revit_list_materials`,
  `revit_get_worksets`, `revit_get_linked_files`, and
  `revit_get_model_health`.
- Use pagination or a narrow category/filter when listing elements. Avoid
  unbounded dumps when a targeted query can answer the question.
- Read the tool schema and required arguments before every call. An error from
  missing or invalid arguments does not prove the MCP route is down.
- Treat the 94-tool catalogue as availability, not proof that every operation
  has been tested. Report which calls actually succeeded.

## Protect the document

- Begin with inspection only. Do not create, modify, delete, save, export, or
  reload model data unless the user's task explicitly authorizes that operation.
- Before an authorized mutation, identify the exact active document and intended
  output. Preserve source files; save/export only to an explicitly authorized,
  versioned destination. Read back the result and verify the relevant model delta.
- Never save a diagnostic RVT opened by an MCP check when it is detached from
  its workshared source and Revit reports it as modified. Do not treat that
  detached document as the production central model or close it as cleanup
  without checking with the user.
- Keep Revit calls serialized when they can affect the same document or session.

## Verified production subset, 2026-10-06

- A separate new non-workshared project passed 20 HTTP calls across 19 tools:
  level/grid/wall/floor/opening, 3D and plan views, schedule/sheet/text/detail
  line creation, wall move/rotate, section box, parameter write/read, wall type
  change, deletion and PDF export. A second level creation used dryRun: response
  committed=false and subsequent level inventory confirmed the level was absent.
- Named-pipe `export_fbx` exported the explicit QA 3D view to a new FBX path.
  PDF/FBX signatures and sizes were independently checked. Evidence:
  `tmp/mcp/revit-production-20261006/report.json`.
- RVT v001 was saved through native UI before later parameter/type/deletion
  edits. The current QA document has later unsaved edits. User accepted the
  working behavior and explicitly deferred save/reopen QA; this does not prove
  persistence of those later edits. Preserve the open original detached document.
- No RVT save/new-project tool exists in the current catalogs. Use native UI
  for these steps; do not invent an MCP save call. SaveAs/reopen and exported
  FBX geometry readback remain unverified. Section-box response reports
  verify.status=not_supported; independently inspect its bounds if required.
- This subset supplements earlier inspection coverage; 94 exposed tools are
  not 94 tested tools. Families, MEP, joins and other advanced writes need their
  own representative fixture checks when used.

## Report evidence

State the route, active document, exact tools called, successful results, and
any failed or untested operations. Separate read access from mutation/export
verification. A live ping or visible tool catalogue alone is not end-to-end
proof of every tool.

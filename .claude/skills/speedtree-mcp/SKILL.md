---
name: speedtree-mcp
description: Inspect SpeedTree SPM files and presets, then batch-export versioned FBX files through the project MCP adapter.
---

# SpeedTree MCP for project agents

1. Use `speedtree`, backed by `tools/mcp/speedtree_server.py`. Call
   `installation_info` and verify the executable. This route reads files and
   launches separate CLI exports; it does not attach to or edit the active GUI.
2. Page through `list_templates` and `list_presets` with limit 1..100. Select
   exact absolute SPM/INI paths; no fuzzy names or guessed presets are accepted.
3. Call `inspect_spm` and `inspect_preset`. Cached triangle counts describe
   stored metadata, not a fresh geometry evaluation. Inspect preset units,
   grouping, LOD and texture options before export. No generic code execution,
   model edits, GUI launch or forced-close tool is exposed.
4. For an authorized export, create an empty versioned directory inside this
   task worktree. Call `export_tree(source_path, preset_path, output_path)` with
   a new absolute `.fbx` path. Timeout is 1..120 seconds. The entire parent must
   be empty to protect sidecars; links and existing files are rejected.
5. Require both protocol success and `success:true` in the result. Inspect
   exit code, FBX signature, generated file hashes and unchanged input hashes.
   After failure retain partial files and choose a new directory for the next
   justified attempt; do not overwrite them or blindly repeat failed operations.
6. Import the exported FBX into the intended DCC and check geometry, materials,
   UVs, units and visual appearance. Exporter success does not prove delivery.

## Verified subset, 2026-10-06

All six tools passed through the configured stdio route on installed
Games/Broadleaf.spm with Games/Generic FBX.ini. Export produced a nonempty FBX
and STMAT sidecar; input hashes were unchanged. Existing output and wrong input
extension were rejected as MCP errors. Evidence:
`tmp/mcp/speedtree-mcp-20261006/report.json`.

Local Blender 5.1.2 imported the FBX: 10435 vertices, 12298 faces, two UV layers
and Sample_Mat. Saved readback: `native_readback_v002.blend`; report:
`tmp/mcp/speedtree-mcp-20261006/native_readback_report.json`. The builtin sample
has empty normal/opacity texture paths; texture completeness, scale equivalence
and visual acceptance remain unverified. Blender's MCP CLI tool timed out;
direct local Blender CLI import succeeded and is separate from MCP integration.
Actual Codex reload and visual inspection remain pending.
Only FBX is supported by this adapter; ST, ST9, growth, seed changes and active
GUI editing are not provided. Configuration paths are local to this machine;
retain this worktree until the route is relocated and verified.

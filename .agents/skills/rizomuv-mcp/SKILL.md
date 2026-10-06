---
name: rizomuv-mcp
description: Load, unwrap, pack and save versioned OBJ/FBX meshes through the project's RizomUVLink MCP adapter.
---

# RizomUV MCP for project agents

1. Use `rizomuv`. Call `get_session_status`; `open_session` creates a separate
   MCP-managed window. It does not attach to an arbitrary user's open document.
   Confirm managed PID, version and connection before relying on it.
2. Inspect the intended source and obtain task authorization for UV changes.
   `load_mesh` accepts existing OBJ/FBX; `load_obj` is the OBJ-specific alias.
   Confirm `loaded_path` in status after load. Never infer units from OBJ.
3. Use typed `unfold_visible`, `optimize_visible`, `pack_visible` operations.
   Unfold/Optimize explicitly target islands; Pack explicitly enables translation.
   Allowed working sets are `Visible`, `Visible&UnLocked`, `Selected`.
   Inspect islands and locks before choosing the working set. No generic
   `Eval` or arbitrary Lua is exposed.
4. Save with `save_mesh` to a new absolute OBJ/FBX path in a fresh versioned
   directory. The parent must exist; overwriting and symbolic-link destinations
   are rejected. A fresh directory also protects exporter sidecar files.
5. Read back the output, compare geometry/topology, UVs and units, then inspect
   the result in a native app. Require outer MCP success and meaningful inner
   results. A successful operation alone does not prove UV quality.
6. `close_managed_session` closes only this server's owned process. Save the
   authorized result first. Server restart loses ownership of a previous process;
   never claim it reattached automatically or kill another user's session.
7. Native Link runs in a separate helper on one thread. Startup and requests have
   bounded waits. A request timeout means its outcome is unknown: inspect the
   managed document before retrying any edit. Only the helper is terminated on
   an operation timeout; the GUI/document is preserved. `open_session` can reconnect
   a replacement helper to the still-owned application without repeating edits.

## Verified scope

On 2026-10-06 actual Codex calls connected, loaded FBX, saved/reloaded OBJ and
closed the managed application. Quad FBX readback preserves XYZ, faces and UVs.
Evidence: `tmp/mcp/rizom-reload-20261006/`. Native screenshot showed the saved quad
in both 3D and UV panes. The earlier cube exposed missing Island/Translate
parameters; its UV result failed acceptance despite successful transport calls.

The corrected configured route passed all ten tools and three open/close cycles:
`tmp/mcp/rizom-worker-20261006T190343Z/report.json`. Six-island cube stage outputs
and FBX readback are alongside it. Earlier direct native lifecycle calls hung;
the worker now isolates native lifetime and thread affinity. After restart,
actual Codex load/pack/versioned save/close/reopen/status passed; evidence:
`tmp/mcp/rizom-reload-20261006/codex_restart_report.json`. Native cube visual
checkpoint was interrupted by user Escape and remains pending. Locks,
multi-UV sets, complex production meshes and recovery after timeout remain
unverified; a ten-tool catalog does not mean the whole native API is exposed.

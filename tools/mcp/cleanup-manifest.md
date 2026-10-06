# Temporary MCP setup files cleanup record

These task-owned source copies were inspected, installed or verified, and then
removed from the task worktree to keep third-party source and temporary files
out of the project commit. User-level installed components remain in place.

| Exact path | Classification and reason | Replacement/recovery | Retention and action |
| --- | --- | --- | --- |
| `C:\Users\artsafro\DigitalTwinProject\tmp\codex-dcc-mcp\downloads` | Temporary official Blender Lab MCP 1.0.3 ZIP and extracted review copy. ZIP SHA-256: `A7A9DA816192502E5A0A202A396444E266B47D8FC4F74AD4698048BD43040707`. | Installed add-on and server are recorded in `README.md`; recover from upstream tag `2cea8d566dde07fbac28a61d698909d69724e853`. | Removed after install and Blender CLI validation. |
| `C:\Users\artsafro\DigitalTwinProject\tmp\codex-dcc-mcp\vendor\blender_mcp` | Temporary upstream Git clone used for source/security review; clean at revision `2cea8d566dde07fbac28a61d698909d69724e853`. | Re-clone official repository at the recorded commit; installed artifacts remain in the user profile and isolated venv. | Removed after source review and installation. |
| `C:\Users\artsafro\DigitalTwinProject\tmp\codex-dcc-mcp\Scripts\mcp\__pycache__` | Python bytecode cache created by `py_compile`; generated, reproducible task cache. | Recreated from `rizomuv_server.py` by Python when needed. | Removed after compile verification. |

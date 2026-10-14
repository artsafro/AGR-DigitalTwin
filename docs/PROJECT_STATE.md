# Project state

Last updated: 2026-10-15 (after #139). Edit rule: `docs/agents/WORKFLOW.md`, "Project state".

## Goal

NPM and VPM deliveries per the Moscow regulation (later IFC) for buildings, Ground, MAF, Flora and UCX,
plus the Unreal experience. Now: close the delivery gates of KPP1 and PSU275, and make the harness
agent-ready (spec `docs/prd/agent-ready-harness.md` = #118, tickets #119-#134).

## In production

No official delivery has passed yet. Accepted partial results: `docs/cases.md`.

| Object | Version | Status | Open gates |
|---|---|---|---|
| KPP1 | VPM + NPM v005 (`jobs/KPP1/REPORT.md`) | accepted by the user as reviewed (~90 %) | GeoJSON, MSK-77, district code, manual SINTEZ items; v007 (inset roof, spec match with Revit) waits for user acceptance; real `run_all.sh` run on a new version |
| PSU275 | VPM + NPM delivery-v003 (`jobs/PSU275/REPORT.md`) | accepted by the user as reviewed; predates the inset-slab rule (mark, do not touch) | GeoJSON, MSK-77, district code, address, УКЭП, Ground, racks, transformer massing, window frame density, manual SINTEZ items |
| OBJ03 | by source modules v011 / v012 (local outputs) | **unsuccessful** (user 2026-10-14, #117); `from_source` stays experimental | do not resume without the user |

Before any new model is reported as passing: a normals check, topology on every mesh incl. decor, the
independent checker and the user's visual review (#117).

## Harness

Green, verified locally (CI on GitHub does not start: account locked for billing, 2026-10-14):
- `uv run pytest -q` (short `--basetemp` on this machine), `uv run dt profiles check`, `uv run dt schemas --check`.
- Benchmarks: B01 / B02 / B02t 9/9 etalon and engine model.
- Spec extractor (spec v0.7), engine `from_spec`, checkers `tools/qa/check_geometry.py`, `check_decor`.
- `pipeline_gate` (pre-commit + PreToolUse, fails closed), guard hook, skills sync test.
- Context rotation (`/handover`, `/takeover`); subagents source-inspector, pattern-librarian, bench-runner,
  independent-checker (verified on B01); Kanban board `artsafro/projects/1`.

Not green: K01 (KPP1) 6/9 with known engine stops; K02 waits for the user's `source.max` and `etalon.max`;
`mesh-reader` configured, not test-called; Codex and Antigravity guard hooks (H1); desktop and interactive
CLI hooks (#110); checker blind spots of #117 (#126).

## Next step

1. User: choices page C7, C8, C10, C25 (`docs/domain/conflict-choices-2026-10-09.md`); KPP1 v007
   acceptance; K01 open items (`benchmark/bench-k01-kpp1/README.md`); cut K02 `source.max` + `etalon.max`.
2. Claude: harness wave 1 - #121 transcripts at handover; #138 decision ids outside the docs; then the
   blocked-by graph (`gh issue list --label harness`).
3. Claude: decor PR 4 (K02 run), intake IN2-IN8, MH3, engine gaps, #56; extractor follow-ups #21-#24,
   #28, #34, #37, #45 when they block a benchmark.
4. Claude: PSU275 racks and massing; export-safety rerun on KPP1 and PSU275 (backlog H13).
5. Codex (when back): Q6, H1, H2, Q3; with Claude Q7. Antigravity: H4.

## Links

- Pipeline stages: `docs/pipeline.md`; unsolved work: `docs/backlog.md`; open conflicts: `docs/domain/conflicts.md`.
- Roles and git fallback: `docs/agents/ROLES.md`; task loop and rotation: `docs/agents/WORKFLOW.md`.
- Tools, MCP routes, machine and repository: `docs/agents/CAPABILITIES.md`.
- Sources: `docs/sources/README.md`; plan and benchmarks: `docs/HARNESS_PLAN.md`, `benchmark/`.
- Per-object state: `jobs/<ID>/STATE.md`; current task handoff: `docs/HANDOFF.md`.
- History: `git log --merges` and the pull requests; decisions: `docs/decisions.md` (lookup order in `AGENTS.md`).

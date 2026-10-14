# Decision log

Every dated user decision, one line each, sorted by date. The line is a pointer, not the rule: the full text
lives where "Applies to" says, and that text carries the id (`[D012]`). ADRs (`docs/adr/`) stay for
architectural forks; conflicts keep their `C<N>` in `docs/domain/conflicts.md` and are logged here when decided.

Add a decision: next free id, the date the user decided, one sentence, the file or pattern it applies to, and the
source (PR, issue or `chat`). Put `[D<n>]` next to the decision in that file. Superseded decisions stay, with
"superseded by D<n>". Format and references: `tests/test_decisions.py`.

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D001 | 2026-10-06 | Roles: Claude leads 3D/DCC production, Codex code and organization, Antigravity supports both | `docs/agents/ROLES.md` | chat |
| D002 | 2026-10-06 | Blender Online Access enabled | `tools/mcp/README.md` (Blender) | chat |
| D003 | 2026-10-07 | While Codex is unavailable Claude takes its git and harness duties (branches, PRs, merges, state after merges) | `docs/agents/ROLES.md` | chat |
| D004 | 2026-10-07 | A name says what the thing does; object codes live only in data, never in shared names | `docs/agents/NAMING.md` | chat |
| D005 | 2026-10-07 | Branches `claude/npm-models-school-kpp-ec9ced`, `claude/modest-ptolemy-684fb7`, `feature/kpp1-ground` are not merged on purpose | `docs/backlog.md` H12 | chat |
| D006 | 2026-10-07 | PSU275 target profile: NPM and VPM | `docs/sources/psu275.md` | chat |
| D007 | 2026-10-07 | PSU275 geometry reference is Revit only; missing parts from the FBX | `docs/sources/psu275.md` | chat |
| D008 | 2026-10-07 | PSU275: work in the detached Revit 2025 copy; absolute mark from drawings, no MSK-77 yet; first-floor bounds by Claude | `docs/sources/psu275.md` | chat |
| D009 | 2026-10-07 | C1: the VPM triangle table is the hard limit; project target <= 150 000 triangles per OKS FBX in VPM as in NPM | `docs/domain/conflicts.md` #1, `docs/domain/npm-vpm.md` | chat |
| D010 | 2026-10-07 | C2: GeoJSON as the checker - OKS `FNO_code` mandatory, `act_AGR` may be empty, never invent | `docs/domain/conflicts.md` #2 | chat |
| D011 | 2026-10-07 | C3: UCX budget by the checker formula (< 50 000 -> 15 000, else min(ceil 5 %, 100 000)) | `docs/domain/conflicts.md` #3, `docs/domain/validation.md` | chat |
| D012 | 2026-10-07 | C5: NPM placeholders 128x128 (Metallic/Roughness only), VPM 256x256 | `docs/domain/conflicts.md` #5 | chat |
| D013 | 2026-10-07 | C6: NPM deliveries carry no normal map | `docs/domain/conflicts.md` #6 | chat |
| D014 | 2026-10-07 | C12: binary units (1 GB = 1024 MiB) | `docs/domain/conflicts.md` #12 | chat |
| D015 | 2026-10-07 | C13: `Glasses` GeoJSON as the checker (`[]` or one object keyed by glass material) | `docs/domain/conflicts.md` #13 | chat |
| D016 | 2026-10-07 | C14: VPM lights only in `SM_<Address>_Light.fbx`; any non-mesh in the main FBX fails | `docs/domain/conflicts.md` #14 | chat |
| D017 | 2026-10-07 | C19: VPM pivot as the checker (origin 0,0,0, bbox centre within 10 %, shared origin, Z = project zero) | `docs/domain/conflicts.md` #19 | chat |
| D018 | 2026-10-07 | C20: encode the missing YAML rules as the checker plus regulation limits | `docs/domain/conflicts.md` #20 | chat |
| D019 | 2026-10-07 | C21: no alpha in any NPM image; opacity as a separate `_o_` map | `docs/domain/conflicts.md` #21 | chat |
| D020 | 2026-10-07 | C26: cut VPM quads to about 4 x 4 m (1024 px/m; adapter default 3.9 m) | `docs/domain/conflicts.md` #26 | chat |
| D021 | 2026-10-08 | Strict level contour: with no full-height shape the extractor stops and the user gives `contour_at_m` | `docs/HARNESS_PLAN.md` §4 | PR #19 |
| D022 | 2026-10-08 | Projections not over the full storey height never change the contour; they are questions; `bands` only with a benchmark need and an ADR | `docs/HARNESS_PLAN.md` §4, pattern `contour-niche` | #6 |
| D023 | 2026-10-08 | Roof slopes up to 10 deg are one roof (area-weighted height); steeper parts are a question | pattern `parapet` | #9 |
| D024 | 2026-10-08 | A door recess from the floor (>= 1.9 m high, 0.7-3 m wide, one straight mouth) is an opening, not a contour notch | patterns `wall-from-contour`, `contour-niche` | #31 |
| D025 | 2026-10-08 | Spec opening = the hole with its frame; glass as `glass_w` / `glass_h` / `panes` | pattern `wall-from-contour` | #36, PR #39 |
| D026 | 2026-10-08 | Revit attachments by the main-walls hull rule | `docs/agents/CAPABILITIES.md` (Revit twin path) | PR #35 |
| D027 | 2026-10-09 | A projection or groove in section with depth and height both <= 0.10 m is relief, not a question | patterns `wall-from-contour`, `contour-niche` | PR #46 |
| D028 | 2026-10-09 | An inward shell offset that self-intersects (niche, corner) stops and asks | patterns `contour-niche`, `non-90-corner` | PR #48 |
| D029 | 2026-10-09 | The 0.20 m frame and 0.10 m depth thresholds stay, in `spec_extract` of the benchmark tolerances | pattern `wall-from-contour` | PR #40 |
| D030 | 2026-10-09 | Vent grilles are openings of kind `grille` | pattern `vent-grille` | PR #40 |
| D031 | 2026-10-10 | C24 final: one opening depth per building; `npm_min` plane at full depth, `mid` at half; supersedes the same-day reverse | `docs/domain/conflicts.md` #24, `conflict-choices-2026-10-09.md`, pattern `opening-plane` | PR #52 |
| D032 | 2026-10-10 | Every slab (roof in a parapet, terrace) is inset - hole + plate, joint required, a solid slab fails; etalons that differ are fixed | pattern `roof-inset-plane`, benchmarks | PR #63 |
| D033 | 2026-10-10 | `plate_gap_m` / `plate_overlap_m` are building parameters of the spec, default 5 / 20 mm | pattern `roof-inset-plane` | PR #64 |
| D034 | 2026-10-10 | A benchmark etalon never comes from the engine; its README names the author | `docs/HARNESS_PLAN.md` §6, `benchmark/` | PR #61 |
| D035 | 2026-10-10 | Terrace = a floor-step ledge with a parapet; spec v0.4 `terraces: [{level, parapet_h_m}]` | pattern `terrace` | PR #59 |
| D036 | 2026-10-10 | Pattern `terrace` proven on benchmark `bench-b02t-terrace` | pattern `terrace`, `patterns/INDEX.md` | PR #61 |
| D037 | 2026-10-10 | Floor step: engine order step -> oblique wall -> terrace; ledge with the roof ID, soffit with the facade ID | pattern `floor-step` | PR #55 |
| D038 | 2026-10-10 | Markup helpers plan approved (HARNESS_PLAN §14, MH1-MH3), after the terrace | `docs/HARNESS_PLAN.md` §14, pattern `markup-helpers` | PR #60 |
| D039 | 2026-10-10 | Revit levels mapped by `object.json` `revit_levels`; `LEVEL_roof` = base + offset + volume / area | pattern `markup-helpers` | PR #69 |
| D040 | 2026-10-10 | A Blender B01 etalon made by Claude by hand from the brief proves the Blender route | pattern `markup-helpers` | PR #68 |
| D041 | 2026-10-10 | B01 first green run recorded as a case (a benchmark result, not a model acceptance) | `docs/cases.md` | PR #51 |
| D042 | 2026-10-11 | OD1: default opening depth 0.4 m; a source with no depth takes it, listed as "depth by default", never 0 | `docs/domain/conflicts.md` #24, pattern `opening-plane` | PR #76 |
| D043 | 2026-10-11 | Intake plan approved (HARNESS_PLAN §15, IN0-IN8); no own skill, extend `analyze-architectural-source` | `docs/HARNESS_PLAN.md` §15 | PR #70 |
| D044 | 2026-10-11 | The colleague's OBJ03 job is a lesson: honest mixed mode with numbered engine gaps, `pipeline_gate`, job scripts committed before running | `docs/HARNESS_PLAN.md` §16, `docs/cases.md` | PR #73 |
| D045 | 2026-10-11 | Facade decor: one solid per element inset 0.02 m, body not cut, 5 mm off openings; projection <= 0.10 m (inclusive) is texture | pattern `facade-decor-inset` | PR #73 |
| D046 | 2026-10-11 | The first decor benchmark is a real facade fragment (K02, source and etalon separate files); synthetic B03 deferred | `benchmark/bench-k02-decor-fragment`, `benchmark/bench-b03-decor` | PR #73 |
| D047 | 2026-10-11 | K01: KPP1 material IDs from `jobs/KPP1/materials.json`; geometry thresholds = HARNESS_PLAN §5 starting numbers | `benchmark/bench-k01-kpp1` | PR #72 |
| D048 | 2026-10-12 | Split decor pieces merge: one section, one axis, gaps <= `plate_gap_m` x 12 = 0.06 m | pattern `facade-decor-inset` | PR #74 |
| D049 | 2026-10-12 | Decor ids by material: metal 16-20, plaster / stone / tile 26-30 | pattern `facade-decor-inset` | PR #76 |
| D050 | 2026-10-12 | A free-standing decor column is a box >= 2 m high, 0.05-1.5 m a side, its bottom on a `LEVEL_*` | pattern `facade-decor-inset` | PR #74 |
| D051 | 2026-10-12 | A projection over 0.8 m is no decor: an attachment candidate, listed in the report | pattern `facade-decor-inset`, `docs/backlog.md` EG2 | PR #74 |
| D052 | 2026-10-12 | One question per type: one kind and cross-section repeated is one question with count and positions | pattern `facade-decor-inset`, `docs/HARNESS_PLAN.md` §7 | PR #74 |
| D053 | 2026-10-12 | Decor elements meet by a run-in, not a gap (horizontal main, vertical subordinate; corner rule) | pattern `facade-decor-inset` | PR #75 |
| D054 | 2026-10-12 | Rule 3: a storey contour is its mid-storey section; a change only in the 0.3 m under the next level is the slab edge | `docs/HARNESS_PLAN.md` §4 | PR #81 |
| D055 | 2026-10-12 | Rule 4: `roof.parapet_thickness_m` measured as a mitred inset; unreadable -> the default, marked | `docs/HARNESS_PLAN.md` (spec v0.6) | PR #81 |
| D056 | 2026-10-12 | Rule 5: the extractor never substitutes a value; `--collect-stops` lists every stop, writes no spec | `docs/HARNESS_PLAN.md` §4 | PR #80 |
| D057 | 2026-10-12 | `%TEMP%\pytest-of-artsafro` stays inaccessible; pytest runs with a short `--basetemp` | `docs/agents/REVIEW_CHECKLIST.md` | PR #79 |
| D058 | 2026-10-12 | `pipeline_gate` does not cover a compromised environment (for example a fake `py` on PATH) | `docs/agents/CAPABILITIES.md` (Pipeline gate) | PR #79 |
| D059 | 2026-10-13 | One parapet thickness per building; a terrace parapet takes the same | `docs/HARNESS_PLAN.md` (spec v0.6) | PR #81 |
| D060 | 2026-10-13 | Rules 1-2: a panel facade without a shell is read by panels (`source_class: panelised`, `slabs`) | `docs/HARNESS_PLAN.md` §4 | PR #83 |
| D061 | 2026-10-13 | Roof screen enclosures are body silhouette: spec v0.7 `roof_structures`, `npm_min` planes and top, roof ids | pattern `roof-screen-enclosure` | PR #92 |
| D062 | 2026-10-13 | The building weld `weld_m` is 3 mm | pattern `roof-inset-plane` | chat |
| D063 | 2026-10-13 | A slab opening with both sizes under 0.7 m is no body opening; listed in the report | pattern `roof-inset-plane` | PR #83 |
| D064 | 2026-10-13 | OBJ03 decision 3a: OD1 applies; a source with no depth is no longer a question | `conflict-choices-2026-10-09.md` C24 | chat |
| D065 | 2026-10-13 | Five read-only subagents; only the main agent writes, commits and decides | `docs/agents/WORKFLOW.md` (Subagents) | PR #86 |
| D066 | 2026-10-13 | Disputed geometry: look first (isolated renders, views, sizes), then classify | `docs/agents/WORKFLOW.md` (Subagents) | chat |
| D067 | 2026-10-13 | Review procedure: rounds by risk, ceiling 3; P1 fixed in the PR, P2 to issues; merge on the user's command | `docs/agents/REVIEW_CHECKLIST.md` | PR #86 |
| D068 | 2026-10-14 | Events make skills and subagents mandatory (triggers table) | `docs/agents/WORKFLOW.md` (Triggers) | PR #107 |
| D069 | 2026-10-14 | Rule of three: repeated procedures become code, a skill or a pattern; the agent only proposes | `docs/agents/WORKFLOW.md` (Rule of three) | PR #107 |
| D070 | 2026-10-14 | Context rotation: `/handover` -> `/clear` -> «продолжай» or `/takeover` at a task boundary or 40-50 % context | `docs/agents/WORKFLOW.md` (Context rotation) | PR #107 |
| D071 | 2026-10-14 | Kanban board on GitHub Projects over the issues | `docs/agents/KANBAN.md` | PR #114 |
| D072 | 2026-10-14 | An auto-named worktree branch is renamed before its first commit; the agent proposes, the user confirms | `docs/agents/NAMING.md` | PR #107 |
| D073 | 2026-10-14 | OBJ03 by `from_source` is unsuccessful; `from_source` stays as an experimental start | `docs/cases.md`, `docs/agents/CAPABILITIES.md` | #117 |
| D074 | 2026-10-14 | Primitive first: reduction, not reproduction; the parts list is confirmed before any build | pattern `primitive-first` | PR #106 |
| D075 | 2026-10-14 | OBJ03: thin plates are opening ids; the storey band frame runs round the contour; pier steps 0.07-0.10 m kept | pattern `primitive-first` | PR #106 |
| D076 | 2026-10-14 | Silhouette test at 0.07 m in five views | pattern `primitive-first` | PR #106 |
| D077 | 2026-10-14 | About 12 section points describe a silhouette; the budget per group is the job's (OBJ03: total 150 000) | pattern `primitive-first` | PR #106 |
| D078 | 2026-10-14 | Nothing of the source is dropped: unreducible pieces kept as source faces, listed | pattern `primitive-first` | PR #106 |
| D079 | 2026-10-14 | By source modules: real sections, one mesh per run; joints superseded the same day by D074 | pattern `facade-decor-inset` | PR #106 |
| D080 | 2026-10-14 | A build by source modules follows the source: screens with no top get no top plane | pattern `roof-screen-enclosure` | PR #106 |
| D081 | 2026-10-14 | A terrace glass railing is one 20 mm plate per free side; frames and posts are texture | pattern `terrace` | PR #106 |
| D082 | 2026-10-14 | Every agent-facing document is in English; Russian only for human cheat sheets | `AGENTS.md`, `docs/prd/agent-ready-harness.md` | #118 |
| D083 | 2026-10-14 | Harness waves in order: context and memory -> evals and trace -> guardrails and tools -> process and readiness | `docs/prd/agent-ready-harness.md` | #118 |
| D084 | 2026-10-14 | Agent-ready = two capability evals green (B01 from the root; ticket to PR) | `docs/prd/agent-ready-harness.md` | #118 |
| D085 | 2026-10-14 | Harness work follows grilling -> to-spec -> to-tickets -> implement -> code-review | `docs/prd/agent-ready-harness.md` | #118 |
| D086 | 2026-10-14 | Merges stay on the user's command; the only added autonomy is the spec's two escalation classes | `docs/prd/agent-ready-harness.md` | #118 |

# Handoff — 2026-10-12

State of the harness at the end of a long Claude session, so a new agent starts exactly here without that
chat. Facts only, from the repository and the open work. Current detail: `docs/PROJECT_STATE.md`;
unsolved work: `docs/backlog.md`.

## Where we are (merged on `main`, what the chain can do now)

- #1, #3, harness naming / plan / review checklist — repo scaffolding, material id ranges
  (`standards/material_id_ranges.yaml`, ADR 0001), naming (`docs/agents/NAMING.md`), review recipe
  (`docs/agents/REVIEW_CHECKLIST.md`), HARNESS_PLAN.
- #5–#9, #16 — spec extractor on a mesh dump: levels from `LEVEL_*` helpers or `object.json`, contours over
  the full storey, kinks and rounded corners, openings from holes or glass, typical floors written once,
  roof at the input level, frames per source.
- #10, #11, #29 — Revit route (TwinPack, walls on location lines) and spec comparison Revit vs mesh.
- #31, #36, grilles — doors, relief, openings across levels; spec v0.3 (opening = hole with frame, depth
  only as an exception); vent grilles as openings; extraction thresholds from `tolerances.json`.
- #4 — window type library (`window_types.json`, user-confirmed types).
- #14, #47, #48 — benchmark B01 tolerances and geometry checkers; first patterns approved.
- #50, #12/#13/#51 — engine `src/dt_ai/geometry/from_spec.py` (spec -> model) and the chain
  `tools/qa/run_benchmark.py` (etalon FBX -> spec -> engine -> Blender FBX -> readback -> checks).
- #52 — C24: `npm_min` opening plane at the full opening depth, `mid` at half.
- #53, #58 — B02 etalon (non-90 corner, niche) green end to end; oblique walls.
- #54, #55 — parapet from `LEVEL_roof`; a contour per floor, ledge and soffit at a floor step.
- #59, #61 — terraces (spec v0.4): engine parapet on a ledge, extractor reads it; bench B02t.
- #62 — non-manifold vertices fail the mesh check.
- #63, #64, #65, #66 — inset slabs everywhere (hole + plate, `plate_gap_m` 5 mm / `plate_overlap_m` 20 mm in
  the spec), around shafts; ledges between final contours.
- #67 — KPP1 v007 with the inset roof (not yet accepted by the user).
- #60, #68, #69 — markup helpers plan; MH1 Blender `LEVEL_*` route; MH2 level helpers from Revit Levels.
- #70, #71 — intake plan (HARNESS_PLAN §15) and IN1 skeleton (`dt intake check`: sources.json,
  picture.md, questions.md, spec-draft.json).
- #72 — K01 (KPP1 as a benchmark): material ids from UDIM tiles, geometry thresholds; first run 5/8.
- #73 — colleague case `alina-bld` as a lesson (`docs/cases.md`); pattern `facade-decor-inset` (draft);
  decor benchmark K02 brief (`bench-k02-decor-fragment`, catalogue `decor-catalog.json`); synthetic B03
  deferred, old B03 attachments -> B04; hook `pipeline_gate` (pre-commit + Claude PreToolUse: a job's
  `Pipeline status` above draft needs `pipeline/spec.json`, `spec.report.json`, `check.json`; new job
  scripts name an engine gap `EG<n>`); mixed mode (engine gaps EG1–EG4 in backlog).
- #74 — spec v0.5 `decor` block and its extractor `src/dt_ai/spec/decor.py` (boxes on walls, columns on a
  level, split pieces merged up to `plate_gap_m` x 12 = 0.06 m, projection <= 0.10 m texture, > 0.8 m an
  attachment candidate, one question per type).
- #75 — engine builds decor in its own mesh `decor` (body never cut, 0.02 m inset, 5 mm off openings,
  run-in meetings, convex corners: the main element runs on and keeps its back outside the wall, the other
  higher -> `decor-corner`); `check_decor` reads the model back with the extractor. Post-merge B01 / B02 /
  B02t 9/9 etalon and model.

## In work

| What | Branch / PR | Status | Left to do |
|---|---|---|---|
| OD1: opening depth default 0.4, "depth by default" in the report | `harness/od1-opening-depth`, PR #76, head `9190781` | Codex rounds 1–2 fixed; **round 3 running** in `C:/x/cr-76` (result `C:/x/cr-76/review3-76.md`); **not merged** | read round 3, fix, merge, update PROJECT_STATE on main |
| (inside #76) K01 `decor_tol_m`; `check_decor` on a real building (attachments are no decor); decor ids by material (metal 16–20 or 26–30) | same | same | same |
| Materials table: 3ds Max slots and glass slots | `harness/source-slot-table`, PR #77, `9b70e92` | open, **waits for OD1, no review started** | 3 Codex rounds after #76, merge |
| Colleague building through the harness | `job/case-alina-bld-pipeline` (on top of #77's branch), `f8ae02d`; `jobs/case-alina-bld/` | `Pipeline status: draft`; run 1 stopped (no body); rules 1–5 below not in code | implement rules 1–5, rerun, compare with the colleague's v001 |

Local state outside git:
- Source of `case-alina-bld`: `C:/Users/artsafro/Downloads/alina_bld.max`, layer `Геометрия исходная`
  (user). Exported read only to `data/sources/case-alina-bld/source-geometry-v001.fbx` and
  `dumps/source-dump-v001.json` (local, git-ignored). The scene is open in 3ds Max 2024, not saved.
- Colleague's v001 results (to compare with): worktree `.claude/worktrees/3d-max-floor-modeling-742570`,
  `jobs/alina-bld/outputs/` (body, openings, decor, balconies; not tracked).
- The new pre-commit (`tools/git-hooks/pre-commit`: link large files, then `pipeline_gate`) is installed
  in `.git/hooks/pre-commit`; the old one is in `C:/x/pre-commit.backup-2026-10-12`.
- `~/.claude/settings.json` got a `permissions` block (backup `~/.claude/settings.backup-2026-10-12.json`).
- `C:/x/cr-46 … cr-75`: leftovers of Codex review sandboxes (pytest temp dirs with ACLs this user cannot
  delete); harmless.

## User decisions not in code yet

`case-alina-bld` (2026-10-12), verbatim in substance:
1. Source class "panel facade without a shell" -> recorded in intake (IN2) as the first check: is there a
   closed body. If not, the path is "contours by slabs + panels as finish / decor"; the extractor is not run
   on such a source by default. Into case `alina-bld` as the second reason the first run went by scripts.
2. Contours by slabs: 104–221 vertices follow the slab relief. Simplify by the relief rule: deviations
   <= 0.10 m from the wall line collapse; check the result against the envelope of the panels' outer faces.
   Areas 611 / 599 / 582 / 522 into the report as `measured by slabs`.
3. Contour section rule: a storey's contour is taken at mid storey height (`level + 0.5·h`). A change of
   section in the band <= 0.3 m under the next level is the slab edge (`floor-step` / belt), not the
   contour. The `contour_at_m` question stays only when the section changes inside the wall band itself.
4. Parapet thickness: measured from the source when it gives a closed section (0.3 / 0.4 / 0.6, always
   from the project). If not readable, take `parapet_thickness_default_m` (the value already in
   object.json / tolerances, 0.3 or 0.4), mark "parapet thickness by default" in the report, no question;
   the user adjusts at acceptance.
5. No provisional values, not even to collect stops: `dt spec extract --collect-stops` — one pass, every
   stop listed, nothing substituted. Into the harness rules.

Decor ids by material (metal 16–20, plaster / stone / tile 26–30): **implemented in #76, not on main**. The
K01 strip with id 17 was identified from `jobs/KPP1/materials.json` as `Metal_RAL5015` (0.074 x 0.30 m,
0.22 m out, east wall at 3.6 m: a metal bracket); recorded in the pattern; **confirmed by the user 2026-10-12**
("металлический кронштейн, правило верное").

Corner of decor elements of different heights (back kept outside the wall, the other higher ->
`decor-corner`): **in code since #75**.

## Waiting for the user

- K02: `source.max` + `etalon.max` of the fragment (brief `benchmark/bench-k02-decor-fragment/README.md`,
  cut z 12.52–19.69) and the offset used.
- KPP1 v007 acceptance.
- `case-alina-bld`: the real object id `<site>-<code>`; the levels' open points (95.75 vs 96.55, 0.8 m apart;
  terrace decks 56.2 / 69.4 / 82.6 are 0.2 above the slabs); a finish table for the material slots.

## Next steps, in order

1. OD1 (#76): finish round 3, merge, PROJECT_STATE.
2. #77 slots: 3 Codex rounds, merge.
3. `case-alina-bld` with rules 1–5 (intake check for a closed body, contours by slabs, mid-storey section,
   parapet default, `--collect-stops`), then the full chain and the comparison with the colleague's v001.
4. K02 PR 4 (decor run on the fragment) once the user gives source + etalon.
5. EG2 balconies / attachments over 0.8 m.

## Harness rules that were broken and must not be again

- Building past `dt spec extract` / the engine / the checkers (the colleague case; now `pipeline_gate`).
- Provisional values, even to collect stops (rule 5; run 1 of `case-alina-bld` did it and was reverted).
- An etalon made by the engine (an etalon is always hand-made by the user).
- A lost `.py` with a live `.pyc` (job scripts are committed before they run; `pipeline_gate --job` checks).

## Links

- Plan: `docs/HARNESS_PLAN.md` §3 (spec contract up to v0.5), §4 (extractor), §5 (benchmark), §7 (patterns,
  gray zone, one question per type), §8 (pipeline, hooks), §14 (markup helpers), §15 (intake), §16 (lessons
  of `alina-bld`: OD1, decor, `pipeline_gate`, mixed mode).
- Backlog: `docs/backlog.md` (EG1–EG4, IN2–IN8, MH1b, MH3, H-items). Cases: `docs/cases.md`.
- Patterns: `docs/domain/patterns/INDEX.md`, `facade-decor-inset.md`, `opening-plane.md`,
  `roof-inset-plane.md`, `terrace.md`, `markup-helpers.md`.
- Benchmarks: `benchmark/README.md`, `bench-b01-box`, `bench-b02-corner-niche`, `bench-b02t-terrace`,
  `bench-k01-kpp1`, `bench-k02-decor-fragment` (brief + catalogue), `bench-b03-decor` (deferred),
  `bench-b04-attachments`.
- Briefs for the modeller (ТЗ): the READMEs of `bench-k02-decor-fragment` and `bench-b03-decor`. A Claude
  Docs copy of a brief is not referenced anywhere in the repository.

## Prompt for the new agent

Paste this as the first message of the new chat:

```text
Ты — агент Claude Code в репозитории AGR-DigitalTwin (artsafro/AGR-DigitalTwin): харнесс извлечения spec,
движок from_spec, чекеры и бенчмарки для моделей NPM/VPM. Роль — по CLAUDE.md.

1. Прочитай по порядку: AGENTS.md, CLAUDE.md, docs/HANDOFF.md, docs/PROJECT_STATE.md, docs/backlog.md.
2. Проверь фактическое состояние: git status и git log -1 на main; открытые PR (gh pr list) и их статус;
   ветки harness/od1-opening-depth, harness/source-slot-table, job/case-alina-bld-pipeline; результат
   Codex-ревью раунда 3 по #76 в C:/x/cr-76/review3-76.md (если файла нет — ревью не завершилось).
3. Сверь это с docs/HANDOFF.md и доложи расхождения (коротко, списком) до начала работы.
4. Затем продолжи с первого пункта раздела «Next steps» в HANDOFF. Новых направлений без пользователя не
   начинай.

Правила те же: одна задача — одна ветка — один worktree; каждый PR — 3 раунда Codex-ревью (codex exec
в C:/x/cr-<N>), мерж по команде пользователя, после мержа — PROJECT_STATE на main; вопросы вместо догадок
и без временных подстановок значений; эталон делает только пользователь; сборка только через
dt spec extract -> движок -> чекеры. Пользователю отвечай по-русски.
```

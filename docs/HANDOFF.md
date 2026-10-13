# Handoff — 2026-10-13

State of the harness at the end of a long Claude session, so a new session (with the project subagents) starts
the OBJ03 model exactly here. Facts only. Detail: `docs/PROJECT_STATE.md`; unsolved work: `docs/backlog.md`;
merged history before 2026-10-12: git log and PROJECT_STATE.

## Where we are

`main` = `723097a` (merge of #92). Merged since the last handoff: #77 material slots, #78 unlisted decor judged
against the body, #79 `pipeline_gate` fails closed, #80 OBJ03 rule 5 (`--collect-stops`), #81 rules 3–4
(mid-storey section, parapet thickness / default, spec v0.6), #83 rules 1–2 (panelised source, contours by
panels), #86 five read-only subagents, #89 (#87 protrusions by segment, #88 terrace storey's own slab), #92 spec
v0.7 `roof_structures` (pattern `roof-screen-enclosure`, draft).

Moratorium (user 2026-10-13): no new harness PRs until the user has seen the OBJ03 model. #92 was the second and
last exception. A rule the run lacks becomes an issue; the job goes on in mixed mode, the model without that
element.

## OBJ03 — user decisions (2026-10-13)

- Object: `OBJ03` (former `case-alina-bld`; no colleague names in the repo), job folder `jobs/OBJ03/`, branch
  `job/obj03-decor`, object id in `object.json` `obj03-decor`, `source_class: "panelised"`, slabs
  `Shape211223725`, `Shape211223718`.
- **1a** — #87 / #88 only, no new spec fields (done in #89).
- **2a** — 96.55 is the roof; 95.75 is no level; the top storey runs 92.3–96.55. The roof screen enclosure
  `RailClone2142` (up to 102.56) is built as planes in `npm_min` (pattern `roof-screen-enclosure`, done in #92):
  `object.json` `roof_screens: ["RailClone2142"]`. Its mid / VPM shell is issue #91.
- **3a** — OD1 applies (opening depth default 0.4); the C24 record must be updated with the date and a link to
  OD1 (not done yet).
- **Parapet** — `parapet_thickness_default_m` 0.3.
- Terrace level = walkable top + 0.2 (decks 56.2 / 69.4 / 82.6 in `object.json`).

## The OBJ03 run (probe, not committed)

`dt spec extract --collect-stops` on `jobs/OBJ03/outputs/source-dump-materials-v001.json` with the probe object
`C:/x/t-obj03/object-rs.json` (= `jobs/OBJ03/object.json` without L28 95.75, with `roof_screens` and the 0.3
default): all storeys are read by panels, the enclosure is read, **one stop**:

> roof at 96.550 m has an opening of 0.07 m2 at (57.70, 151.83) that is not a shaft (walls line 65% of it at
> 94.43 m): roof missing there?

A sliver, likely the Douglas–Peucker contour vs the roof coverage (issue #84). It goes to the user as a model /
data question (roof there or not); under the moratorium no harness fix.

## Local state outside git (preserve)

- `jobs/OBJ03/` is **untracked** in worktree `.claude/worktrees/3d-max-floor-modeling-742570` (STATE.md — old,
  needs a rewrite; object.json, materials.json, tolerances.json; `outputs/`: source dump with materials, spec
  report v001, sections-v001 with 3 renders and 6 SVG sections). The same content is in the stash entry
  `obj03-job-wip` (`64e03c89741fa6fefc524ca22fcbef35e7d7279d`). Branch `job/obj03-decor` exists at `a3cf6a6`
  with no job commits yet.
- Source: `data/sources/OBJ03/` (FBX + `dumps/source-dump-v001.json`), git-ignored.
- Pre-commit hook at the #79 version in `.git/hooks/pre-commit` (backup `C:/x/pre-commit.backup-2026-10-12b`).
- pytest on this machine: only with a short `--basetemp` (`C:/x/t-*`).
- The desktop app session did not load the project subagents; `claude -p` in the worktree did.
- `C:/x/t-obj03/`: probe specs and reports (local).

## Open issues from this work

#82 terrace parapets, #84 DP contour vs roof check, #85 open facade joined to an inner ring, #90 protrusion root
in the facade band, #91 enclosure shell for mid / VPM, #93 shaft under a marked enclosure.

## Next steps, in order (new session)

1. On `job/obj03-decor`: commit `jobs/OBJ03/` with the decisions above (drop L28, `roof_screens`,
   `parapet_thickness_default_m` 0.3), rewrite `STATE.md`, update the C24 record (3a, link OD1). Then drop the
   stash entry `obj03-job-wip`.
2. Rerun `dt spec extract --collect-stops`; send the stops to the user in one message with answer options.
3. The OBJ03 model via spec → engine → checkers (mixed mode for what the engine lacks, `EG<n>`), readback, and
   show it to the user.
4. Then K02 PR 4 (once the user gives the fragment), EG2 attachments.

## Review procedure (user 2026-10-13)

Rounds by risk: src / hooks / gate / checkers 2 rounds (a 3rd only if round 2 finds a P1); docs / patterns 1
round; jobs no Codex. P1 = wrong result, silent skip, data loss, hook bypass — fixed in the PR; P2 → issue.
Review input = diff + affected tests; full suite and benchmarks once before the merge. Ceiling 3 rounds; merge
on the user's command. Codex: `codex exec ... < /dev/null` (it otherwise waits for stdin) in `C:/x/cr-<N>`.

## Prompt for the new agent

```text
Ты — агент Claude Code в репозитории AGR-DigitalTwin (artsafro/AGR-DigitalTwin). Задача сессии — модель OBJ03
через харнесс (spec -> движок -> чекеры), с проектными субагентами (.claude/agents/).

1. Прочитай: AGENTS.md, CLAUDE.md, docs/HANDOFF.md, docs/PROJECT_STATE.md, docs/agents/WORKFLOW.md.
2. Проверь: main = 723097a или новее; ветка job/obj03-decor; jobs/OBJ03 (untracked) и stash obj03-job-wip.
3. Доложи расхождения с HANDOFF, затем «Next steps» по порядку.

Мораторий: новых PR в харнесс нет до показа модели OBJ03; нехватка правила — issue и модель без элемента.
Вопросы пользователю — только про модель и данные объекта; технические решения — сам, строкой «решено: …».
Мерж по команде пользователя. Пользователю отвечай по-русски.
```

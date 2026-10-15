# Evals

Tasks that grade the agent's behaviour from evidence files, not the model's output (spec
`docs/prd/agent-ready-harness.md`, "Checks and evals"; #122). Graders are pure Python in `src/twinqa/evals/`
(no LLM calls); the runner is `uv run dt evals`.

## Layout

```
evals/<task id>/
  task.json      id, suite, grader, evidence rules, references (known evidence with its verdict)
  task.md        what is checked and why, the evidence, the detection rule, what the references are
  fixtures/      optional reference evidence; synthetic files say so in the name (*.synthetic.*) and inside
```

`task.json`:

| Field | Meaning |
|---|---|
| `id` | the folder name |
| `suite` | `regression` (procedural graders, 100 % before every merge) or `capability` (model change, weekly) |
| `grader` | a name in `twinqa.evals.graders.GRADERS` |
| `evidence` | `{name: rule}` the grader reads in a real run |
| `references` | `[{name, evidence, verdict: pass|fail}]`: evidence with a known answer; the reference verdict |

An evidence rule is `{"root": "main"|"task", "path"|"glob": ..., "match": optional}`. `main` is the main
checkout (parent of `git rev-parse --git-common-dir`, where every worktree's `logs/` goes); `task` is the task
folder. `{branch}` and `{branch_slug}` (every character outside `A-Za-z0-9._-` as `-`, the file-name rule of
`tools/hooks/save_transcript.py`) are replaced by the graded branch. A glob takes every match; `match` is a regular
expression the whole file name must match (placeholders inserted escaped), so that a glob prefix cannot take
another branch's files (`harness-x-pr*` would also catch branch `harness/x-pr7-y`). No file = the check is not
measured (exit 2), never a pass.

A `path` / `glob` is relative and stays inside its root: an absolute path or `..` stops the task, and a file
reached through a link out of the root is not measured. The `--evidence name=path` override is explicit user input
and may point anywhere.

Every `task.json` is validated in full before anything runs (field types, the grader's evidence names in
`evidence` and in every reference, the rules). An invalid task is a stopped row (exit 2) in any run that reaches
its folder - a suite run reads every folder, so a typo in `suite` cannot drop a task unseen.

Evidence by convention: transcripts `logs/transcripts/<branch slug>-pr<N|none>-<session>.jsonl` (written at
`/handover`), the usage log `logs/agent-usage.jsonl`, benchmark runs `data/benchmark/<bench>/runs/`.

## Running

```
uv run dt evals --suite regression                 # every regression task, evidence of the current branch
uv run dt evals --suite regression --branch harness/x
uv run dt evals --task no-hook-denial --evidence transcript=<file.jsonl>
uv run dt evals --suite regression --references    # each grader against its reference verdicts
```

The report goes to a new run folder, `<main checkout>/logs/evals/runs/<time>-<selector>/report.json`
(git-ignored; `--output` for another new folder): per check the task, check, expected, measured, pass/fail and the
evidence paths used. Exit 0 every check passes; 1 a grader fails (wins over a check not measured); 2 evidence
missing, a task stopped (bad `task.json`) or the input is wrong - as `tools/qa/run_benchmark.py`.

## Adding a task

A grader is registered in `GRADERS` with the evidence names it reads; it takes `{name: [paths]}`, returns
`{"check", "expected", "measured", "passed", "details"}`, raises `EvidenceError` when the evidence is absent and
returns `passed: None` with an `error` when it is incomplete (a definite failure found in the readable part stays a
failure). Each regression grader has a reference that fails and one that
passes, and a pytest over both (`tests/test_evals.py`).

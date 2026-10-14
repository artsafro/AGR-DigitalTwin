# Agent harness: sources vs. this repository (2026-10-14)

Input for the grilling session and the PRD on an agent-ready harness. Sources: the video
"AI-инженерия с нуля — полный гайд для разработчика [2026]" (youtube `WT0yDhfOjaA`, transcript
read in full, 63 min), its 12 whiteboard screenshots, and the 17 linked papers and guides (each
read from the primary source unless noted). Repository facts come from `AGENTS.md`,
`docs/HARNESS_PLAN.md` rev 3, `docs/agents/*`, `.claude/settings.json`, the hooks, the open
issues and the labels on 2026-10-14.

Status: notes, not decisions. Every "candidate" is a question for the user, not a plan.

## 1. The video's structure

**Three production lines** (screenshot 1). Old: requirement -> developer -> some code -> review
-> release. Naive AI: requirement -> AI -> huge diff -> overloaded review ("verification tax")
-> errors and rework. New: requirement -> specification -> context -> agent -> tools ->
automatic check -> trace -> human decision -> release. The unit of value is not written code
but a verified change in a working system.

**Harness** (screenshot 2): the engineering environment around the model that turns a
probabilistic model into a repeatable executor. Six layers, each answering one question:

| Layer | Question | The video's content |
|---|---|---|
| 6.1 Context engineering + RAG | what the agent must know | sources: grep / search, symbols and AST, dependency graph, git history, issue tracker and ADR, semantic index -> retrieval -> request context -> model. "Whole project in the prompt" does not work. Retrieval is not only embeddings |
| 6.2 Tools and MCP | what the agent can do | files, terminal, GitHub, browser, database, CI / builds, logs, task tracker, staging / env, internal APIs. MCP is a connector ("USB-C for AI"), not memory, not intelligence; it guarantees neither the tool choice, nor the reading of the answer, nor the safety of the action |
| 6.3 Memory and state | what the agent must keep | context = what the model sees now; memory = what returns later. Session saves to memory, the next session reads it back. Forms: progress.md, git history, JSON state, event log, summaries. "Endless chat = a warehouse"; memory = selection + structure |
| 6.4 Tests and evals | how to prove quality | software tests check the product (unit, integration, contract, e2e, performance, security); evals check the agent (understood the task, found the document, called the tool, step order, skipped no step, survives a model change). "Task done" is not proof |
| 6.5 Observability | what happened | a function fails -> stack trace; an agent fails -> six causes. One trace per run: context -> LLM call -> tool -> tests FAIL -> retry. Must be visible: which context it got, which model, which tools, what they returned, how many retries, where it failed, time and cost. Causes of an agent error: wrong context, wrong tool, misread tool answer, lost part of the state, wrong conclusion, ended the loop early. "If you cannot see the agent's path you cannot improve it" |
| 6.6 Guardrails and approvals | what the agent may not do | sandbox (tests, staging, PR) inside guardrails; free: read the test DB, own branch, staging, pull request; approval only: production, real refunds, deleting data, migrations; limits: budget, attempts, time |

**The loop** (screenshot 12): intention -> specification -> context -> action -> check ->
memory, one turn = one verified change; observability watches every step; guardrails enclose
all of it.

**Maturity** (Stanford SWEPR, 50:57): L0 no observable AI; L1 opportunistic prompting; L2
systematized prompting (prompts and rules versioned, reusable); L3 agent-backed development
(callable agents or scripts take over parts of the work); L4 orchestrated agentic workflows
(several agents coordinated by workflows or DAGs).

**AI engineer** (53:23): designs which context the model gets and from where, what is kept in
memory, which tools exist, how retrieval works, the agent loop, when to stop and call a human,
how traces are read, where the model may not go.

## 2. What the sources add

- **Anthropic, Effective context engineering.** Context is finite with diminishing returns: the
  smallest set of high-signal tokens. System prompt at the "right altitude" (no brittle if-else,
  no vague guidance). Tools minimal and non-overlapping: if a human cannot pick the tool, the
  agent cannot. Just-in-time retrieval by lightweight identifiers (paths, queries) beats
  pre-loading; folder structure and naming are signals. Compaction: recall first, then
  precision. Structured note-taking (a NOTES.md outside the window). Sub-agents return 1-2k
  token summaries. "Do the simplest thing that works."
- **Anthropic, Contextual retrieval.** Under ~200k tokens of knowledge: put it all in the prompt,
  no retrieval. Beyond: chunk + a 50-100 token context per chunk, BM25 + embeddings, rerank to
  ~20 chunks. Always run evals on your own data.
- **Google, Long context.** Default is now the full context window plus context caching;
  filtering and RAG remain for some cases. Multi-needle retrieval degrades.
- **Du et al. 2025, Context length alone hurts LLM performance despite perfect retrieval**
  (arXiv 2510.05381). Five models, math / QA / code: 13.9-85 % drop as the input grows even when
  the irrelevant tokens are whitespace or masked. Mitigation: make the model recite the relevant
  evidence before solving (long task -> short task), +4 % on RULER.
- **Anthropic, Effective harnesses for long-running agents.** Two agents, one harness: the
  initializer writes `init.sh`, `claude-progress.txt`, a JSON feature list with every feature
  `passes: false` and the first commit; every later coding session reads the progress file and
  the git log, picks one feature, tests it end to end as a user would (unit tests and curl
  missed failures), commits, updates the notes, leaves the tree mergeable. The agent may flip
  only `passes`; JSON is corrupted less than Markdown. Each mechanism names the failure it
  removes (declares done too early; leaves undocumented bugs; wastes time finding how to run).
- **Anthropic, Harness design for long-running application development.** Planner (short prompt
  -> spec; without it the generator under-scopes), generator, evaluator (Playwright, clicks like
  a user, hard threshold per criterion, few-shot calibrated; Claude out of the box is a poor QA
  agent that talks itself into approving). Context resets with a structured handoff beat in-place
  compaction while models had "context anxiety"; with Opus 4.5 resets were dropped. Every
  harness component is an assumption about what the model cannot do alone: remove pieces one at
  a time at each model release, keep the load-bearing ones. Solo run 20 min / $9 with a broken
  core; full harness 6 h / $200 and a working app.
- **Anthropic, Building effective agents.** Workflows (predefined code paths) before agents;
  five patterns (chaining, routing, parallel, orchestrator-workers, evaluator-optimizer).
  Simplicity, transparency (show the plan), ACI: tool docs tested like code; poka-yoke the tools
  (absolute paths removed a whole error class).
- **Anthropic, Demystifying evals for AI agents.** Terms: task, trial, grader, transcript,
  outcome (the environment state, not the claim). Graders: code (fast, brittle), model (needs
  calibration), human (calibrates the others). Capability evals start low; regression evals sit
  near 100 %; a saturated capability eval moves to regression. pass@k vs pass^k (75 % per trial
  = 42 % over three). Start with 20-50 tasks from bug trackers and manual checks; a reference
  solution per task; balance "should" and "should not"; isolate trials; grade outcomes, not the
  path; 0 % usually means a broken grader; read transcripts before trusting scores; evals in CI.
- **OpenAI, A practical guide to building agents.** Model + tools + instructions. Tool types:
  data, action, orchestration. Instructions from existing procedures, one clear action per
  step, edge cases as branches. Single agent first; split on complex logic or tool overlap
  (15 distinct tools work, 10 overlapping do not). Guardrails as layered defence; **tool
  safeguards: rate every tool low / medium / high by read-only vs write, reversibility,
  permissions, financial impact, and let the rating trigger a pause or an escalation.** Human
  intervention on exceeded failure thresholds (retries, actions) and on high-risk actions.
- **OpenAI, Evaluate agent workflows / Trace grading / Integrations and observability.** A trace
  = the full run (model calls, tool calls, handoffs, guardrails). Debug with traces first; a
  grader on traces answers "picked the right tool? handed off when it should? violated an
  instruction?"; then datasets and eval runs for repeatable comparison. Reduce tracing, never
  turn it off; group related runs; use high-signal traces as eval inputs.
- **OpenAI, Build an agent improvement loop (cookbook).** Flywheel: traces show what happened,
  feedback says what mattered, evals make it reusable, Codex implements the change; artifacts
  per step (JSONL traces, eval config, results, `codex_handoff.md`). The harness is the whole
  contract: instructions, tools, routing, output requirements, validation checks. Start with a
  reviewed loop (a human approves the diff).
- **OpenAI, Safety in building agents.** Untrusted text out of developer messages; structured
  outputs between nodes; approvals on for MCP tools; guardrails are a first layer only; agents
  will still be tricked, so limit what they can reach.
- **Stanford SWEPR.** Levels L0-L4 read from version-control traces (prompt files, agent configs,
  workflow definitions), not surveys; confidence from commit activity and contributors.
- **Stanford, Enterprise AI playbook (51 deployments).** 77 % of the hardest problems were
  change management, data quality, process redesign; 61 % had a prior failure. Escalation-based
  models (AI handles 80 %+, humans review exceptions) gave a 71 % median gain vs 30 % for
  approval-on-every-output models, partly because they are applied to recoverable, high-volume
  tasks. Model choice was interchangeable in 42 % of cases: the durable advantage is the
  orchestration layer. Messy data is not a blocker if the design expects it.
- **SWE-bench.** The video's point: the best models resolve ~77 % of real issues, so every
  output is a candidate, not a solution. Our equivalent of SWE-bench is `benchmark/`.

## 3. Layer by layer: what the repository has, what is missing

Legend: **have** = present and used; **gap** = named by the sources, absent or prose-only here;
**candidate** = a possible move, to be decided in the grill.

### 3.1 Context (what the agent knows)

Have: `AGENTS.md` (95 lines) as a pointer table, `CLAUDE.md` 19 lines; `docs/domain/*`,
`GLOSSARY.md`, `docs/domain/patterns/INDEX.md` (14 patterns), `docs/cases.md`,
`docs/domain/conflicts.md`; `docs/HANDOFF.md` injected by the SessionStart hook with branch,
status, last commits, open PRs; `context_watch` at 45 / 65 %; five read-only subagents that keep
dumps, benchmark output and the pattern catalogue out of the main context; `technical_library/`
read only on demand; `jobs/<ID>/questions.md`.

Gaps:
- `docs/PROJECT_STATE.md` (344 lines) is a running history: lines 11-120 are one paragraph of
  merged PRs. It is the file every session reads first ("where things are"), so it is the
  warehouse the video warns about.
- `docs/HARNESS_PLAN.md` (455 lines, Russian) mixes decisions, hypotheses, history and per-PR
  notes; `AGENTS.md` says docs are English. User decisions are scattered as "(user 2026-10-xx)"
  across the plan, the patterns, `WORKFLOW.md`, `cases.md`, PR bodies. There is one ADR.
- The code map exists at the package level (`AGENTS.md` "Code map"; the engine entry points and
  commands in `CAPABILITIES.md`). What is missing is the level below it: which CLI command calls
  which module, and the dependencies between modules — today known only through PR history.
- No decision index that `pattern-librarian` could grep by date or topic.
- Size of the agent-facing rule layer, estimated as characters / 4 at commit 7893140: root files
  ~3k tokens, `docs/agents` ~15k, `docs/domain` ~35k (patterns ~13k of it), plan / state / backlog /
  cases / pipeline / handoff ~31k, `.agents/skills` ~20k, `standards/` ~38k — about 150k in all;
  `docs/agr` ~400k, `jobs` ~106k, `technical_library` ~34k are outside it. Command (Git Bash):
  `for d in <dirs>; do find $d -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.json" \) | xargs cat | wc -c; done`,
  the result divided by four. An estimate, not a tokenizer count.

Candidates: split state from history (`PROJECT_STATE.md` = goal, open gates, next; history to
git / a changelog); a decision log (`docs/adr/` or `docs/decisions.md`, one line per dated user
decision with its home file); a `CODEMAP.md`; a retrieval rule in `AGENTS.md` (what to grep
first). The 200k-token rule says the agent-facing docs should stay small enough to load the
relevant file whole, not indexed.

### 3.2 Tools (what the agent can do)

Have: MCP routes with a verified status per application (`CAPABILITIES.md`), one DCC skill per
route, `skill_gate` denies a DCC call until its skill is loaded, `dt` CLI, `gh`, subagents,
Kanban board, `tools/qa/*`, `validate-delivery`.

Gaps:
- No risk rating per tool (OpenAI: read-only / versioned write / destructive). `guard.py`
  encodes risk for shell commands and production file extensions only; MCP write tools (Revit
  edits, Blender `execute_blender_code`) are governed by prose ("versioned path", "never
  overwrite").
- Codex and Antigravity hooks are CONFIGURED, not validated (backlog H1); CI is undecided (H5).
- No "look at the result as a user would" tool for 3D other than renders through
  `independent-checker` (the Anthropic harness used Playwright for this; #117 shows the checker's
  blind spots).

Candidates: a tool register with a risk class that `guard.py` and the MCP skills share; decide
CI (H5) as the automatic check of the "new process"; a render-based visual check as a mandatory
grader (normals, open edges, decor topology from #117).

### 3.3 Memory (what the agent keeps)

Have: `docs/HANDOFF.md` (7000-char limit) + `/handover` + `/takeover`; `jobs/<ID>/STATE.md`,
`REPORT.md`, `questions.md`; `RunRecord` per run; `docs/cases.md`; patterns; Claude's user-level
auto-memory; `logs/agent-usage.jsonl`; compaction log.

Gaps:
- No memory map: which kind of fact lives where (decision / rule / case / state / question /
  run evidence). The rule of three covers procedures, not facts.
- Run evidence is per job folder (`runs/`, local only); there is no index of runs across jobs.
- `PROJECT_STATE.md` doubles as memory and history (see 3.1).

Candidates: a one-table memory map in `WORKFLOW.md`; the decision log as the memory of
decisions; a run index (one JSONL line per RunRecord) if cross-job queries are needed.

### 3.4 Checks and evals (how quality is proved)

Have: pytest (~50 test modules, contracts, integration), `benchmark/` B01 / B02 / B02t green,
`twinqa` V001-V017 delivery validator, `pipeline_gate` (status cannot rise without extractor and
checker reports), `independent-checker` after every engine run, the 3-question review checklist
with Codex rounds by risk, the `passed=true` rule.

Gaps (the largest):
- **No agent evals.** No retrospective, task-level check proves that the agent followed the
  procedure: called `source-inspector` on a new source, ran the checker before "done", asked
  instead of inventing a number (PR #76 lesson: an invented threshold), stopped after repeated
  failures. The one live gate is `skill_gate` (PreToolUse): it denies a DCC MCP call until the skill
  is loaded, but only for the 3ds Max, Blender and Revit routes, only in the main session, and it
  passes when the transcript cannot be read; its tests cover the gate, not the task. The proxies
  for everything else are the hook denials and the 7-day usage counts in `/takeover`.
- The §13 "transferability test" (a new agent reads only the root and builds B01) was never run;
  it is exactly a capability eval.
- The benchmark set is a regression suite run by hand (`bench-runner`), not on every change.
- The checker has known blind spots (#117: normals, open edges, decor topology) — "green checks
  are not a clean model".

Candidates: an eval suite with three kinds of tasks and graders: (a) procedural graders over
transcripts or `agent-usage.jsonl` (one per row of the WORKFLOW trigger table); (b) the B01
transferability run in a clean worktree via `claude -p`, graded by `bench-runner`; (c) the whole
benchmark set as the regression gate on rule changes; plus closing the checker blind spots as
graders (#117). Start at 20-50 tasks from `cases.md` lessons and closed issues.

### 3.5 Observability (what happened)

Have: `RunRecord`, `AdapterReport`, `logs/agent-usage.jsonl` (subagents, skills, commands),
`agr-compactions.log`, job `STATE.md` / `REPORT.md`, review comments with numbers, Claude Code
transcripts in `~/.claude/projects/` (not indexed, not referenced from the repo).

Gaps:
- No trace per task: which context the session loaded, which tools and subagents it called,
  retries, where it stopped, context share, duration, cost. A PR carries the diff and the
  review, not the path that produced it.
- No failure taxonomy: the lessons in `cases.md` (#76, #117) are prose; the video's six causes
  (wrong context / wrong tool / misread answer / lost state / wrong conclusion / early stop) are
  not applied.
- `context_watch` silent on a forked session (#112).

Candidates: a trace summary step in `/handover` (and in the PR body): tools, subagents, skills,
retries, hook denials, context %, duration; a cause class on every lesson row; a transcript
export per merged PR (local, by link) so a grader can read it later.

### 3.6 Guardrails and approvals (what the agent may not do)

Have: `guard.py` asks on push, history rewrite, recursive deletes, installs, system changes,
production binaries; `pipeline_gate` denies; subagent hooks deny writes; `permissions`
allow / ask / deny; a worktree per task; one owner per DCC scene and port; pre-commit gates
(branch names, large files, pipeline status); three review rounds max; merge only on the user's
command; "three attempts -> stop" in prose.

Gaps:
- Limits (attempts, time, budget) exist as prose only; the §8 escalation after three module
  failures is not enforced.
- The free / approval-only matrix of the video is implicit; `guard.py` does not cover `gh pr
  merge` (the PR #76 incident was a merge without command) or `gh` deletes.
- No sandbox notion for DCC: scenes are live, the "versioned path" rule is prose.
- Codex / Antigravity guard parity is unverified (H1).

Candidates: an explicit permission matrix per agent (free / versioned write / ask / never),
`gh pr merge` and `gh ... delete` in the guard, an attempts counter in `pipeline/state` that the
gate reads, a scratch-copy rule for DCC checked by the skill.

### 3.7 Process and maturity

Have: the WORKFLOW loop (card -> goal -> questions -> contract -> plan -> execute -> verify ->
hand off), `spec.json` as the contract for jobs, Kanban with Needs-you, review rounds, the
Rule of three, context rotation. Maturity by SWEPR: **L3** (callable agents: five subagents,
skills, commands, hooks) with L4 planned (§10 orchestrator, after B01-B03 are stable).

Gaps:
- For harness and code tasks the "specification" step has no standard form: `WORKFLOW.md` requires
  a contract for multi-stage work (in the job `STATE.md` or in the PR), but an issue body is free
  text, there is no template, and `ready-for-agent` has no completeness gate.
- No "trace" step between the automatic check and the human decision.
- The operating model is approval on every output (Stanford: 30 % median gain) — chosen on
  purpose for model and data questions; nothing is in the escalation class yet.
- No harness inventory with "the failure each component removes" and "last verified", so
  pieces cannot be removed at a model release the way Anthropic recommends (nine hook scripts,
  three commands, five subagents today).

Candidates: an issue template for harness tasks (goal, acceptance, evidence); a harness
inventory table in `CAPABILITIES.md` "Harness" (component -> failure it prevents -> evidence ->
last verified); decide which task classes may move to escalation (e.g. doc-only PRs after a
clean Codex round).

## 4. Questions for the grill (one per layer, more inside)

1. Context: is `PROJECT_STATE.md` state or history? Where do dated user decisions live?
2. Tools: should MCP write tools carry a risk class that the guard enforces, or stay in skills?
3. Memory: one memory map, or keep the current spread?
4. Evals: which agent behaviours must be proven on every change, and from which evidence
   (transcript, usage log, benchmark)?
5. Observability: what must a PR carry about the path that produced it?
6. Guardrails: what is free, what needs the user, what is never allowed — per agent?
7. Process: what is the escalation class, if any? What is the target level, L3 or L4, and by
   when?
8. Harness hygiene: which existing components earn their place, and how is that re-checked?

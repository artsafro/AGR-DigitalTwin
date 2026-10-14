# Task workflow

Adapted from the AGR orchestration cycle (`docs/agr/` and the archive). Scale it to the
task: a one-line fix skips most steps; a multi-stage delivery uses all of them.

## Loop

1. **Goal and discovery.** Read `docs/PROJECT_STATE.md`, the relevant `docs/domain/` file,
   the matching accepted case (`docs/cases.md`) and the real inputs. A script or MCP that
   exists is not working until there is current evidence (`CAPABILITIES.md` status).
2. **Questions.** Ask only what changes the result, inputs, architecture, acceptance,
   destructive actions or publication. Decide routine details yourself.
3. **Contract.** For multi-stage work write in `jobs/<JOB>/STATE.md` (or the PR): goal and
   acceptance, exact inputs/versions, profile (NPM-OKS, VPM-OKS, NPM-territory…), owner of
   each scene/port/export, outputs, mandatory checks, stop conditions, next step. "Model"
   alone does not define the profile — ask when it matters.
4. **Plan.** Stages, dependencies, reused tools, checks. An open decision blocks only the
   stages that depend on it.
5. **Execute** in narrow stages. Pure computation in `src/`, DCC calls in adapters/tools,
   object parameters in the job, manual decisions in a record with their source. Every
   rerun writes a new versioned output; keep manifests and hashes.
6. **Verify independently.** The executor's report, exit 0 or a child agent's summary is
   not evidence. Read the actual files back. Classify a failure (source / tool / code /
   test / contract), fix the cause, rerun the affected checks. A failed mandatory check is
   never turned into a pass by rewording. After two failures with the same cause, stop that
   path, save the state and propose the next step.
7. **Hand off.** Compare the result with the original goal; report what is done, what was
   checked (commands, evidence paths) and what is open. On restart, read saved outputs and
   hashes before repeating any mutation (`run-evidence` skill).

## Subagents (Claude Code, user 2026-10-13)

The main agent keeps dumps, MaxScript output, benchmark runs and the pattern catalogue out of its own
context. It delegates them to the read-only subagents in `.claude/agents/`:

| Need | Subagent |
|---|---|
| Read a source scene or file: inventory, units, layers, sections at given heights, screenshots, slab and helper candidates | `source-inspector` |
| Is there a rule? (pattern, case, conflict, answered question) | `pattern-librarian` |
| Run benchmarks or tests and get a pass/fail table | `bench-runner` |
| Check a built model independently | `independent-checker` |
| A numeric question about an FBX or a dump (open edges, ids, heights, section areas) | `mesh-reader` |

Rules:
- Only the main agent writes code, commits and decides. No subagent may write to `src/`, `docs/` or `jobs/`,
  and none is created with write tools. Agent Teams are not enabled.
- After every engine run the main agent calls `independent-checker` before it reports "done".
- A subagent's result is data, not a decision. The main agent weighs it, and it asks the user only about the
  model or the object (`questions-only` rule).
- Disputed geometry: look first, then classify (user 2026-10-13) - every group of a classifier's verdict, every
  question and every stop is shown isolated on the body (renders, three views, sizes) before a rule or a question.

## Context rotation (Claude Code, user 2026-10-14)

A long session loses detail when it is compacted. Rotate instead, in the same worktree:

1. **When:** at a task boundary (PR opened, stage accepted), or when the context reaches about 40-50 % (the
   status line shows `ctx N%`), whichever comes first. Do not wait for auto-compaction. The UserPromptSubmit
   hook `tools/hooks/context_watch.py` measures it (the last response's `usage` in the transcript) and tells the
   agent once per session at 45 % to suggest `/handover` in one sentence, and at 65 % to urge it.
2. **`/handover`** (`.claude/commands/handover.md`): commit, a PR only at a task boundary (merge on the
   user's command), `docs/HANDOFF.md` from `docs/HANDOFF.template.md`, `jobs/<ID>/STATE.md` for a job;
   `PROJECT_STATE.md` only on `main` after a merge. It ends with «Чекпоинт готов, можно /clear».
3. **`/clear`** in the same worktree. The SessionStart hook (`tools/hooks/session_context.py`) puts the branch,
   `git status --short`, the last 5 commits, open PRs and the handoff into the new context, with a warning when
   the handoff is behind HEAD, belongs to another branch or has the old format.
4. **«продолжай»** - the agent names the branch, commit and next step, then does it. **`/takeover`**
   (`.claude/commands/takeover.md`) - the full reconciliation of handoff, git and GitHub, a list of open items and
   a proposal; it waits for «да». The names avoid the built-ins `/checkpoint` (alias of `/rewind`) and
   `/resume` (session picker), and the `handoff` skills.

Compaction: a manual `/compact` with a stale handoff is blocked (`/compact force` passes). An automatic one is
never blocked (that can fail the request); after it the hook tells the agent to run the handover procedure
first. Each compaction is logged to `<git dir>/agr-compactions.log`.

Worktrees and chats: a new worktree only for a new task, from fresh `main`. A second chat in the same repo only
reads, or writes files that do not overlap with the first one's. `docs/HANDOFF.md` describes its own branch: at
a merge to `main` keep `main`'s handoff unless the merged branch's handoff is the one the next session needs.

## Reports

Keep full arrays, scenes and logs in files. In a report give counts, statuses, up to five
errors and paths to full evidence. `AdapterReport` describes one operation, not readiness
of the whole object.

## Experience capture

When the user accepts a result ("принято", "круто получилось", …) capture it before the
stage ends with the `experience-transfer` skill: exact acceptance scope, inputs/versions and
hashes, code used, checks actually run, failures and fixes, reuse candidates. Add it to
`docs/cases.md`. Praise does not replace QA. A procedure becomes a general tool or skill
only after it works on a second representative object.

## Git

- Start independent work from fresh `main` in a new worktree; continue a task in its own
  worktree. Check existing worktrees, branch, base/head and dirty state before choosing.
- Commit successes and useful failed attempts with an honest status message.
- Merge only after review and the user's approval; remove a worktree only after its
  ignored outputs that matter are saved.

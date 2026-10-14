---
description: Save the session for a context rotation - commit, PR at a task boundary, docs/HANDOFF.md from the template, job STATE - then report that /clear is safe.
disable-model-invocation: true
---

Handover before a context rotation (docs/agents/WORKFLOW.md, "Context rotation"). Current state:

!`py -3 tools/hooks/session_context.py report`

Do these steps in order. Talk to the user in Russian; files stay in English.

1. **Commit.** Review `git status`. Commit every change of this task with an honest message (what works, what
   does not). Do not commit files of another agent or task, local-only data (`data/`, `jobs/*/outputs/`,
   `runs/`) or secrets; name any such leftovers in the handoff ("In progress") instead. After this step no
   change of this task is uncommitted.
2. **PR, only at a task boundary** (the task's acceptance is met, or a stage the user asked to review is done):
   push the branch and open a PR by the project rules (`docs/agents/NAMING.md`, `REVIEW_CHECKLIST.md`; evidence
   in the body). The guard asks before the push. Never merge: merging waits for the user's command. Mid-task:
   no push, no PR.
3. **Transcript.** Make up a fresh random token of 16 letters and digits and run
   `py -3 tools/hooks/save_transcript.py --nonce <token>` (after step 2, so the PR number is known). Your Bash call
   lands in your own transcript before it runs, so the token proves which session is yours. It copies the transcript
   to `logs/transcripts/` of the main checkout and prints the path for the handoff's `Transcript:` line. Exit 1: this
   session's copy for this branch and PR exists and is kept - name it in `Transcript:`. Exit 2 (no or several
   transcripts hold the token, git or I/O failure; nothing is written): `Transcript: -` and the message under
   "Rules broken".
4. **Handoff.** Rewrite `docs/HANDOFF.md` from `docs/HANDOFF.template.md`: every section, facts only, under 7000
   characters. `Commit:` is HEAD after step 1. Put in it what the next session cannot get from git: user
   decisions not yet in code (with dates), questions waiting for the user, rules broken this session, local
   state outside git, the next step in one line. Do not copy history; point to commits and PRs.
5. **Job.** If the task is a job (`jobs/<ID>/`), update `jobs/<ID>/STATE.md` (status, next step, evidence paths).
6. **Repeats.** List the procedures done two or more times in this session (the same command chain, the same
   manual check, the same chain of judgement, the same question resolved). For each, add one line to
   `docs/backlog.md`, section "Reuse proposals", by the rule of three (`docs/agents/WORKFLOW.md`): kind
   (CLI command / skill / pattern), what it is, how many times, this branch, marked `proposal`. Do not create
   the command, skill or pattern. None: skip the step.
7. **Project state.** `docs/PROJECT_STATE.md` changes only on `main` after a merge, by replacing a section
   (`docs/agents/WORKFLOW.md`, "Project state"). In a task branch do not touch it; state changes go into the handoff.
8. **Commit the handoff**: `Handoff: <next step in a few words>` with the handoff, STATE and backlog files. Then
   `git status --short` must show nothing of this task.
9. **Report** in Russian, short: branch, HEAD commit, PR (if any), next step, reuse proposals added (count), then exactly
   «Чекпоинт готов, можно /clear».

If a step cannot be done (a failing hook, a push the user declined), do not hide it: write it into the handoff
under "Rules broken" or "Waiting for the user", and say it in the report instead of «Чекпоинт готов».

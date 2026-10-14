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
3. **Handoff.** Rewrite `docs/HANDOFF.md` from `docs/HANDOFF.template.md`: every section, facts only, under 7000
   characters. `Commit:` is HEAD after step 1. Put in it what the next session cannot get from git: user
   decisions not yet in code (with dates), questions waiting for the user, rules broken this session, local
   state outside git, the next step in one line. Do not copy history; point to commits and PRs.
4. **Job.** If the task is a job (`jobs/<ID>/`), update `jobs/<ID>/STATE.md` (status, next step, evidence paths).
5. **Project state.** `docs/PROJECT_STATE.md` changes only on `main` after a merge. In a task branch do not
   touch it; state changes go into the handoff.
6. **Commit the handoff**: `Handoff: <next step in a few words>` with the handoff and STATE files. Then
   `git status --short` must show nothing of this task.
7. **Report** in Russian, short: branch, HEAD commit, PR (if any), next step, then exactly
   «Чекпоинт готов, можно /clear».

If a step cannot be done (a failing hook, a push the user declined), do not hide it: write it into the handoff
under "Rules broken" or "Waiting for the user", and say it in the report instead of «Чекпоинт готов».

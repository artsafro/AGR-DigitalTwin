---
description: Reconcile docs/HANDOFF.md with git and GitHub after a rotation, list what is open and propose what to take first - without starting it.
disable-model-invocation: true
---

Resume after a context rotation (docs/agents/WORKFLOW.md, "Context rotation"). Current state:

!`py -3 tools/hooks/session_context.py report`

This command only reads and reports. Change no file, run no DCC call, push nothing.

1. **Read** `docs/HANDOFF.md` in full (the state above may cut it), then the parts of `docs/PROJECT_STATE.md`
   and `docs/backlog.md` that name this branch, task, job or the issues in the handoff. For a job also
   `jobs/<ID>/STATE.md`.
2. **Reconcile** the handoff with reality and list every discrepancy:
   - branch and worktree vs the handoff's `Branch:` line;
   - the handoff's `Commit:` vs HEAD (commits since: `git log --oneline <commit>..HEAD`);
   - uncommitted changes (`git status --short`) the handoff does not mention;
   - each PR and issue in the handoff vs its real state (`gh pr view <N> --json state,mergedAt,reviewDecision`,
     `gh issue view <N> --json state`), and open PRs of this branch the handoff does not list;
   - `main` moved since the handoff (`git fetch` then `git log --oneline HEAD..origin/main`), if relevant.
   No discrepancy: say so in one line.
3. **List what is open**, from the handoff: "In progress", "Waiting for the user", "Next step", open PRs and
   issues, "Rules broken" still unresolved. One line each.
4. **Propose** what to take first and why, in one or two lines. A question waiting for the user goes first.
5. **Stop.** Do not start the work. Wait for the user's «да» (or another choice).

Answer in Russian, short: discrepancies, open items, proposal.

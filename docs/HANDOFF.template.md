# Handoff — <YYYY-MM-DD HH:MM>

Branch: `<branch>` · Commit: `<short sha of the work commit before this handoff>` · Worktree: `<path>` · Job: `<ID or ->`

<!-- Written by /handover (.claude/commands/handover.md), read by tools/hooks/session_context.py and /takeover.
Keep the `Branch:` line as is (the hook parses it). Facts only, no history: git log and the pull requests hold
that. The whole file stays under 7000 characters so the SessionStart hook passes it in full. Empty section: "-". -->

## Where we are

<Task goal in one line. What is done and committed (commits, PR numbers). What is verified, with the command or
evidence path.>

## In progress

<Branch, commit, what is left of the task: unfinished steps, failing checks, files touched but not done.
Local state outside git that must survive (untracked outputs, stash entries, probe folders, open DCC scenes).>

## User decisions not in the code

- <decision> (user <YYYY-MM-DD>) — <where it applies>

## Waiting for the user

- <question or approval the work is blocked on; "-" if none>

## Next step

<One line: the very next action.>

## Rules broken

- <rule from AGENTS.md / WORKFLOW.md / a memory, how it was broken and what was done about it; "-" if none>

## Open PRs and issues for this task

- <#N title — state (open / review round k / waiting for merge command)>

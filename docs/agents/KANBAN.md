# Kanban for agent work — Vibe Kanban trial (2026-10-14)

Verdict: **do not use Vibe Kanban.** Its board is gone; what is left fights our worktree, naming and Claude
Code rules. Recommended instead: a **GitHub Projects board over the existing GitHub Issues** (the tracker
`docs/agents/issue-tracker.md` already names). Linear through MCP only if the user wants Linear itself — it
means a second tracker and a migration. Decision: the user's.

## What was checked (facts, with sources)

| Question | Finding | Source |
|---|---|---|
| State of the project | bloop (the company) shut down 2026-04-10; "community maintained". 28 commits since, last release 0.1.44 (2026-09-19), 543 open issues | vibekanban.com/blog/shutdown; GitHub API |
| Kanban board, issues, columns, tags | Live only in Vibe Kanban Cloud (`crates/remote`), retired. The local 0.1.44 UI shows: "Project functionality has been retired … kanban, issue, and workspace flows are no longer available here" — export only. Locally left: a workspace list grouped Needs Attention / Running / Idle | local run `npx vibe-kanban@0.1.44`, port 3077; docs `/docs/cloud/*` |
| Our columns Backlog / Ready / In progress / Review / Needs you / Done, labels `ai`, `ai+human`, `human` | Not possible locally. Cloud had fixed statuses To do / In progress / In review / Done (+ hidden Backlog, Cancelled) and project tags; self-hosting the remote stack (Docker Compose) is the only way back | docs `issue-management`, `self-hosting/deploy-docker` |
| Executors | Claude Code, Codex, Gemini CLI, Copilot, Amp, Cursor CLI, OpenCode, Droid, CCR, Qwen Code | docs `supported-coding-agents` |
| How Claude Code runs | `npx -y @anthropic-ai/claude-code@2.1.119 -p --output-format=stream-json --verbose`, `--permission-prompt-tool=stdio`, `--disallowedTools=AskUserQuestion`, optional `--dangerously-skip-permissions`. A pinned CLI ~175 versions behind ours (2.1.294); `base_command_override` can point at the local `claude` | `crates/executors/src/executors/claude.rs` |
| Worktrees | Own folder `.vibe-kanban-workspaces` (configurable), branch `vk/<id>-<slug>` from a chosen target branch, setup scripts run automatically, periodic "workspace cleanup" of orphaned / expired worktrees | docs `creating-workspaces`; startup log |
| `.claude/agents/`, hooks, `CLAUDE.md` | Not documented. The agent runs `claude -p` inside a git worktree of this repo, and `claude -p` loads project settings, hooks and subagents (verified in PR #107) — so they would apply, but under the pinned 2.1.119 | inference from the above, not run |
| PR and merge | "Open pull request" from the workspace; push only with a PR; the in-app "Merge" pulls the target branch into the working branch; PR merge happens on GitHub. No setting to disable merge buttons is documented | docs `git-operations` |
| Telemetry, network | Starts a client to `https://api.vibekanban.com` (the retired cloud); PostHog analytics unless the key is empty | startup log; README |

The card → agent → branch → PR → Review run on issues #109–#112 was **not done**: there is no card to start
from, and the local workspace wizard did not get past the repository step in this trial (path and base branch
chosen, the screen reset). Per the task, it was not repaired.

## What would break our procedure even with a working board

- **One task = one worktree in `.claude/worktrees/`**: VK makes its own worktrees elsewhere and cleans up
  "expired" ones on its own schedule — ignored outputs kept in a worktree (`jobs/*/outputs/`) can go with them.
- **Branch names** (`docs/agents/NAMING.md`: `harness/`, `job/`, …): VK names branches `vk/<id>-…`.
- **Claude Code version**: the project's hooks (rotation, triggers, subagents) are verified on the current CLI,
  not on a pinned 2.1.119.
- **Merge only on the user's command**: the buttons exist and cannot be turned off.
- **DCC work**: one owner per scene and MCP port; parallel VK agents would fight over 3ds Max / Blender ports.

## Recommendation

Use a GitHub Projects (v2) board on `artsafro/AGR-DigitalTwin` issues: a Status field with Backlog / Ready /
In progress / Review / Needs you / Done, labels `ai`, `ai+human`, `human` next to the triage labels. Agents
already use `gh` and the GitHub MCP; worktrees, branches, hooks and merge rules stay ours. Linear (official
remote MCP) is an option only if the user prefers its UI — it would duplicate GitHub Issues.

## Local leftovers of the trial

`~/.vibe-kanban/` (binary 0.1.44 and config, ~48 MB) and `C:/x/vk/vk.log`. Vibe Kanban created no worktree or
branch in the repo. Remove the folder when no longer needed.

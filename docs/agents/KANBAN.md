# Kanban board — GitHub Projects

Board: <https://github.com/users/artsafro/projects/1> (project `AGR-DigitalTwin`, number 1, owner
`artsafro`, private, linked to `artsafro/AGR-DigitalTwin`). Set up by the user's decision on 2026-10-14 [D071].

GitHub Issues stay the source of truth: the board only adds two fields to them. A pull request is not a
card; it links to its issue with `Closes #N` in the description.

## Fields

| Field | Values | Meaning |
|---|---|---|
| Status | Backlog | not ready: `needs-triage`, `needs-info` or no labels |
| | Ready | specified, can be taken (`ready-for-agent` or `ready-for-human`) |
| | In progress | an agent or the user works on it (one branch, one worktree) |
| | Review | PR open |
| | Needs you | waits for the user's decision on model or data; the question is in an issue comment |
| | Done | closed |
| Agent | Claude / Codex / Antigravity / Human | default owner by `docs/agents/ROLES.md` |

Triage labels (`docs/agents/triage-labels.md`) and area labels stay as they are.

## Who moves cards

- GitHub workflows of the project: item added → Backlog, PR linked → Review, item closed and PR merged →
  Done, auto-add of new repo issues. Set in the project UI (Settings → Workflows); the API cannot enable them.
- The agent that takes an issue: Ready → In progress at the start; → Needs you when it stops on the user's
  decision. Commands: `docs/agents/issue-tracker.md`.

## Parallel work

One card = one session = one worktree (a new Code session in the desktop app, or a Codex task), as
`AGENTS.md` requires. Up to 3 agents at once. At most one agent per DCC application (3ds Max, Blender,
Revit, AutoCAD): a scene and its MCP port have one owner; the others work on files, code and docs.

## Vibe Kanban — rejected (trial 2026-10-14, 0.1.44)

The board, issues and columns lived only in Vibe Kanban Cloud, retired after bloop shut down
(2026-04-10, vibekanban.com/blog/shutdown). The local app keeps only workspaces: its own worktree
folder with automatic cleanup, `vk/<id>-…` branches, Claude Code pinned to 2.1.119, merge buttons that
cannot be disabled. Getting the board back means self-hosting the remote stack (Docker Compose) or an
old 0.0.x release; neither was pursued. Local leftovers: `~/.vibe-kanban/` (~48 MB), `C:/x/vk/vk.log`.

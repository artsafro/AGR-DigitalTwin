# Herdr workspaces

How this project uses Herdr (0.9.3, Windows) for Claude Code, Codex and Antigravity.
Tools live in `tools/herdr/`; Herdr's config (`%APPDATA%\herdr\config.toml`) and the
local plugin `artsafro.dev-layout` point there.

## Layout of an agent tab

```
┌─────────┬─────────────────────────┬──────────────┐
│ Sidebar │                         │ TOOLS        │
│ (files, │  AGENT                  ├──────────────┤
│  git)   │  Claude / Codex / agy   │ CHEAT        │
│         ├────────────────┬────────┴──────────────┤
│         │ LOGS           │ HUD                   │
└─────────┴────────────────┴───────────────────────┘
```

- **AGENT** — the one writing agent of this worktree.
- **TOOLS** — every tool call of the AGENT pane with ✓ / ✗ (`agent_feed.py --mode tools`).
- **LOGS** — your prompts, file edits, commits, failed commands, MCP calls, and new lines of
  project logs (`Unreal/**/Saved/Logs`, `logs/`, `tools/**/*.log`).
- **CHEAT** — what to create (folder / pane / tab / worktree) — `cheat.py`.
- **HUD** — agents and their state, usage limits, large-file mode, keys — `hud.py`.
- Feeds read Claude and Codex session logs; Antigravity's log is binary, so its feeds
  show a "no readable log" note.

Panels are found by label, so they can be moved or resized freely; Ctrl+B Shift+U restores
only what is missing.

## What to create

| Need | Create |
|---|---|
| Same files and same task, fresh conversation | tab / new chat |
| Console, git, logs beside the agent | pane |
| New task, experiment, parallel implementation | worktree + branch (its own Herdr workspace) |
| Arrange files | folder |

One worktree = one writing agent; a second agent there only reads or reviews.
Worktrees live in `C:\Users\artsafro\HerdrWorktrees\AGR-DigitalTwin\<name>`.

## Keys

Ctrl+B Shift+H opens the full cheat sheet (`tools/herdr/cheatsheet.txt`); the HUD lists
the same keys. Letter keys also work in the Russian layout.

## Getting the latest changes

Ctrl+B Shift+M (`update-from-main.ps1`) in a tab: on `main` it runs `git pull --ff-only`;
on a task branch it merges `main`, so the worktree sees what other agents published. It
skips a checkout with uncommitted changes or a working agent and aborts on conflict.
The sidebar's "Sync Changes" button also **pushes** — do not use it to fetch.

## Rules

- Run Herdr **non-elevated**: Codex refuses to start its daemon under an administrator
  terminal, and elevated agents can change the whole system. If the tab title says
  "Администратор", run `herdr server stop` and start Herdr from a normal terminal.
- Agents do not start, prompt or drive other agents; handoff (Ctrl+B A) is started by the user.
- Agents may use read-only Herdr CLI (`herdr pane list`, `pane get`, `pane read`) to inspect
  the workspace.

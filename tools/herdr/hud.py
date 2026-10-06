"""Herdr HUD pane: hotkeys, agent state, and locally reported usage. Refreshes every 2 s.

Agents come from `herdr pane list`. For Claude panes, statusline.py leaves
%LOCALAPPDATA%/claude-hud/<pane>.json with the live session id and context %;
task progress is read from ~/.claude/tasks/<session>/*.json.
Codex reports no progress, so it shows state only.
"""
import glob
import json
import re
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation

HUD_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "claude-hud")
TASKS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "tasks")

RESET, DIM, BOLD = "\033[0m", "\033[2m", "\033[1m"
STATE = {  # glyph, color
    "working": ("●", "\033[33m"),
    "blocked": ("?", "\033[31m"),
    "done": ("✓", "\033[32m"),
    "idle": ("○", "\033[90m"),
}

HOTKEYS = [  # (keys after Ctrl+B, action) shown as a two-column table; S-H = full sheet
    ("v", "split →"), ("-", "split ↓"),
    ("x", "close"), ("z", "zoom"),
    ("c", "new tab"), ("w", "workspace"),
    ("S-G", "worktree"), ("S-L", "layout"),
    ("S-T", "rename"), ("S-H", "help"),
    ("S-V", "review"), ("S-E", "sidebar"),
    ("a", "handoff"), ("t", "annotate"),
    ("f", "files"), ("i", "image"),
    ("S-K", "big files"), ("q", "detach"),
    ("S-↔", "move pane"), ("C-↔", "resize"),
    ("S-U", "refresh UI"), ("S-M", "get latest"),
    ("r", "resize mode"),
]


def herdr(*args):
    try:
        out = subprocess.run(["herdr", *args], capture_output=True, text=True,
                             encoding="utf-8", timeout=3)
        return json.loads(out.stdout).get("result", {})
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def tasks(session):
    done = total = 0
    current = ""
    for path in glob.glob(os.path.join(TASKS_DIR, session, "*.json")):
        task = read_json(path) or {}
        status = task.get("status")
        if status not in ("pending", "in_progress", "completed"):
            continue
        total += 1
        if status == "completed":
            done += 1
        elif status == "in_progress" and not current:
            current = task.get("activeForm") or task.get("subject") or ""
    return done, total, current


CODEX_SESSIONS = os.path.join(os.path.expanduser("~"), ".codex", "sessions")
_codex_cache = {"at": 0.0, "value": None}


def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        obj = list(obj.values())
    if isinstance(obj, list):
        for v in obj:
            found = find_key(v, key)
            if found is not None:
                return found
    return None


def codex_limits():
    """Latest rate_limits Codex wrote into its session logs: (record, iso timestamp).

    Rescanned at most once a minute; Codex only refreshes it while it runs.
    """
    if time.time() - _codex_cache["at"] < 60:
        return _codex_cache["value"]
    best = None
    files = sorted(glob.glob(os.path.join(CODEX_SESSIONS, "**", "rollout-*.jsonl"), recursive=True),
                   key=os.path.getmtime, reverse=True)[:10]
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if "rate_limits" not in line:
                        continue
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    rl = find_key(d, "rate_limits")
                    if rl and (rl.get("primary") or rl.get("secondary") or rl.get("credits")):
                        if best is None or d.get("timestamp", "") > best[1]:
                            best = (rl, d.get("timestamp", ""))
        except OSError:
            continue
    _codex_cache.update(at=time.time(), value=best)
    return best


def claude_limits():
    states = [read_json(p) for p in sorted(glob.glob(os.path.join(HUD_DIR, "*.json")),
                                           key=os.path.getmtime, reverse=True)]
    return next((s["rate_limits"] for s in states if s and s.get("rate_limits")), None)


def when(epoch):
    t = time.localtime(epoch)
    return time.strftime("%H:%M" if time.strftime("%d", t) == time.strftime("%d") else "%d.%m", t)


def window_name(minutes):
    return f"{minutes // 1440}d" if minutes and minutes >= 1440 else f"{(minutes or 0) // 60}h"


def limit_line(name, window, used, reset, width, note=""):
    left = max(0.0, 100.0 - float(used))
    color = "\033[31m" if left < 15 else "\033[33m" if left < 40 else "\033[32m"
    reset_txt = f" →{when(reset)}" if reset else ""
    return f" {name:<7}{window:<3}{color}{bar(left / 100, width)}{RESET} {left:>3.0f}%{DIM}{reset_txt}{note}{RESET}"


def remaining_window(rl, key):
    window = rl.get(key) or {}
    used = window.get("used_percent")
    if used is None:
        return None
    return f"{window_name(window.get('window_minutes'))} {max(0, 100 - float(used)):.0f}%"


def credit_balance(rl):
    credits = rl.get("credits") or {}
    if credits.get("unlimited"):
        return "unlimited"
    balance = credits.get("balance")
    if balance is None:
        return None
    try:
        return format(Decimal(str(balance)).normalize(), "f")
    except (InvalidOperation, TypeError, ValueError):
        return str(balance)


def short_timestamp(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%H:%M" if dt.date() == datetime.now().astimezone().date()
                           else "%d.%m %H:%M")
    except (AttributeError, ValueError):
        return "unknown time"


def limit_row(name, window, used, reset, width):
    left = max(0.0, 100.0 - float(used))
    color = "\033[31m" if left < 15 else "\033[33m" if left < 40 else "\033[32m"
    reset_txt = f" ↻{when(reset)}" if reset else ""
    return (f"{name:<7}{DIM}{window:<3}{RESET}{color}{bar(left / 100, width)}{RESET}"
            f" {left:>3.0f}%{DIM}{reset_txt}{RESET}")


def limits(cols):
    width = max(min(cols - 23, 10), 3)
    lines = [f"{BOLD}LIMITS{RESET} {DIM}left{RESET}"]
    cl = claude_limits() or {}
    rows = [(win, cl[key]) for key, win in (("five_hour", "5h"), ("seven_day", "7d"))
            if (cl.get(key) or {}).get("used_percentage") is not None]
    for i, (win, w) in enumerate(rows):
        lines.append(limit_row("claude" if i == 0 else "", win, w["used_percentage"], w.get("resets_at"), width))
    if not rows:
        lines.append(f"claude {DIM}no data yet{RESET}")
    cx = codex_limits()
    if cx:
        rl, ts = cx
        first = True
        for key in ("primary", "secondary"):
            w = rl.get(key) or {}
            if w.get("used_percent") is not None:
                lines.append(limit_row("codex" if first else "", window_name(w.get("window_minutes")),
                                       w["used_percent"], w.get("resets_at"), width))
                first = False
        balance = credit_balance(rl)
        if balance not in (None, "0"):
            try:
                balance = f"{float(balance):.0f}"
            except ValueError:
                pass
            lines.append(f"       {DIM}credits{RESET} {balance}")
        lines.append(f"       {DIM}as of {short_timestamp(ts)}{RESET}")
    else:
        lines.append(f"codex  {DIM}no data yet{RESET}")
    lines.append(f"agy    {DIM}no local data{RESET}")
    return [clip(l, cols) for l in lines]


PROJECT_REPO = r"C:\Users\artsafro\AGR-DigitalTwin"


def big_files_line():
    """State of the link-large pre-commit toggle (git config twin.linkLarge)."""
    def cfg(key):
        try:
            return subprocess.run(["git", "-C", PROJECT_REPO, "config", "--get", key],
                                  capture_output=True, text=True, timeout=2).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    if cfg("twin.linkLarge") == "false":
        return f"big    {DIM}files committed (LFS){RESET}"
    return f"big    \033[32mlinks ON{RESET} {DIM}>{cfg('twin.linkLargeMb') or 50} MB{RESET}"


def bar(fraction, width):
    """Thin line gauge; the empty part is dim. Callers colour the filled part."""
    filled = round(fraction * width)
    return "━" * filled + f"{DIM}{'─' * (width - filled)}{RESET}"


ANSI = re.compile(r"\033\[[0-9;?]*[A-Za-z]")


def clip(text, width):
    """Cut to `width` visible characters; colour codes do not count."""
    out, seen, pos = [], 0, 0
    for m in ANSI.finditer(text + "\033[0m"):
        for ch in text[pos:m.start()]:
            if seen >= width:
                return "".join(out)[:-1] + "…" + RESET
            out.append(ch)
            seen += 1
        out.append(m.group())
        pos = m.end()
    return "".join(out)


def agent_rows(cols):
    """One line per agent: name (its tab, as in the radar sidebar), state, context/tasks."""
    tabs = {t["tab_id"]: t.get("label", "") for t in herdr("tab", "list").get("tabs", [])}
    agents = [p for p in herdr("pane", "list").get("panes", []) if p.get("agent")]
    agents.sort(key=lambda p: (p.get("agent_status") != "blocked", p.get("agent_status") != "working"))
    lines = [f"{BOLD}AGENTS{RESET}"]
    if not agents:
        return lines + [f"{DIM}no agents running{RESET}"]
    for p in agents:
        status = p.get("agent_status", "unknown")
        glyph, color = STATE.get(status, ("·", "\033[35m"))
        tab = tabs.get(p.get("tab_id"), "")
        name = tab if tab and not tab.isdigit() else p["agent"]
        name = re.sub(r"^\d+\s*·\s*", "", name)          # drop auto-title's "1 · "
        extra = ""
        state = read_json(os.path.join(HUD_DIR, p["pane_id"].replace(":", "_") + ".json"))
        if p["agent"] == "claude" and state:
            done, total, _ = tasks(state.get("session", ""))
            ctx = state.get("ctx")
            extra = (f"{done}/{total} " if total else "") + (f"ctx {ctx:.0f}%" if isinstance(ctx, (int, float)) else "")
        name_w = min(max(cols - 13, 6), 22)               # fixed columns: name | glyph | detail
        name = name if len(name) <= name_w else name[: name_w - 1] + "…"
        lines.append(f"{name:<{name_w}} {color}{glyph}{RESET} {DIM}{(extra or status)[:11]}{RESET}")
    return lines


def key_table(cols):
    lines = [f"{BOLD}KEYS{RESET} {DIM}Ctrl+B +{RESET}"]
    per_row = 3 if cols >= 48 else 2                  # wide HUD: three columns, fewer rows
    cell = max(cols // per_row, 12)
    for i in range(0, len(HOTKEYS), per_row):
        cells = []
        for key, action in HOTKEYS[i:i + per_row]:
            text = action[: cell - 5]
            cells.append(f"{key:<4}{DIM}{text}{RESET}" + " " * max(cell - 4 - len(text), 1))
        lines.append(clip("".join(cells).rstrip(), cols))
    return lines


def render():
    size = shutil.get_terminal_size((60, 20))
    cols, rows = size.columns - 1, size.lines        # last column free: no auto-wrap
    agents = agent_rows(cols)
    lim = limits(cols) + [clip(big_files_line(), cols)]
    keys = key_table(cols)
    lines = agents + [""] + lim + [""] + keys
    if len(lines) > rows:                            # short pane: drop spacing and detail lines
        lim = [l for l in lim if not any(s in l for s in ("as of", "no local data"))]   # credits stay
        lines = agents + lim + keys
    if len(lines) > rows:                            # still short: section titles go too
        lines = agents + lim[1:] + keys[1:]
    return lines


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    # Alternate screen + hidden cursor; each frame overwrites in place, no scrollback.
    sys.stdout.write("\033[?1049h\033[?25l")
    try:
        while True:
            rows = shutil.get_terminal_size((60, 20)).lines
            frame = render()[:rows]
            sys.stdout.write("\033[H" + "\033[K\r\n".join(frame) + "\033[K\033[J")
            sys.stdout.flush()
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\033[?1049l" + RESET)


if __name__ == "__main__":
    main()

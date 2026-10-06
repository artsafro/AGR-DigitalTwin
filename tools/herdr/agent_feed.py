"""Live feed of what the agent in a Herdr pane is doing, read from its transcript.

  py -3 agent_feed.py --pane w3:p1 --mode tools   every tool call, with ✓ / ✗
  py -3 agent_feed.py --pane w3:p1 --mode logs    user prompts, file changes, commits,
                                                  failed commands, MCP calls + project logs

Claude Code transcripts are discovered through its statusline state. Codex
transcripts are discovered from the Herdr pane's active session id. Both are read
only; nothing here writes to either transcript.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

HUD_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "claude-hud")
PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")
CODEX_SESSIONS = os.path.join(os.path.expanduser("~"), ".codex", "sessions")
BACKLOG_BYTES = 400_000          # history shown when a transcript is first opened
PROJECT_LOGS = ["Unreal/**/Saved/Logs/*.log", "logs/**/*.log", "tools/**/*.log"]
SHELL_KEEP = re.compile(r"\bgit\s+(commit|push|merge|rebase|checkout\s+-b|switch\s+-c)\b"
                        r"|\bherdr\s+worktree\b"
                        # project scripts only: `py -3 tools/x.py`, not a venv's Scripts\python.exe
                        r"|(?<![\w$])(py|python)(\.exe)?(\s+-3)?\s+[\"']?Scripts[/\\]")

R, DIM, BOLD = "\033[0m", "\033[2m", "\033[1m"
GREEN, RED, YELLOW, CYAN = "\033[32m", "\033[31m", "\033[33m", "\033[36m"


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def short_path(p):
    p = str(p).replace("\\", "/")
    parts = p.rstrip("/").split("/")
    return "/".join(parts[-2:]) if len(parts) > 1 else p


def summarize(name, inp):
    """(label, text) for one tool call."""
    inp = inp or {}
    if name in ("Bash", "PowerShell"):
        cmd = inp.get("command", "").strip().splitlines()
        return "ps" if name == "PowerShell" else "sh", inp.get("description") or (cmd[0] if cmd else "")
    if name in ("Read", "Edit", "Write", "NotebookEdit"):
        return name.lower(), short_path(inp.get("file_path") or inp.get("notebook_path", ""))
    if name in ("Grep", "Glob"):
        return name.lower(), inp.get("pattern", "")
    if name == "Agent":
        return "agent", inp.get("description", "")
    if name in ("WebFetch", "WebSearch"):
        return "web", inp.get("url") or inp.get("query", "")
    if name == "Skill":
        return "skill", inp.get("skill", "")
    if name.startswith("Task"):
        return "task", inp.get("subject") or f"#{inp.get('taskId', '')} {inp.get('status', '')}"
    if name.startswith("mcp__"):
        _, server, tool = (name.split("__", 2) + ["", ""])[:3]
        return "mcp", f"{server}: {tool}"
    first = next((str(v) for v in inp.values() if isinstance(v, (str, int))), "")
    return name[:6].lower(), first


def keep_in_logs(name, inp):
    """None = never, True = always, 'error' = only if it fails."""
    if name in ("Edit", "Write", "NotebookEdit", "Agent", "Skill") or name.startswith("mcp__"):
        return True
    if name in ("Bash", "PowerShell"):
        return True if SHELL_KEEP.search((inp or {}).get("command", "")) else "error"
    return None


def clock(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%H:%M")
    except (AttributeError, ValueError):
        return "--:--"


def prompt_text(content):
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        if any(b.get("type") == "tool_result" for b in content if isinstance(b, dict)):
            return None
        text = " ".join(b.get("text", "") for b in content if isinstance(b, dict)
                        and b.get("type") in ("text", "input_text"))
    else:
        return None
    text = re.sub(r"<[^>]+>.*?</[^>]+>", "", text, flags=re.S).strip()
    return text.splitlines()[0] if text else None


class Feed:
    def __init__(self, mode):
        self.mode = mode
        self.entries = []          # dicts: time, mark, label, text, hidden
        self.pending = {}          # tool_use_id -> entry
        self.path = None
        self.offset = 0
        self.rest = b""
        self.log_path = None
        self.log_offset = 0

    def open(self, path):
        self.__init__(self.mode)
        self.path = path
        size = os.path.getsize(path)
        self.offset = max(0, size - BACKLOG_BYTES)
        self.skip_partial = self.offset > 0

    def poll_transcript(self):
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                chunk = f.read()
        except OSError:
            return False
        if not chunk:
            return False
        self.offset += len(chunk)
        data = self.rest + chunk
        lines = data.split(b"\n")
        self.rest = lines.pop()
        if self.skip_partial and lines:
            lines.pop(0)
            self.skip_partial = False
        for line in lines:
            try:
                self.handle(json.loads(line))
            except ValueError:
                continue
        return True

    def add(self, **entry):
        entry.setdefault("hidden", False)
        self.entries.append(entry)
        del self.entries[:-500]
        return entry

    def handle(self, d):
        if d.get("type") == "response_item":
            self.handle_codex(d)
            return
        self.handle_claude(d)

    def handle_claude(self, d):
        msg = d.get("message") or {}
        content = msg.get("content")
        when = clock(d.get("timestamp"))
        if d.get("type") == "user" and not d.get("isMeta") and self.mode == "logs":
            text = prompt_text(content)
            if text:
                self.add(time=when, mark="»", color=CYAN, label="you", text=text)
        if not isinstance(content, list):
            return
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                name, inp = b.get("name", "?"), b.get("input")
                label, text = summarize(name, inp)
                keep = True if self.mode == "tools" else keep_in_logs(name, inp)
                if keep is None:
                    continue
                self.pending[b.get("id")] = self.add(time=when, mark="…", color=YELLOW, label=label,
                                                     text=text, hidden=(keep == "error"))
            elif b.get("type") == "tool_result":
                e = self.pending.pop(b.get("tool_use_id"), None)
                if e:
                    failed = bool(b.get("is_error"))
                    e["mark"], e["color"] = ("✗", RED) if failed else ("✓", GREEN)
                    if e["hidden"] and failed:
                        e["hidden"] = False

    def handle_codex(self, d):
        payload = d.get("payload") or {}
        kind = payload.get("type")
        when = clock(d.get("timestamp"))

        if kind == "message" and payload.get("role") == "user" and self.mode == "logs":
            text = prompt_text(payload.get("content"))
            if text:
                self.add(time=when, mark="»", color=CYAN, label="you", text=text)
            return

        if kind in ("custom_tool_call", "function_call"):
            name = payload.get("name", "tool")
            inp = payload.get("input", payload.get("arguments"))
            label, text = summarize_codex(name, inp)
            if self.mode == "logs":       # same rule as Claude: changes, MCP, commits, failures
                keep = label in ("edit", "mcp") or (label == "sh" and SHELL_KEEP.search(text))
            else:
                keep = True
            call_id = payload.get("call_id")
            self.pending[call_id] = self.add(time=when, mark="…", color=YELLOW,
                                             label=label, text=text, hidden=not keep)
        elif kind in ("custom_tool_call_output", "function_call_output"):
            entry = self.pending.pop(payload.get("call_id"), None)
            if entry:
                output = payload.get("output")
                failed = bool(payload.get("is_error")) or output_failed(output)
                entry["mark"], entry["color"] = (("✗", RED) if failed else ("✓", GREEN))

    def poll_project_log(self, cwd):
        if self.mode != "logs" or not cwd:
            return False
        files = [f for pat in PROJECT_LOGS for f in glob.glob(os.path.join(cwd, pat), recursive=True)]
        if not files:
            return False
        newest = max(files, key=os.path.getmtime)
        if newest != self.log_path:
            self.log_path, self.log_offset = newest, max(0, os.path.getsize(newest) - 4000)
        try:
            with open(newest, "rb") as f:
                f.seek(self.log_offset)
                chunk = f.read()
        except OSError:
            return False
        if not chunk:
            return False
        self.log_offset += len(chunk)
        name = os.path.basename(newest)
        for line in chunk.decode("utf-8", "replace").splitlines()[-50:]:
            if line.strip():
                color = RED if re.search(r"error", line, re.I) else YELLOW if re.search(r"warn", line, re.I) else DIM
                self.add(time=datetime.now().strftime("%H:%M"), mark="│", color=color,
                         label=name[:6], text=line.strip())
        return True


def summarize_codex(name, inp):
    """One-line summary of a Codex call: first command line, patched file, or tool name.

    Never prints the full script; only the first line of a shell command.
    """
    label = str(name or "tool")[:8]
    if name == "exec" and isinstance(inp, str):
        # Paths sit inside a JS string: escaped backslashes, lines ended by a literal "\n".
        files = re.findall(r"\*\*\* (?:Update|Add|Delete) File: (.+?)(?:\\n|\n|\"|$)", inp)
        if files:
            more = f" +{len(files) - 1}" if len(files) > 1 else ""
            return "edit", short_path(files[0].replace("\\\\", "\\").strip()) + more
        cmd = re.search(r"\bcmd\s*:\s*([\"'`])((?:\\.|(?!\1).)*)\1", inp, re.S)
        if cmd:
            text = cmd.group(2).encode().decode("unicode_escape", "ignore") if "\\" in cmd.group(2) else cmd.group(2)
            line = next((l.strip() for l in text.splitlines() if l.strip()), "")
            return "sh", line
        nested = list(dict.fromkeys(re.findall(r"\btools\.([A-Za-z0-9_]+)\s*\(", inp)))
        mcp = [n for n in nested if "__" in n]
        if mcp:
            server, _, tool = mcp[0].partition("__")
            return ("web" if server == "web" else "mcp"), f"{server}: {tool}"
        if nested:
            return "exec", ", ".join(nested[:3])
        return "exec", "Codex tool call"
    if isinstance(inp, dict):
        safe = inp.get("description") or inp.get("title") or inp.get("name")
        if safe:
            return label, str(safe).splitlines()[0]
    return label, "Codex tool call"


def output_failed(output):
    if isinstance(output, dict):
        if output.get("isError") or output.get("is_error"):
            return True
        output = json.dumps(output, ensure_ascii=False)
    if not isinstance(output, str):
        return False
    return bool(re.search(r'"(?:exit_code|exitCode)"\s*:\s*[1-9]\d*|'
                          r'"isError"\s*:\s*true|\b(?:command failed|traceback)\b',
                          output, re.I))

_PANE_SESSION_CACHE = {}


def find_transcript(pane):
    state = read_json(os.path.join(HUD_DIR, pane.replace(":", "_") + ".json")) or {}
    path = state.get("transcript")
    if path and os.path.exists(path):
        return path
    session = state.get("session")
    if session:
        hits = glob.glob(os.path.join(PROJECTS, "*", f"{session}.jsonl"))
        if hits:
            return hits[0]

    now = time.monotonic()
    cached = _PANE_SESSION_CACHE.get(pane)
    if cached and now - cached[0] < 2:
        return cached[1]
    path = None
    try:
        out = subprocess.run(["herdr", "pane", "get", pane], capture_output=True, text=True,
                             encoding="utf-8", timeout=3)
        info = json.loads(out.stdout)["result"]["pane"]
        agent = info.get("agent")
        session_id = (info.get("agent_session") or {}).get("value")
        if agent == "codex" and session_id:
            hits = glob.glob(os.path.join(CODEX_SESSIONS, "**", f"rollout-*-{session_id}.jsonl"),
                             recursive=True)
            if hits:
                path = max(hits, key=os.path.getmtime)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        pass
    _PANE_SESSION_CACHE[pane] = (now, path)
    return path
    return None


def pane_cwd(pane):
    try:
        out = subprocess.run(["herdr", "pane", "get", pane], capture_output=True, text=True,
                             encoding="utf-8", timeout=3)
        return json.loads(out.stdout)["result"]["pane"].get("cwd")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return None


_AGENT_CACHE = {}


def pane_agent(pane):
    """Agent Herdr detected in the pane (cached 10 s)."""
    hit = _AGENT_CACHE.get(pane)
    if hit and time.monotonic() - hit[0] < 10:
        return hit[1]
    try:
        out = subprocess.run(["herdr", "pane", "get", pane], capture_output=True, text=True,
                             encoding="utf-8", timeout=3)
        agent = json.loads(out.stdout)["result"]["pane"].get("agent")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        agent = None
    _AGENT_CACHE[pane] = (time.monotonic(), agent)
    return agent


def render(feed, pane, title):
    cols, rows = shutil.get_terminal_size((80, 20))
    head = f"{BOLD}{title}{R} {DIM}{pane}{R}"
    shown = [e for e in feed.entries if not e["hidden"]][-(rows - 1):]
    lines = [head]
    if not feed.path:
        agent = pane_agent(pane)
        if agent and agent not in ("claude", "codex"):
            note = f"{agent}: no readable log (Claude/Codex only)"
            lines.append(f"{DIM}{note[: max(cols - 2, 10)]}{R}")
        else:
            lines.append(f"{DIM}waiting for the agent's first status line…{R}")
    elif not shown:
        lines.append(f"{DIM}nothing yet{R}")
    for e in shown:
        prefix = f"{e['time']} {e['mark']} {e['label']:<6} "
        room = max(cols - 1 - len(prefix), 4)   # keep the last column free (no auto-wrap)
        text = e["text"] if len(e["text"]) <= room else e["text"][: room - 1] + "…"
        lines.append(f"{DIM}{e['time']}{R} {e['color']}{e['mark']}{R} {e['label']:<6} {text}")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pane", required=True, help="Herdr pane id of the agent to follow")
    ap.add_argument("--mode", choices=["tools", "logs"], default="tools")
    args = ap.parse_args()
    title = "TOOLS" if args.mode == "tools" else "LOGS"

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write("\033[?1049h\033[?25l")
    feed, cwd, last_cwd_check, dirty, size = Feed(args.mode), None, 0.0, True, None
    try:
        while True:
            if shutil.get_terminal_size() != size:   # pane resized: redraw at the new width
                size, dirty = shutil.get_terminal_size(), True
            path = find_transcript(args.pane)
            if path and path != feed.path:
                feed.open(path)
                dirty = True
            if feed.path:
                dirty |= feed.poll_transcript()
            if time.time() - last_cwd_check > 10:
                cwd, last_cwd_check = pane_cwd(args.pane), time.time()
            dirty |= feed.poll_project_log(cwd)
            if dirty:
                sys.stdout.write("\033[H" + "\033[K\r\n".join(render(feed, args.pane, title)) + "\033[K\033[J")
                sys.stdout.flush()
                dirty = False
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\033[?1049l" + R)


if __name__ == "__main__":
    main()

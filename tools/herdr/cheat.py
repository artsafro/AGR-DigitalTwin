"""Herdr CHEAT pane: what to create (folder / pane / tab / worktree) and the rule.

Static text, redrawn only when the pane is resized. Full sheet: Ctrl+B Shift+H.
"""
import shutil
import sys
import time

R, DIM, BOLD = "\033[0m", "\033[2m", "\033[1m"

WHAT = [
    ("папка", "новые файлы, часть проекта"),
    ("pane", "окно рядом, та же ветка"),
    ("tab/chat", "новый chat, та же задача"),
    ("worktree", "новая задача / параллельно"),
]
RULE = [
    ("те же файлы и задача", "tab"),
    ("консоль, git, логи", "pane"),
    ("задача, эксперимент", "worktree"),
    ("разложить файлы", "папка"),
]


def clip(text, width):
    return text if len(text) <= width else text[: max(width - 1, 0)] + "…"


def render():
    cols = shutil.get_terminal_size((40, 12)).columns - 1   # last column free: no auto-wrap
    lines = [f"{BOLD}ЧТО СОЗДАВАТЬ{R}"]
    for what, why in WHAT:
        lines.append(f"{what:<9}{DIM}{clip(why, cols - 9)}{R}")
    lines += ["", f"{BOLD}ПРАВИЛО{R}"]
    for case, choice in RULE:
        room = cols - len(choice) - 3
        lines.append(f"{DIM}{clip(case, room)}{R} → {BOLD}{choice}{R}")
    return lines


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write("\033[?1049h\033[?25l")
    size = None
    try:
        while True:
            if shutil.get_terminal_size() != size:
                size = shutil.get_terminal_size()
                frame = render()[: size.lines]
                sys.stdout.write("\033[H" + "\033[K\r\n".join(frame) + "\033[K\033[J")
                sys.stdout.flush()
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\033[?1049l" + R)


if __name__ == "__main__":
    main()

"""Regenerate .claude/skills/ from the canonical .agents/skills/.

Usage: py -3 tools/sync_skills.py [--check]

Vendored skills listed in skills-lock.json are not copied: Claude has user-level copies.
--check exits 1 and lists differences instead of writing.
"""
import filecmp
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".agents" / "skills"
TARGET = ROOT / ".claude" / "skills"


def project_skills() -> list[str]:
    lock = ROOT / "skills-lock.json"
    vendored = set(json.loads(lock.read_text(encoding="utf-8"))["skills"]) if lock.is_file() else set()
    return sorted(p.name for p in SOURCE.iterdir() if p.is_dir() and p.name not in vendored)


def differences() -> list[str]:
    wanted = project_skills()
    present = sorted(p.name for p in TARGET.iterdir() if p.is_dir()) if TARGET.is_dir() else []
    diffs = [f"extra in .claude/skills: {n}" for n in present if n not in wanted]
    for name in wanted:
        cmp = filecmp.dircmp(SOURCE / name, TARGET / name) if (TARGET / name).is_dir() else None
        if cmp is None:
            diffs.append(f"missing in .claude/skills: {name}")
            continue
        stack = [(name, cmp)]
        while stack:
            rel, c = stack.pop()
            diffs += [f"{rel}/{f}: differs or missing" for f in c.left_only + c.right_only + c.diff_files]
            stack += [(f"{rel}/{k}", v) for k, v in c.subdirs.items()]
    return diffs


def sync() -> None:
    if TARGET.is_dir():
        shutil.rmtree(TARGET)
    for name in project_skills():
        shutil.copytree(SOURCE / name, TARGET / name)


if __name__ == "__main__":
    if "--check" in sys.argv:
        found = differences()
        print("\n".join(found) or "in sync")
        sys.exit(1 if found else 0)
    sync()
    print(f"synced {len(project_skills())} skills to {TARGET.relative_to(ROOT)}")

"""Facts for /reuse-scan (.claude/commands/reuse-scan.md): similar job scripts across jobs, recent cases, usage.

Usage: py -3 tools/reuse_candidates.py [--days 7] [--min-ratio 0.6]

Prints, for the tracked jobs/*/scripts/* files:
- pairs from different jobs with the same file name or text similarity >= --min-ratio (difflib on lines),
  marked `recent` when either file changed within --days (git log);
- the subjects of commits that touched docs/cases.md within --days.
Judgement (is it a src/ candidate, a skill, a pattern) stays with the agent; this script only measures.
"""
import argparse
import difflib
import subprocess
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 200_000


def git(*args):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:                            # a failure is not a measured absence (review 2 of #107)
        sys.exit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.splitlines()


def scripts():
    return [p for p in git("ls-files", "jobs/*/scripts/*") if (ROOT / p).is_file()
            and (ROOT / p).stat().st_size <= MAX_BYTES]


def similar_pairs(paths, min_ratio):
    texts = {p: (ROOT / p).read_text(encoding="utf-8", errors="replace").splitlines() for p in paths}
    pairs = []
    for a, b in combinations(paths, 2):
        if a.split("/")[1] == b.split("/")[1] or Path(a).suffix != Path(b).suffix:
            continue                                 # same job, or different languages
        same_name = Path(a).name == Path(b).name
        m = difflib.SequenceMatcher(None, texts[a], texts[b], autojunk=False)
        if not same_name and m.real_quick_ratio() < min_ratio:
            continue
        ratio = m.ratio()
        if same_name or ratio >= min_ratio:
            pairs.append((ratio, same_name, a, b, len(texts[a]), len(texts[b])))
    return sorted(pairs, reverse=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--min-ratio", type=float, default=0.6)
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    since = f"--since={a.days}.days"
    recent = set(git("log", since, "--name-only", "--format=", "--", "jobs"))
    paths = scripts()
    pairs = similar_pairs(paths, a.min_ratio)
    print(f"Job scripts: {len(paths)} tracked, {len(recent & set(paths))} changed in {a.days} days; "
          f"{len(pairs)} cross-job pair(s) with the same name or similarity >= {a.min_ratio}:")
    for ratio, same, x, y, nx, ny in pairs[:40]:
        flag = " recent" if x in recent or y in recent else ""
        print(f"  {ratio:.2f}{' same-name' if same else ''}{flag}  {x} ({nx} lines)  ~  {y} ({ny} lines)")
    if len(pairs) > 40:
        print(f"  ... {len(pairs) - 40} more")
    cases = git("log", since, "--format=%h %ad %s", "--date=short", "--", "docs/cases.md")
    print(f"Commits to docs/cases.md in {a.days} days: {len(cases)}")
    for c in cases:
        print("  " + c)
    return 0


if __name__ == "__main__":
    sys.exit(main())

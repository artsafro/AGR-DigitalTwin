"""Pipeline gate: a job's status cannot rise above draft without the harness's own files (HARNESS_PLAN §16).

    py -3 tools/git-hooks/pipeline_gate.py --staged          # pre-commit: the index
    py -3 tools/git-hooks/pipeline_gate.py --job jobs/<JOB>  # delivery: the working tree

Rules (user decisions 2026-10-11, case alina-bld):
- `jobs/<JOB>/STATE.md` carries one line `Pipeline status: <draft|built|checked|delivered>`. A STATE.md in
  a commit without it is blocked; an untouched old STATE.md is not checked until it changes.
- Above draft: `jobs/<JOB>/pipeline/spec.json` with its extractor report `spec.report.json` beside it
  (written by `dt spec extract`; a spec without it was not extracted) and a checker report
  `pipeline/check.json` (`passed`, `failed`, `not_measured`). `checked` and `delivered` also need no failed
  and no unmeasured check.
- A new job script (`jobs/<JOB>/scripts/*`) names the engine gap it fills in its first lines,
  `Engine gap: EG<n>`, and that gap is listed in `docs/backlog.md`; anything else is asked, not scripted.
- A commit on an auto-generated worktree branch (`claude/<words>-<hex6>`, tools/git-hooks/branch_names.py) is
  blocked until the branch is renamed by docs/agents/NAMING.md (user 2026-10-14).
- Delivery (--job) also needs a committed `.py` for every `.pyc` under `scripts/` (a lost source with a
  live `.pyc` must not happen again).
Exit 0 pass, 1 blocked (reasons on stderr), 2 wrong input.
Pattern: none — harness tooling (REVIEW_CHECKLIST Q1: new-case).
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from branch_names import RENAME_HINT, is_auto  # noqa: E402

LEVELS = ("draft", "built", "checked", "delivered")
# Every line that mentions the pipeline status, once Markdown marks are dropped, counts, however it is
# formatted (bold anywhere, heading, quote, list, BOM, case; reviews 1-2 of PR #73); it must read
# `pipeline status: <level>` and there must be exactly one.
MARKS = re.compile(r"[﻿*_`#>]")
MENTION = re.compile(r"pipeline\s*status", re.I)
STATUS = re.compile(r"^-?\s*pipeline\s+status\s*:\s*(\S+)\s*$", re.I)
GAP_LINE = re.compile(r"Engine gap:\s*(EG\d+)\b")
GAP_HEAD_LINES = 30
# every file under scripts/ is a script except data and bytecode (review 3 of PR #73: .bat, sources in __pycache__)
NOT_SCRIPT_SUFFIXES = {".pyc", ".pyo", ".json", ".yaml", ".yml", ".csv", ".txt", ".md", ".png", ".jpg", ".jpeg"}
JOB_PATH = re.compile(r"^jobs/([^/]+)/")


def status_of(text):
    """(status, error) of a STATE.md text; status None when no line mentions it."""
    lines = [MARKS.sub("", line).strip() for line in text.splitlines()]
    found = [line for line in lines if MENTION.search(line)]
    if not found:
        return None, None
    if len(found) > 1:
        return None, f"{len(found)} lines name the pipeline status; one 'Pipeline status: <level>' per STATE.md"
    m = STATUS.match(found[0])
    if not m or m.group(1).lower() not in LEVELS:
        return None, f"{found[0]!r} is not 'Pipeline status: <{'|'.join(LEVELS)}>'"
    return m.group(1).lower(), None


def _json(read, path, errors):
    raw = read(path)
    if raw is None:
        errors.append(f"{path} missing")
        return None
    try:
        doc = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except ValueError as exc:
        errors.append(f"{path} is not JSON ({exc})")
        return None
    if not isinstance(doc, dict):
        errors.append(f"{path} is not a JSON object")
        return None
    return doc


def job_errors(job, read, require_line):
    """Reasons the job's status is not backed by files. read(posix path) -> bytes/str or None."""
    base = f"jobs/{job}"
    state = read(f"{base}/STATE.md")
    if state is None:
        return []
    text = state.decode("utf-8", "replace") if isinstance(state, bytes) else state
    status, error = status_of(text)
    if error:
        return [f"{base}/STATE.md: {error}"]
    if status is None:
        return [f"{base}/STATE.md: no 'Pipeline status: <{'|'.join(LEVELS)}>' line"] if require_line else []
    if status == "draft":
        return []
    errors = []
    spec = _json(read, f"{base}/pipeline/spec.json", errors)
    report = _json(read, f"{base}/pipeline/spec.report.json", errors)
    check = _json(read, f"{base}/pipeline/check.json", errors)
    if spec is not None and not spec.get("id"):
        errors.append(f"{base}/pipeline/spec.json has no id; not a spec")
    if report is not None and not (isinstance(report.get("questions"), list) and "parts" in report):
        errors.append(f"{base}/pipeline/spec.report.json is no `dt spec extract` report (questions, parts)")
    if report is not None and report.get("stops"):   # --collect-stops: the extractor stopped (review 1 of #80)
        errors.append(f"{base}/pipeline/spec.report.json lists {len(report['stops'])} extractor stop(s); "
                      "a stopped run backs no status above draft")
    if check is not None:
        shape = isinstance(check.get("passed"), bool) and all(isinstance(check.get(k), list)
                                                               for k in ("failed", "not_measured"))
        if not shape:
            errors.append(f"{base}/pipeline/check.json is no checker report (passed, failed, not_measured)")
        elif status in ("checked", "delivered") and (check["failed"] or check["not_measured"] or not check["passed"]):
            errors.append(f"{base}: status {status} with failed {check['failed']} / not measured "
                          f"{check['not_measured']} in pipeline/check.json")
    return [f"{base}: status {status} needs {e}" if e.endswith("missing") else e for e in errors]


def script_errors(path, text, backlog):
    """A new job script must name a listed engine gap in its first lines."""
    head = "\n".join(text.splitlines()[:GAP_HEAD_LINES])
    gap = GAP_LINE.search(head)
    if not gap:
        return [f"{path}: a job script names the engine gap it fills in its first {GAP_HEAD_LINES} lines "
                "('Engine gap: EG<n>', docs/backlog.md); anything else is asked, not scripted"]
    if backlog is None:                              # no list, no gap (review 1 of PR #73)
        return [f"{path}: docs/backlog.md missing; {gap.group(1)} is not a listed engine gap"]
    if f"**{gap.group(1)}**" not in backlog:
        return [f"{path}: {gap.group(1)} is not an engine gap in docs/backlog.md"]
    return []


def is_job_script(path):
    p = PurePosixPath(path)
    return len(p.parts) >= 4 and p.parts[0].lower() == "jobs" and p.parts[2].lower() == "scripts" and \
        p.suffix.lower() not in NOT_SCRIPT_SUFFIXES


class GitError(RuntimeError):
    """git failed: the gate cannot see the commit and blocks it (fail closed, 2026-10-12)."""


def _git(root, *args):
    # core.longpaths: deep job paths under a long checkout pass MAX_PATH on Windows; --no-replace-objects: a
    # replace ref must not show the gate other content than the one committed (review 3 of #79)
    try:
        return subprocess.run(["git", "--no-replace-objects", "-c", "core.longpaths=true", *args], cwd=root,
                              capture_output=True, check=False)
    except OSError as exc:                           # git not found or not startable (review 1 of PR #79)
        raise GitError(f"git {' '.join(args)}: {exc}") from exc


def _git_ok(root, *args):
    result = _git(root, *args)
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result


def auto_branch_error(root):
    """A commit on an auto-generated worktree branch is blocked until it is renamed (user 2026-10-14)."""
    head = _git(root, "symbolic-ref", "--short", "-q", "HEAD")
    branch = head.stdout.decode("utf-8", "replace").strip() if head.returncode == 0 else ""   # detached: no branch
    if is_auto(branch):
        return (f"branch '{branch}' has an auto-generated worktree name; rename it by docs/agents/NAMING.md "
                f"({RENAME_HINT}) before the first commit: propose the name to the user, then git branch -m <name>")
    return None


def staged(root):
    """Errors of the commit being made, read from the index."""
    branch_error = auto_branch_error(root)
    if branch_error:
        return [branch_error]
    out = _git_ok(root, "diff", "--cached", "--name-status", "--no-renames", "-z").stdout.decode("utf-8").split("\0")
    changes = list(zip(out[0::2], out[1::2]))
    blobs, unmerged = {}, set()                      # path -> its blob in the index (stage 0)
    for entry in _git_ok(root, "ls-files", "-s", "-z").stdout.decode("utf-8").split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            _, blob, stage = meta.split()
            if stage == "0":
                blobs[path] = blob
            else:
                unmerged.add(path)
    if unmerged:                                     # an unresolved merge is no state to judge (review 1 of #79)
        return [f"{path}: unresolved merge in the index" for path in sorted(unmerged)]

    def read(path):                                  # None only when the index has no such path
        return _git_ok(root, "cat-file", "blob", blobs[path]).stdout if path in blobs else None

    backlog = read("docs/backlog.md")
    backlog = backlog.decode("utf-8", "replace") if backlog is not None else None
    errors, jobs, states = [], set(), set()
    for code, path in changes:
        if code != "D" and path.split("/")[0].lower() == "jobs" and not path.startswith("jobs/"):
            errors.append(f"{path}: the folder is jobs/ (a case variant would escape the check; review 2 of PR #73)")
            continue
        m = JOB_PATH.match(path)
        if not m:
            continue
        jobs.add(m.group(1))
        if path.lower() == f"jobs/{m.group(1)}/state.md".lower() and path != f"jobs/{m.group(1)}/STATE.md" \
                and code != "D":                     # a case variant would escape the check
            errors.append(f"{path}: name it STATE.md")
        if path == f"jobs/{m.group(1)}/STATE.md" and code != "D":
            states.add(m.group(1))
        if code == "A" and is_job_script(path):
            errors += script_errors(path, (read(path) or b"").decode("utf-8", "replace"), backlog)
    for job in sorted(jobs):
        errors += job_errors(job, read, require_line=job in states)
    return errors


def delivery(root, job_dir):
    """Errors of one job on the working tree, for hand-over."""
    job_dir = (root / job_dir).resolve()
    job = job_dir.name
    if job_dir != (root / "jobs" / job).resolve() or not job_dir.is_dir():   # review 1 of PR #73
        raise ValueError(f"{job_dir} is not a jobs/<JOB> folder of this repository")

    def read(path):
        p = root / path
        return p.read_bytes() if p.is_file() else None

    errors = job_errors(job, read, require_line=True)
    if read(f"jobs/{job}/STATE.md") is None:
        errors.append(f"jobs/{job}/STATE.md missing")
    # committed = in HEAD, not merely staged (review 1 of PR #73)
    tracked = set(_git_ok(root, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", f"jobs/{job}")
                  .stdout.decode("utf-8").split("\0"))
    for pyc in sorted((job_dir / "scripts").rglob("*.pyc")):
        if pyc.parent.name == "__pycache__":         # <name>.<tag>[.opt-N].pyc; the name may hold dots
            source = pyc.parent.parent / (re.sub(r"\.[^.]+(\.opt-\d+)?\.pyc$", "", pyc.name) + ".py")
        else:
            source = pyc.with_suffix(".py")
        rel = source.relative_to(root).as_posix()
        if rel not in tracked:
            errors.append(f"{pyc.relative_to(root).as_posix()}: its source {rel} is not committed")
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="check the index (pre-commit)")
    group.add_argument("--job", help="check one jobs/<JOB> folder on the working tree (delivery)")
    args = ap.parse_args(argv)
    try:
        top = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    except GitError as exc:
        print(f"pipeline_gate: {exc}", file=sys.stderr)
        return 2
    if top.returncode != 0:
        print("pipeline_gate: not inside a git repository", file=sys.stderr)
        return 2
    root = Path(top.stdout.decode("utf-8").strip())
    try:
        errors = staged(root) if args.staged else delivery(root, args.job)
    except (ValueError, GitError) as exc:
        print(f"pipeline_gate: {exc}", file=sys.stderr)
        print("pipeline_gate: blocked (docs/HARNESS_PLAN.md §16)", file=sys.stderr)
        return 2
    for e in errors:
        print(f"pipeline_gate: {e}", file=sys.stderr)
    if errors:
        print("pipeline_gate: blocked (docs/HARNESS_PLAN.md §16)", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

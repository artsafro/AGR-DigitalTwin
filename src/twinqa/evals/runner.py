"""Run eval tasks (`evals/<task>/task.json`) and write `report.json` into a new run folder (`dt evals`).

Exit codes as the benchmark runner (tools/qa/run_benchmark.py): 0 every check passes; 1 a grader fails (a failure
is a definite result, so it wins over a check left unmeasured elsewhere); 2 evidence missing, a task stopped, or the
input is wrong. Evidence rules and the layout: `evals/README.md`.
Pattern: none - harness tooling (REVIEW_CHECKLIST Q1: new-case).
"""
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from twinqa.evals.graders import GRADERS, EvidenceError

SUITES = ("regression", "capability")
VERDICTS = ("pass", "fail")


class EvalInputError(Exception):
    """Wrong input for the whole run (unknown task, existing run folder): exit 2 before anything is written."""


def _git(cwd, *args):
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", timeout=10)
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git_context(cwd):
    """(main checkout, current branch): the main checkout is the parent of the git common dir, as in
    tools/hooks/usage_log.py and save_transcript.py, so every worktree reads the same logs/."""
    common = _git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return (Path(common).parent if common else None), (_git(cwd, "branch", "--show-current") or None)


def branch_slug(branch):
    return re.sub(r"[^A-Za-z0-9._-]", "-", branch)        # the file-name rule of save_transcript.destination


def load_tasks(evals_dir, suite=None, task=None):
    evals_dir = Path(evals_dir)
    if task and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", task):
        raise EvalInputError(f"task id {task!r}: letters, digits, '.', '_' and '-' only")
    folders = [evals_dir / task] if task else sorted(p for p in evals_dir.iterdir() if p.is_dir()) \
        if evals_dir.is_dir() else []
    tasks = []
    for folder in folders:
        path = folder / "task.json"
        if not path.is_file():
            if task:
                raise EvalInputError(f"no task {task!r}: {path} does not exist")
            continue
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            spec = {"id": folder.name, "_error": f"task.json unreadable: {exc}"}
        if not isinstance(spec, dict):
            spec = {"id": folder.name, "_error": "task.json must be a JSON object"}
        if suite and spec.get("suite") != suite and "_error" not in spec:
            continue
        tasks.append((folder, spec))
    if not tasks:
        raise EvalInputError(f"no eval task selected in {evals_dir} (suite={suite}, task={task})")
    return tasks


def task_problem(folder, spec):
    if "_error" in spec:
        return spec["_error"]
    if spec.get("id") != folder.name:
        return f"id {spec.get('id')!r} differs from the folder name {folder.name!r}"
    if spec.get("suite") not in SUITES:
        return f"suite must be one of {SUITES}"
    if spec.get("grader") not in GRADERS:
        return f"unknown grader {spec.get('grader')!r}; known: {sorted(GRADERS)}"
    if not isinstance(spec.get("evidence"), dict) or not spec["evidence"]:
        return "evidence must name at least one rule"
    for ref in spec.get("references", []):
        if not isinstance(ref, dict) or ref.get("verdict") not in VERDICTS or not isinstance(ref.get("evidence"), dict):
            return f"every reference needs a name, an evidence object and a verdict in {VERDICTS}"
    return None


def resolve(rule, folder, main, branch):
    """One evidence rule -> the existing files it names (sorted). Raises EvidenceError when none exists."""
    if not isinstance(rule, dict) or ("path" in rule) == ("glob" in rule):
        raise EvidenceError(f"rule {rule!r} needs exactly one of path / glob")
    root_name = rule.get("root", "main")
    root = {"main": main, "task": folder}.get(root_name, "?")
    if root == "?":
        raise EvidenceError(f"rule root {root_name!r} must be main or task")
    if root is None:
        raise EvidenceError("the main checkout is unknown (git failed); pass --main")
    pattern = rule.get("path") or rule.get("glob")
    if "{branch" in pattern:
        if not branch:
            raise EvidenceError(f"{pattern} needs the branch (detached HEAD or git failed); pass --branch")
        pattern = pattern.replace("{branch_slug}", branch_slug(branch)).replace("{branch}", branch)
    if "path" in rule:
        files = [root / pattern] if (root / pattern).is_file() else []
    else:
        files = sorted(p for p in root.glob(pattern) if p.is_file())
    if not files:
        raise EvidenceError(f"no evidence: {root / pattern}")
    return files


def _not_measured(task_id, check, expected, message, evidence=()):
    return {"task": task_id, "check": check, "expected": expected, "measured": "not measured", "passed": None,
            "evidence": [str(p) for p in evidence], "error": message}


def grade(task_id, spec, rules, folder, main, branch, overrides):
    """Resolve every evidence rule (an override path wins) and run the task's grader -> one check row."""
    evidence = {}
    try:
        for name, rule in rules.items():
            if name in overrides:
                path = Path(overrides[name]).resolve()
                if not path.is_file():
                    raise EvidenceError(f"no evidence: {path} (--evidence {name}=...)")
                evidence[name] = [path]
            else:
                evidence[name] = resolve(rule, folder, main, branch)
        row = GRADERS[spec["grader"]](evidence)
    except EvidenceError as exc:
        return _not_measured(task_id, spec["grader"], None, str(exc),
                             [p for paths in evidence.values() for p in paths])
    return {"task": task_id, **row, "evidence": [str(p) for paths in evidence.values() for p in paths]}


def run_task(folder, spec, main, branch, overrides, references):
    task_id = spec.get("id", folder.name)
    problem = task_problem(folder, spec)
    if problem:
        return [_not_measured(task_id, "task.json", "valid", f"stopped: {problem}")]
    if not references:
        return [grade(task_id, spec, spec["evidence"], folder, main, branch, overrides)]
    rows = []
    if not spec.get("references"):
        return [_not_measured(task_id, spec["grader"], "a reference verdict", "task.json has no references")]
    for ref in spec["references"]:        # the grader against its known answers: expected = the reference verdict
        row = grade(task_id, spec, ref["evidence"], folder, main, branch, {})
        name = f"{row['check']} [reference {ref.get('name', '?')}]"
        if row["passed"] is None:
            rows.append({**row, "check": name, "expected": ref["verdict"]})
            continue
        verdict = "pass" if row["passed"] else "fail"
        rows.append({**row, "check": name, "expected": ref["verdict"], "measured": f"{verdict} ({row['measured']})",
                     "passed": verdict == ref["verdict"]})
    return rows


def exit_code(rows):
    if any(r["passed"] is False for r in rows):
        return 1
    return 2 if any(r["passed"] is None for r in rows) else 0


def run(evals_dir, *, suite=None, task=None, references=False, overrides=None, main=None, branch=None,
        output=None, cwd=None):
    """Run the selected tasks; returns (exit code, report, run folder). Raises EvalInputError on a wrong input."""
    if bool(suite) == bool(task):
        raise EvalInputError("give exactly one of --suite or --task")
    if suite and suite not in SUITES:
        raise EvalInputError(f"--suite must be one of {SUITES}")
    overrides = overrides or {}
    if overrides and not task:
        raise EvalInputError("--evidence overrides need --task (one task, one set of evidence)")
    if overrides and references:
        raise EvalInputError("--references grades the evidence of task.json; drop --evidence")
    git_main, git_branch = git_context(cwd or Path.cwd())
    main = Path(main).resolve() if main else git_main
    branch = branch or git_branch
    tasks = load_tasks(evals_dir, suite, task)
    if output is None:
        if main is None:
            raise EvalInputError("the main checkout is unknown (git failed); pass --main or --output")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = main / "logs" / "evals" / "runs" / f"{stamp}-{suite or task}{'-references' if references else ''}"
    output = Path(output)
    if output.exists():
        raise EvalInputError(f"{output} exists; use a new run folder")
    rows = [r for folder, spec in tasks for r in run_task(folder, spec, main, branch, overrides, references)]
    code = exit_code(rows)
    report = {
        "selector": {"suite": suite, "task": task, "references": references},
        "evidence_overrides": {k: str(Path(v).resolve()) for k, v in overrides.items()},
        "main_checkout": str(main) if main else None, "branch": branch,
        "created": datetime.now().isoformat(timespec="seconds"),
        "passed": sum(r["passed"] is True for r in rows), "failed": sum(r["passed"] is False for r in rows),
        "not_measured": sum(r["passed"] is None for r in rows),
        "exit_code": code, "checks": rows,
    }
    output.mkdir(parents=True)
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return code, report, output


def table(report):
    lines = ["task | check | expected | measured | result"]
    for r in report["checks"]:
        result = {True: "PASS", False: "FAIL", None: "NOT MEASURED"}[r["passed"]]
        lines.append(f"{r['task']} | {r['check']} | {r['expected']} | {r['measured']} | {result}")
        if r.get("error"):
            lines.append(f"  - {r['error']}")
    return "\n".join(lines)

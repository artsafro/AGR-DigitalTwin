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
from pathlib import Path, PurePosixPath, PureWindowsPath

from twinqa.evals.graders import GRADERS, EvidenceError

SUITES = ("regression", "capability")
VERDICTS = ("pass", "fail")
ROOTS = ("main", "task")
RULE_KEYS = {"root", "path", "glob", "match"}


class EvalInputError(Exception):
    """Wrong input for the whole run (unknown task, existing run folder): exit 2 before anything is written."""


class TaskError(Exception):
    """A task.json that does not follow the schema: the task is a stopped row, exit 2."""


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


def _check_rule(rule, where):
    """An evidence rule: {"root": main|task, "path"|"glob": relative pattern, "match": optional file-name regex}."""
    if not isinstance(rule, dict):
        raise TaskError(f"{where}: a rule must be an object, got {type(rule).__name__}")
    if set(rule) - RULE_KEYS:
        raise TaskError(f"{where}: unknown keys {sorted(set(rule) - RULE_KEYS)}")
    if ("path" in rule) == ("glob" in rule):
        raise TaskError(f"{where}: needs exactly one of path / glob")
    if rule.get("root", "main") not in ROOTS:
        raise TaskError(f"{where}: root must be one of {ROOTS}")
    pattern = rule.get("path", rule.get("glob"))
    if not isinstance(pattern, str) or not pattern:
        raise TaskError(f"{where}: path / glob must be a non-empty string")
    for flavour in (PurePosixPath, PureWindowsPath):  # confined to the root on every platform
        p = flavour(pattern)
        if p.is_absolute() or p.drive or p.root or ".." in p.parts:
            raise TaskError(f"{where}: {pattern!r} must stay inside its root (relative, no '..')")
    if "match" in rule:
        if not isinstance(rule["match"], str):
            raise TaskError(f"{where}: match must be a string")
        try:
            re.compile(_fill(rule["match"], "branch", regex=True))
        except re.error as exc:
            raise TaskError(f"{where}: match is not a regular expression: {exc}") from exc


def _check_evidence(evidence, names, where):
    if not isinstance(evidence, dict):
        raise TaskError(f"{where} must be an object of rules")
    if set(evidence) != set(names):
        raise TaskError(f"{where} must name exactly {sorted(names)} (the grader's evidence), got {sorted(evidence)}")
    for name, rule in evidence.items():
        _check_rule(rule, f"{where}.{name}")


def validate(folder, spec):
    """The whole task.json schema, before anything runs (review 1 of #142). Raises TaskError."""
    if not isinstance(spec, dict):
        raise TaskError("task.json must be a JSON object")
    if spec.get("id") != folder.name:
        raise TaskError(f"id {spec.get('id')!r} differs from the folder name {folder.name!r}")
    if not isinstance(spec.get("suite"), str) or spec["suite"] not in SUITES:
        raise TaskError(f"suite must be one of {SUITES}, got {spec.get('suite')!r}")
    if not isinstance(spec.get("grader"), str) or spec["grader"] not in GRADERS:
        raise TaskError(f"unknown grader {spec.get('grader')!r}; known: {sorted(GRADERS)}")
    names = GRADERS[spec["grader"]][1]
    _check_evidence(spec.get("evidence"), names, "evidence")
    refs = spec.get("references", [])
    if not isinstance(refs, list):
        raise TaskError("references must be a list")
    for i, ref in enumerate(refs):
        if not isinstance(ref, dict) or not isinstance(ref.get("name"), str) or ref.get("verdict") not in VERDICTS:
            raise TaskError(f"references[{i}] needs a name and a verdict in {VERDICTS}")
        _check_evidence(ref.get("evidence"), names, f"references[{i}].evidence")


def load_tasks(evals_dir, suite=None, task=None):
    """Every selected task as (folder, spec, problem). Every task.json is validated before the suite filter: an
    invalid task cannot drop out of a suite unseen, it stays as a stopped row."""
    evals_dir = Path(evals_dir)
    if task and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", task):
        raise EvalInputError(f"task id {task!r}: letters, digits, '.', '_' and '-' only")
    if task:
        folders = [evals_dir / task]
    else:
        folders = sorted(p for p in evals_dir.iterdir() if p.is_dir()) if evals_dir.is_dir() else []
    tasks = []
    for folder in folders:
        path = folder / "task.json"
        if not path.is_file():
            if task:
                raise EvalInputError(f"no task {task!r}: {path} does not exist")
            continue
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
            validate(folder, spec)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            tasks.append((folder, None, f"task.json unreadable: {exc}"))
            continue
        except TaskError as exc:
            tasks.append((folder, spec, str(exc)))
            continue
        if suite and spec["suite"] != suite:
            continue
        tasks.append((folder, spec, None))
    if not tasks:
        raise EvalInputError(f"no eval task selected in {evals_dir} (suite={suite}, task={task})")
    return tasks


def _fill(text, branch, regex=False):
    values = {"{branch_slug}": branch_slug(branch), "{branch}": branch}
    for key, value in values.items():
        text = text.replace(key, re.escape(value) if regex else value)
    return text


def resolve(rule, folder, main, branch):
    """One evidence rule -> the existing files it names (sorted), all inside the rule's root.
    Raises EvidenceError when none exists."""
    root = {"main": main, "task": folder}[rule.get("root", "main")]
    if root is None:
        raise EvidenceError("the main checkout is unknown (git failed); pass --main")
    pattern = rule.get("path", rule.get("glob"))
    if "{branch" in pattern + rule.get("match", ""):
        if not branch:
            raise EvidenceError(f"{pattern} needs the branch (detached HEAD or git failed); pass --branch")
        pattern = _fill(pattern, branch)
    if "path" in rule:
        files = [root / pattern] if (root / pattern).is_file() else []
    else:
        files = sorted(p for p in root.glob(pattern) if p.is_file())
    if "match" in rule:
        name = re.compile(_fill(rule["match"], branch, regex=True))
        files = [p for p in files if name.fullmatch(p.name)]
    base = root.resolve()
    outside = [p for p in files if not p.resolve().is_relative_to(base)]   # a link out of the root
    if outside:
        raise EvidenceError(f"evidence outside its root {base}: {[str(p) for p in outside]}")
    if not files:
        raise EvidenceError(f"no evidence: {root / pattern}" + (f" matching {rule['match']}" if "match" in rule else ""))
    return files


def _not_measured(task_id, check, expected, message, evidence=()):
    return {"task": task_id, "check": check, "expected": expected, "measured": "not measured", "passed": None,
            "evidence": [str(p) for p in evidence], "error": message}


def grade(task_id, spec, rules, folder, main, branch, overrides):
    """Resolve every evidence rule (an override path wins) and run the task's grader -> one check row."""
    grader = GRADERS[spec["grader"]][0]
    evidence = {}
    used = lambda: [p for paths in evidence.values() for p in paths]  # noqa: E731
    try:
        for name, rule in rules.items():
            if name in overrides:          # explicit user input: any path, no root confinement
                path = Path(overrides[name]).resolve()
                if not path.is_file():
                    raise EvidenceError(f"no evidence: {path} (--evidence {name}=...)")
                evidence[name] = [path]
            else:
                evidence[name] = resolve(rule, folder, main, branch)
        row = grader(evidence)
    except EvidenceError as exc:
        return _not_measured(task_id, spec["grader"], None, str(exc), used())
    except Exception as exc:  # noqa: BLE001 - a grader that breaks stops its task, never the run
        return _not_measured(task_id, spec["grader"], None, f"stopped: {type(exc).__name__}: {exc}", used())
    return {"task": task_id, **row, "evidence": [str(p) for p in used()]}


def run_task(folder, spec, problem, main, branch, overrides, references):
    if problem:
        return [_not_measured(folder.name, "task.json", "valid", f"stopped: {problem}")]
    task_id = spec["id"]
    if not references:
        return [grade(task_id, spec, spec["evidence"], folder, main, branch, overrides)]
    if not spec.get("references"):
        return [_not_measured(task_id, spec["grader"], "a reference verdict", "task.json has no references")]
    rows = []
    for ref in spec["references"]:        # the grader against its known answers: expected = the reference verdict
        row = grade(task_id, spec, ref["evidence"], folder, main, branch, {})
        name = f"{row['check']} [reference {ref['name']}]"
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
    for _, spec, problem in tasks:
        unknown = set(overrides) - set(GRADERS[spec["grader"]][1]) if not problem else set()
        if unknown:
            raise EvalInputError(f"--evidence {sorted(unknown)}: the grader reads {list(GRADERS[spec['grader']][1])}")
    if output is None:
        if main is None:
            raise EvalInputError("the main checkout is unknown (git failed); pass --main or --output")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = main / "logs" / "evals" / "runs" / f"{stamp}-{suite or task}{'-references' if references else ''}"
    output = Path(output)
    if output.exists():
        raise EvalInputError(f"{output} exists; use a new run folder")
    rows = [r for folder, spec, problem in tasks
            for r in run_task(folder, spec, problem, main, branch, overrides, references)]
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

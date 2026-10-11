"""pipeline_gate: a job status above draft needs spec + extractor report + checker report (HARNESS_PLAN §16)."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("pipeline_gate", ROOT / "tools/git-hooks/pipeline_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)
HOOK = ROOT / ".claude/hooks/pipeline_gate.py"

SPEC = json.dumps({"id": "obj", "levels": []})
REPORT = json.dumps({"parts": 3, "questions": []})
CHECK_PASS = json.dumps({"passed": True, "failed": [], "not_measured": [], "checks": []})
CHECK_FAIL = json.dumps({"passed": False, "failed": ["bbox"], "not_measured": [], "checks": []})
BACKLOG = "# Backlog\n\n- **EG1** Facade decor.\n"


def state(status):
    return f"# State\n\nPipeline status: {status}\n"


def reader(files):
    return lambda path: files.get(path)


def job(files, status, **pipeline):
    files = dict(files)
    files["jobs/J/STATE.md"] = state(status)
    for name, text in pipeline.items():
        files[f"jobs/J/pipeline/{name.replace('_', '.')}"] = text
    return files


@pytest.mark.parametrize("text, expected", [
    ("Pipeline status: built\n", ("built", None)),
    ("Pipeline status: `checked`\n", ("checked", None)),
    ("Pipeline status: **draft**\n", ("draft", None)),
    ("no status here\n", (None, None)),
])
def test_status_line(text, expected):
    assert gate.status_of(text) == expected


def test_status_line_rejects_unknown_and_twice():
    assert "none of" in gate.status_of("Pipeline status: accepted\n")[1]
    assert "one per" in gate.status_of("Pipeline status: draft\nPipeline status: built\n")[1]


def test_draft_needs_nothing():
    assert gate.job_errors("J", reader(job({}, "draft")), require_line=True) == []


def test_built_without_spec_is_blocked():
    errors = gate.job_errors("J", reader(job({}, "built")), require_line=True)
    assert any("spec.json missing" in e for e in errors)
    assert any("spec.report.json missing" in e for e in errors)
    assert any("check.json missing" in e for e in errors)


def test_hand_written_spec_without_extractor_report_is_blocked():
    files = job({}, "built", spec_json=SPEC, check_json=CHECK_PASS,
                spec_report_json=json.dumps({"note": "written by hand"}))
    assert any("no `dt spec extract` report" in e for e in gate.job_errors("J", reader(files), True))


def test_built_with_all_files_passes_even_when_checks_fail():
    files = job({}, "built", spec_json=SPEC, spec_report_json=REPORT, check_json=CHECK_FAIL)
    assert gate.job_errors("J", reader(files), True) == []


def test_checked_needs_a_passing_report():
    files = job({}, "checked", spec_json=SPEC, spec_report_json=REPORT, check_json=CHECK_FAIL)
    assert any("failed ['bbox']" in e for e in gate.job_errors("J", reader(files), True))
    files = job({}, "delivered", spec_json=SPEC, spec_report_json=REPORT,
                check_json=json.dumps({"passed": False, "failed": [], "not_measured": ["uv"]}))
    assert any("not measured ['uv']" in e for e in gate.job_errors("J", reader(files), True))
    files = job({}, "delivered", spec_json=SPEC, spec_report_json=REPORT, check_json=CHECK_PASS)
    assert gate.job_errors("J", reader(files), True) == []


def test_check_report_shape():
    files = job({}, "built", spec_json=SPEC, spec_report_json=REPORT, check_json=json.dumps({"ok": True}))
    assert any("no checker report" in e for e in gate.job_errors("J", reader(files), True))


def test_missing_line_only_when_required():
    files = {"jobs/J/STATE.md": "# State\nStatus: accepted by the user\n"}
    assert gate.job_errors("J", reader(files), require_line=False) == []
    assert "no 'Pipeline status" in gate.job_errors("J", reader(files), require_line=True)[0]


def test_script_must_name_a_listed_gap():
    assert "names the engine gap" in gate.script_errors("jobs/J/scripts/a.py", "print(1)\n", BACKLOG)[0]
    assert "not an engine gap" in gate.script_errors("jobs/J/scripts/a.py", '"""Engine gap: EG9"""\n', BACKLOG)[0]
    assert gate.script_errors("jobs/J/scripts/a.py", '"""Decor.\n\nEngine gap: EG1\n"""\n', BACKLOG) == []
    late = "\n" * gate.GAP_HEAD_LINES + "# Engine gap: EG1\n"
    assert gate.script_errors("jobs/J/scripts/a.py", late, BACKLOG)


def test_is_job_script():
    assert gate.is_job_script("jobs/J/scripts/build.py")
    assert gate.is_job_script("jobs/J/scripts/sub/run.sh")
    assert not gate.is_job_script("jobs/J/scripts/__pycache__/build.cpython-313.pyc")
    assert not gate.is_job_script("jobs/J/scripts/data.json")
    assert not gate.is_job_script("jobs/J/STATE.md")


# --- git: pre-commit (--staged) and delivery (--job) ---------------------------------------------------

def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/backlog.md").write_text(BACKLOG, encoding="utf-8")
    (tmp_path / "jobs/OLD").mkdir(parents=True)
    (tmp_path / "jobs/OLD/STATE.md").write_text("Status: accepted (before the gate)\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def write(repo, rel, text):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    git(repo, "add", rel)


def test_staged_built_without_files_is_blocked(repo):
    write(repo, "jobs/J/STATE.md", state("built"))
    assert any("spec.json missing" in e for e in gate.staged(repo))


def test_staged_built_with_files_passes(repo):
    write(repo, "jobs/J/STATE.md", state("built"))
    write(repo, "jobs/J/pipeline/spec.json", SPEC)
    write(repo, "jobs/J/pipeline/spec.report.json", REPORT)
    write(repo, "jobs/J/pipeline/check.json", CHECK_PASS)
    assert gate.staged(repo) == []


def test_staged_reads_the_index_not_the_working_tree(repo):
    write(repo, "jobs/J/STATE.md", state("built"))
    for name, text in (("spec.json", SPEC), ("spec.report.json", REPORT), ("check.json", CHECK_PASS)):
        (repo / "jobs/J/pipeline").mkdir(parents=True, exist_ok=True)
        (repo / "jobs/J/pipeline" / name).write_text(text, encoding="utf-8")     # on disk, not staged
    assert any("spec.json missing" in e for e in gate.staged(repo))


def test_staged_deleting_the_report_under_a_built_status_is_blocked(repo):
    write(repo, "jobs/J/STATE.md", state("built"))
    write(repo, "jobs/J/pipeline/spec.json", SPEC)
    write(repo, "jobs/J/pipeline/spec.report.json", REPORT)
    write(repo, "jobs/J/pipeline/check.json", CHECK_PASS)
    git(repo, "commit", "-qm", "built")
    git(repo, "rm", "-q", "jobs/J/pipeline/check.json")
    assert any("check.json missing" in e for e in gate.staged(repo))


def test_staged_old_state_untouched_passes_touched_needs_the_line(repo):
    write(repo, "jobs/OLD/notes.md", "x\n")
    assert gate.staged(repo) == []
    write(repo, "jobs/OLD/STATE.md", "Status: accepted, edited\n")
    assert any("no 'Pipeline status" in e for e in gate.staged(repo))


def test_staged_new_script_needs_a_gap(repo):
    write(repo, "jobs/J/scripts/build_decor.py", "import bpy\n")
    assert any("names the engine gap" in e for e in gate.staged(repo))
    write(repo, "jobs/J/scripts/build_decor.py", '"""Build decor.\n\nEngine gap: EG1\n"""\nimport bpy\n')
    assert gate.staged(repo) == []


def test_delivery_pyc_without_committed_source(repo):
    write(repo, "jobs/J/STATE.md", state("draft"))
    git(repo, "commit", "-qm", "j")
    pyc = repo / "jobs/J/scripts/__pycache__/build_decor.cpython-313.pyc"
    pyc.parent.mkdir(parents=True)
    pyc.write_bytes(b"\0")
    errors = gate.delivery(repo, "jobs/J")
    assert any("jobs/J/scripts/build_decor.py is not committed" in e for e in errors)
    write(repo, "jobs/J/scripts/build_decor.py", '"""Engine gap: EG1"""\n')
    git(repo, "commit", "-qm", "source")
    assert gate.delivery(repo, "jobs/J") == []


def test_delivery_requires_the_line(repo):
    assert any("no 'Pipeline status" in e for e in gate.delivery(repo, "jobs/OLD"))


def test_cli_exit_codes(repo):
    run = lambda *a: subprocess.run([sys.executable, str(ROOT / "tools/git-hooks/pipeline_gate.py"), *a],
                                    cwd=repo, capture_output=True, text=True)
    assert run("--staged").returncode == 0
    write(repo, "jobs/J/STATE.md", state("checked"))
    result = run("--staged")
    assert result.returncode == 1 and "blocked" in result.stderr
    assert run("--job", "nowhere").returncode == 2


# --- Claude Code PreToolUse hook ------------------------------------------------------------------------

def hook(payload):
    result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] if result.stdout.strip() else "allow"


def test_hook_denies_a_status_without_files(tmp_path):
    target = tmp_path / "jobs/J/STATE.md"
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": state("built")}}
    assert hook(payload) == "deny"
    payload["tool_input"]["content"] = state("draft")
    assert hook(payload) == "allow"


def test_hook_edit_applies_the_change(tmp_path):
    target = tmp_path / "jobs/J/STATE.md"
    target.parent.mkdir(parents=True)
    target.write_text(state("draft"), encoding="utf-8")
    edit = {"tool_name": "Edit", "tool_input": {"file_path": str(target), "old_string": "draft",
                                                "new_string": "delivered"}}
    assert hook(edit) == "deny"
    for name, text in (("spec.json", SPEC), ("spec.report.json", REPORT), ("check.json", CHECK_PASS)):
        (tmp_path / "jobs/J/pipeline").mkdir(exist_ok=True)
        (tmp_path / "jobs/J/pipeline" / name).write_text(text, encoding="utf-8")
    assert hook(edit) == "allow"


def test_hook_new_script_needs_a_gap(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/backlog.md").write_text(BACKLOG, encoding="utf-8")
    target = tmp_path / "jobs/J/scripts/build_decor.py"
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": "import bpy\n"}}
    assert hook(payload) == "deny"
    payload["tool_input"]["content"] = '"""Engine gap: EG1"""\nimport bpy\n'
    assert hook(payload) == "allow"


def test_hook_ignores_other_files(tmp_path):
    assert hook({"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "src/a.py"), "content": ""}}) == "allow"
    assert hook({"tool_name": "Bash", "tool_input": {"command": "ls"}}) == "allow"


# --- review 1 of PR #73 ------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Pipeline status: draft\n**Pipeline status: built**\n",
    "Pipeline status: draft\npipeline STATUS: built\n",
    "Pipeline status: draft\n> - Pipeline status: built\n",
])
def test_a_second_formatted_status_line_counts(text):
    assert "one per" in gate.status_of(text)[1]


@pytest.mark.parametrize("text", ["**Pipeline status: built**\n", "\ufeffPipeline status: built\n",
                                  "**Pipeline status:** built\n", "Pipeline status: Built\r\n"])
def test_formatted_single_status_is_read(text):
    assert gate.status_of(text) == ("built", None)


def test_missing_backlog_lists_no_gap():
    assert "backlog.md missing" in gate.script_errors("jobs/J/scripts/a.py", '"""Engine gap: EG999"""\n', None)[0]


def test_staged_backlog_deleted_unknown_gap_blocked(repo):
    git(repo, "rm", "-q", "docs/backlog.md")
    write(repo, "jobs/J/scripts/a.py", '"""Engine gap: EG999"""\n')
    assert any("backlog.md missing" in e for e in gate.staged(repo))


def test_staged_case_variant_of_state_is_blocked(repo):
    write(repo, "jobs/J/state.md", state("built"))
    assert any("name it STATE.md" in e for e in gate.staged(repo))


def test_delivery_staged_source_is_not_committed(repo):
    write(repo, "jobs/J/STATE.md", state("draft"))
    git(repo, "commit", "-qm", "j")
    pyc = repo / "jobs/J/scripts/__pycache__/build.cpython-313.pyc"
    pyc.parent.mkdir(parents=True)
    pyc.write_bytes(b"\0")
    write(repo, "jobs/J/scripts/build.py", '"""Engine gap: EG1"""\n')      # staged only
    assert any("build.py is not committed" in e for e in gate.delivery(repo, "jobs/J"))


def test_delivery_dotted_cache_name(repo):
    write(repo, "jobs/J/STATE.md", state("draft"))
    write(repo, "jobs/J/scripts/build.decor.py", '"""Engine gap: EG1"""\n')
    git(repo, "commit", "-qm", "j")
    pyc = repo / "jobs/J/scripts/__pycache__/build.decor.cpython-313.pyc"
    pyc.parent.mkdir(parents=True)
    pyc.write_bytes(b"\0")
    assert gate.delivery(repo, "jobs/J") == []


def test_delivery_rejects_a_non_canonical_job_path(repo):
    (repo / "nested/jobs/J").mkdir(parents=True)
    with pytest.raises(ValueError):
        gate.delivery(repo, "nested/jobs/J")


def test_pre_commit_gate_sees_the_index_after_linking(repo):
    import shutil
    hooks = repo / ".git/hooks"
    shutil.copy(ROOT / "tools/git-hooks/pre-commit", hooks / "pre-commit")
    (repo / "tools/git-hooks").mkdir(parents=True)
    for name in ("pipeline_gate.py", "link_large_files.py"):
        shutil.copy(ROOT / "tools/git-hooks" / name, repo / "tools/git-hooks" / name)
    git(repo, "add", "tools")
    git(repo, "commit", "-qm", "hooks", "--no-verify")
    git(repo, "config", "twin.linkLargeMb", "0.001")
    write(repo, "jobs/J/STATE.md", state("built"))
    write(repo, "jobs/J/pipeline/spec.json", json.dumps({"id": "obj", "pad": "x" * 4000}))
    write(repo, "jobs/J/pipeline/spec.report.json", REPORT)
    write(repo, "jobs/J/pipeline/check.json", CHECK_PASS)
    result = subprocess.run(["git", "commit", "-qm", "built"], cwd=repo, capture_output=True, text=True)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "spec.json missing" in result.stderr


def test_hook_state_name_case_blind(tmp_path):
    target = tmp_path / "jobs/J/state.md"
    assert hook({"tool_name": "Write", "tool_input": {"file_path": str(target), "content": state("built")}}) == "deny"


@pytest.mark.parametrize("raw", ["[]", "null", '"x"', '{"tool_name": "Write", "tool_input": "x"}',
                                 '{"tool_name": "Write", "tool_input": {"file_path": 5}}'])
def test_hook_malformed_payload_passes(raw):
    result = subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True, text=True)
    assert result.returncode == 0 and not result.stdout.strip(), result.stderr


def test_delivery_optimized_cache_name(repo):
    write(repo, "jobs/J/STATE.md", state("draft"))
    write(repo, "jobs/J/scripts/build.decor.py", '"""Engine gap: EG1"""\n')
    git(repo, "commit", "-qm", "j")
    pyc = repo / "jobs/J/scripts/__pycache__/build.decor.cpython-313.opt-1.pyc"
    pyc.parent.mkdir(parents=True)
    pyc.write_bytes(b"\0")
    assert gate.delivery(repo, "jobs/J") == []
    (pyc.parent / "other.cpython-313.opt-2.pyc").write_bytes(b"\0")
    assert any("other.py is not committed" in e for e in gate.delivery(repo, "jobs/J"))

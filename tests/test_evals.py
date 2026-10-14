"""`dt evals` and its first grader, no hook denial (#122): verdicts from evidence files, exit codes 0 / 1 / 2."""
import json
import shutil
from pathlib import Path

import pytest

from dt_ai.cli.main import main
from twinqa.evals.graders import EvidenceError, hook_denials, no_hook_denial, read_jsonl

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "evals/no-hook-denial"
DENIED = TASK / "fixtures/denied.synthetic.jsonl"
CLEAN = TASK / "fixtures/clean.synthetic.jsonl"
S1, S2, S3 = ("1b4e28ba-2fa1-11d2-883f-0016d3cca42" + c for c in "789")      # session ids are UUIDs
TORN = '{"type": "user", "message": {"role": "user", "content": [{"type": "tool_res'


def dt(tmp_path, *args):
    out = tmp_path / "run"
    code = main(["evals", *args, "--main", str(tmp_path / "main"), "--branch", "harness/task-x",
                 "--output", str(out)])
    report = json.loads((out / "report.json").read_text(encoding="utf-8")) if (out / "report.json").is_file() else None
    return code, report


def test_grader_fails_on_the_denied_fixture():
    row = no_hook_denial({"transcript": [DENIED]})
    assert (row["expected"], row["measured"], row["passed"]) == (0, 1, False)
    assert row["details"][0]["tool"] == "Bash" and row["details"][0]["tool_use_id"] == "toolu_synthetic_01"


def test_grader_passes_on_the_clean_fixture_with_look_alikes():
    row = no_hook_denial({"transcript": [CLEAN]})
    assert (row["measured"], row["passed"]) == (0, True)


def test_older_record_without_permission_decision_is_read_from_the_tool_result():
    records = [{"type": "user", "message": {"content": [{"type": "tool_result", "is_error": True, "tool_use_id": "t1",
                "content": [{"type": "text", "text": "PreToolUse:mcp__blender__x hook error: load the skill"}]}]}}]
    assert [(d["tool"], d["reason"]) for d in hook_denials(records)] == [("mcp__blender__x", "load the skill")]


def test_hook_error_text_in_a_successful_result_or_assistant_text_is_not_a_denial():
    quoted = "PreToolUse:Bash hook error: quoted in a file"
    records = [{"type": "user", "message": {"content": [{"type": "tool_result", "content": quoted, "tool_use_id": "t"}]}},
               {"type": "assistant", "message": {"content": [{"type": "text", "text": quoted}]}}]
    assert hook_denials(records) == []


def test_empty_or_missing_transcript_is_not_evidence(tmp_path):
    (tmp_path / "empty.jsonl").write_text("\n", encoding="utf-8")
    assert no_hook_denial({"transcript": [tmp_path / "empty.jsonl"]})["passed"] is None
    with pytest.raises(EvidenceError):
        read_jsonl(tmp_path / "absent.jsonl")


def test_runner_exit_1_on_the_denied_transcript(tmp_path):
    code, report = dt(tmp_path, "--task", "no-hook-denial", "--evidence", f"transcript={DENIED}")
    assert code == 1
    (row,) = report["checks"]
    assert (row["task"], row["expected"], row["measured"], row["passed"]) == ("no-hook-denial", 0, 1, False)
    assert row["evidence"] == [str(DENIED.resolve())]


def test_runner_exit_0_on_the_clean_transcript(tmp_path):
    code, report = dt(tmp_path, "--task", "no-hook-denial", "--evidence", f"transcript={CLEAN}")
    assert code == 0 and report["checks"][0]["passed"] is True


def test_runner_exit_2_when_the_evidence_is_missing(tmp_path):
    code, report = dt(tmp_path, "--suite", "regression")       # no logs/transcripts in the main checkout
    assert code == 2
    assert report["checks"][0]["measured"] == "not measured" and "no evidence" in report["checks"][0]["error"]
    code, _ = dt(tmp_path / "b", "--task", "no-hook-denial", "--evidence", f"transcript={tmp_path / 'absent.jsonl'}")
    assert code == 2


def test_runner_reads_every_transcript_of_the_branch_from_the_main_checkout(tmp_path):
    folder = tmp_path / "main/logs/transcripts"
    folder.mkdir(parents=True)
    shutil.copy(CLEAN, folder / f"harness-task-x-pr7-{S1}.jsonl")
    shutil.copy(DENIED, folder / f"harness-task-x-prnone-{S2}.jsonl")
    shutil.copy(DENIED, folder / f"harness-task-x-other-pr7-{S3}.jsonl")        # another branch: not read
    code, report = dt(tmp_path, "--suite", "regression")
    assert code == 1
    assert [Path(p).name for p in report["checks"][0]["evidence"]] == [f"harness-task-x-pr7-{S1}.jsonl",
                                                                       f"harness-task-x-prnone-{S2}.jsonl"]


def test_references_match_their_verdicts(tmp_path):
    code, report = dt(tmp_path, "--task", "no-hook-denial", "--references")
    assert code == 0
    assert [(r["expected"], r["measured"]) for r in report["checks"]] == [("fail", "fail (1)"), ("pass", "pass (0)")]


def test_wrong_input_exit_2_and_an_existing_run_folder_is_never_overwritten(tmp_path):
    assert main(["evals", "--task", "no-such-task", "--output", str(tmp_path / "r1")]) == 2
    (tmp_path / "r2").mkdir()
    assert main(["evals", "--task", "no-hook-denial", "--evidence", f"transcript={CLEAN}",
                 "--output", str(tmp_path / "r2")]) == 2
    assert not (tmp_path / "r2/report.json").exists()


def test_a_broken_task_json_stops_the_task(tmp_path):
    evals = tmp_path / "evals"
    (evals / "bad").mkdir(parents=True)
    (evals / "bad/task.json").write_text('{"id": "bad", "suite": "regression", "grader": "nope", "evidence": {}}',
                                         encoding="utf-8")
    code, report = dt(tmp_path, "--suite", "regression", "--evals-dir", str(evals))
    assert code == 2 and report["checks"][0]["error"].startswith("stopped:")


# Codex review 1 of PR #142


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_a_torn_line_after_clean_records_is_not_measured(tmp_path):
    path = write(tmp_path / "t.jsonl", CLEAN.read_text(encoding="utf-8") + TORN + "\n")
    row = no_hook_denial({"transcript": [path]})
    assert row["passed"] is None and row["measured"] == "not measured" and "1 line" in row["error"]
    code, _ = dt(tmp_path, "--task", "no-hook-denial", "--evidence", f"transcript={path}")
    assert code == 2


def test_a_denial_found_stays_a_failure_beside_a_torn_line(tmp_path):
    path = write(tmp_path / "t.jsonl", DENIED.read_text(encoding="utf-8") + TORN + "\n")
    row = no_hook_denial({"transcript": [path]})
    assert (row["measured"], row["passed"]) == (1, False)
    code, _ = dt(tmp_path, "--task", "no-hook-denial", "--evidence", f"transcript={path}")
    assert code == 1


@pytest.mark.parametrize("text", [
    "{}\n",                                                                   # no type
    '{"type": "user"}\n',                                                     # a message record without message
    '[1, 2]\n',                                                               # not an object
    '{"type": "attachment", "attachment": {"type": "date"}}\n',               # no conversation record at all
])
def test_unrecognizable_records_are_not_transcript_evidence(tmp_path, text):
    path = write(tmp_path / "t.jsonl", text)
    try:
        row = no_hook_denial({"transcript": [path]})
    except EvidenceError:
        return
    assert row["passed"] is None


def test_an_invalid_task_is_a_stopped_row_in_a_suite_of_clean_tasks(tmp_path):
    evals = tmp_path / "evals"
    shutil.copytree(TASK, evals / "no-hook-denial")
    write(evals / "typo/task.json", '{"id": "typo", "suit": "regression", "grader": "no_hook_denial", '
                                    '"evidence": {"transcript": {"root": "task", "path": "x.jsonl"}}}')
    write(tmp_path / f"main/logs/transcripts/harness-task-x-pr1-{S1}.jsonl", CLEAN.read_text(encoding="utf-8"))
    code, report = dt(tmp_path, "--suite", "regression", "--evals-dir", str(evals))
    assert code == 2
    assert [(r["task"], r["passed"]) for r in report["checks"]] == [("no-hook-denial", True), ("typo", None)]
    assert report["checks"][1]["error"].startswith("stopped:")


def test_the_branch_glob_skips_a_branch_whose_name_extends_the_slug(tmp_path):
    folder = tmp_path / "main/logs/transcripts"
    write(folder / f"harness-task-x-pr7-{S1}.jsonl", CLEAN.read_text(encoding="utf-8"))
    write(folder / f"harness-task-x-pr7-other-pr8-{S2}.jsonl", DENIED.read_text(encoding="utf-8"))  # task-x-pr7-other
    write(folder / "harness-task-x-pr7-notes.jsonl", DENIED.read_text(encoding="utf-8"))            # not a session id
    code, report = dt(tmp_path, "--suite", "regression")
    assert code == 0
    assert [Path(p).name for p in report["checks"][0]["evidence"]] == [f"harness-task-x-pr7-{S1}.jsonl"]


GOOD_RULE = {"root": "task", "path": "fixtures/clean.synthetic.jsonl"}


@pytest.mark.parametrize("change", [
    {"grader": []},
    {"grader": None},
    {"id": 5},
    {"suite": ["regression"]},
    {"references": None},
    {"references": [{"name": "r", "verdict": "pass", "evidence": {"transcript": {"root": "task", "path": 3}}}]},
    {"references": [{"name": "r", "verdict": "pass", "evidence": {}}]},
    {"references": ["x"]},
    {"evidence": {"log": GOOD_RULE}},
    {"evidence": {"transcript": "fixtures/clean.synthetic.jsonl"}},
    {"evidence": {"transcript": {"root": "task", "path": 3}}},
    {"evidence": {"transcript": {"root": "task", "glob": ["*"]}}},
    {"evidence": {"transcript": {"root": "home", "path": "x.jsonl"}}},
    {"evidence": {"transcript": {"root": "task", "path": "a", "glob": "b"}}},
    {"evidence": {"transcript": {"root": "task", "path": "../outside.jsonl"}}},
    {"evidence": {"transcript": {"root": "task", "glob": "../*.jsonl"}}},
    {"evidence": {"transcript": {"root": "task", "path": "C:/outside.jsonl"}}},
    {"evidence": []},
])
@pytest.mark.parametrize("references", [False, True])
def test_a_malformed_task_json_is_a_stopped_row_with_a_report(tmp_path, change, references):
    evals = tmp_path / "evals"
    shutil.copytree(TASK, evals / "no-hook-denial")
    write(tmp_path / "evals/outside.jsonl", CLEAN.read_text(encoding="utf-8"))  # an escape would find clean evidence
    spec = {**json.loads((TASK / "task.json").read_text(encoding="utf-8")), "evidence": {"transcript": GOOD_RULE},
            **change}
    write(evals / "no-hook-denial/task.json", json.dumps(spec))
    try:
        code, report = dt(tmp_path, "--suite", "regression", "--evals-dir", str(evals),
                          *(["--references"] * references))
    except Exception as exc:          # before the fix: a crash, no report
        pytest.fail(f"crashed: {type(exc).__name__}: {exc}")
    assert code == 2 and report is not None
    assert all(r["passed"] is None and r["error"].startswith("stopped:") for r in report["checks"])


def test_an_explicit_evidence_override_may_point_anywhere(tmp_path):
    path = write(tmp_path / "elsewhere/t.jsonl", CLEAN.read_text(encoding="utf-8"))
    code, report = dt(tmp_path, "--task", "no-hook-denial", "--evidence", f"transcript={path}")
    assert code == 0 and report["checks"][0]["evidence"] == [str(path.resolve())]


def test_two_copies_of_one_session_count_a_denial_once(tmp_path):
    """Review of #142 by the main session: prnone and pr142 copies of one transcript gave 2 for 1 denial."""
    from twinqa.evals.graders import no_hook_denial
    denied = ROOT / "evals/no-hook-denial/fixtures/denied.synthetic.jsonl"
    copy = tmp_path / "copy.jsonl"
    copy.write_bytes(denied.read_bytes())
    once = no_hook_denial({"transcript": [denied]})
    twice = no_hook_denial({"transcript": [denied, copy]})
    assert twice["measured"] == once["measured"] and twice["passed"] is False

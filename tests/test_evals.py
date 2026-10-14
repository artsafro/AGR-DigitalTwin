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
    for path in (tmp_path / "empty.jsonl", tmp_path / "absent.jsonl"):
        with pytest.raises(EvidenceError):
            read_jsonl(path)


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
    shutil.copy(CLEAN, folder / "harness-task-x-pr7-s1.jsonl")
    shutil.copy(DENIED, folder / "harness-task-x-pr7-s2.jsonl")
    shutil.copy(DENIED, folder / "harness-task-x-other-pr7-s3.jsonl")        # another branch: not read
    code, report = dt(tmp_path, "--suite", "regression")
    assert code == 1
    assert [Path(p).name for p in report["checks"][0]["evidence"]] == ["harness-task-x-pr7-s1.jsonl",
                                                                       "harness-task-x-pr7-s2.jsonl"]


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

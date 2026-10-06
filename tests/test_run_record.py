import json
import os
from pathlib import Path
import sys

import pytest

from dt_ai.core.run_record import (
    EvidenceMismatch, OwnershipConflict, RunRecord, RunStopped, resource_lock,
)


def fixture_run(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("approved")
    inputs = {"source": source}
    run = RunRecord.create(tmp_path / "runs", "fixture", inputs, {"tool": "fixture-v1"})
    return run, inputs


def writer(output, counter):
    script = (
        "from pathlib import Path; "
        f"p=Path({str(counter)!r}); "
        "p.write_text(str(int(p.read_text())+1) if p.exists() else '1'); "
        f"Path({str(output)!r}).write_text('exported')"
    )
    return [sys.executable, "-c", script]


def test_crash_after_produced_resumes_without_second_export(tmp_path):
    run, inputs = fixture_run(tmp_path)
    output, counter = tmp_path / "fbx.txt", tmp_path / "counter"
    argv = writer(output, counter)
    assert run.run_stage("export", argv, {"fbx": output})["status"] == "produced"
    restarted = RunRecord.open(run.directory, inputs, {"tool": "fixture-v1"})
    assert restarted.run_stage("export", argv, {"fbx": output})["status"] == "produced"
    assert restarted.verify_stage("export", lambda files: Path(files["fbx"]).read_text() == "exported")["status"] == "verified"
    assert counter.read_text() == "1"
    assert len(restarted.read()["attempts"]) == 1


def test_stale_output_rejected_even_if_ledger_says_produced(tmp_path):
    run, _ = fixture_run(tmp_path)
    output, counter = tmp_path / "out", tmp_path / "counter"
    argv = writer(output, counter)
    run.run_stage("export", argv, {"out": output})
    output.write_text("corrupted")
    with pytest.raises(EvidenceMismatch, match="Stale output"):
        run.run_stage("export", argv, {"out": output})
    assert counter.read_text() == "1"


def test_changed_input_cannot_reuse_or_overwrite_prior_output(tmp_path):
    run, inputs = fixture_run(tmp_path)
    output, counter = tmp_path / "out", tmp_path / "counter"
    argv = writer(output, counter)
    run.run_stage("export", argv, {"out": output})
    inputs["source"].write_text("revised")
    with pytest.raises(EvidenceMismatch, match="fresh output"):
        run.run_stage("export", argv, {"out": output})
    replacement = tmp_path / "out-v2"
    record = run.run_stage("export", writer(replacement, counter), {"out": replacement})
    assert record["status"] == "produced"
    assert counter.read_text() == "2"
    assert len(run.read()["attempts"]) == 2


def test_concurrent_output_owner_rejected_before_command(tmp_path):
    run, _ = fixture_run(tmp_path)
    other = RunRecord.create(tmp_path / "runs", "other", run.inputs)
    output, counter = tmp_path / "shared", tmp_path / "counter"
    with resource_lock(output, str(other.directory)):
        with pytest.raises(OwnershipConflict, match="already owned"):
            run.run_stage("export", writer(output, counter), {"out": output})
    assert not counter.exists()
    assert not run.read()["attempts"]


def test_timeout_preserves_partial_stdout_and_stderr(tmp_path):
    run, _ = fixture_run(tmp_path)
    argv = [sys.executable, "-u", "-c",
            "import sys,time; print('partial out',flush=True); print('partial err',file=sys.stderr,flush=True); time.sleep(20)"]
    record = run.run_stage("export", argv, {"out": tmp_path / "missing"}, timeout=1)
    assert record["status"] == "interrupted"
    assert record["reason"] == "timeout"
    assert isinstance(record["spawned_pid"], int)
    if os.name == "nt":
        assert record["timeout_cleanup_argv"] == ["taskkill", "/PID", str(record["spawned_pid"]), "/T", "/F"]
        assert record["timeout_cleanup_returncode"] == 0
    assert "partial out" in Path(record["stdout"]).read_text()
    assert "partial err" in Path(record["stderr"]).read_text()
    assert json.loads(run.path.read_text())["attempts"][0]["stages"]["export"]["status"] == "interrupted"


def test_two_same_cause_failures_stop_run_and_keep_attempts(tmp_path):
    run, _ = fixture_run(tmp_path)
    argv = [sys.executable, "-c", "import sys; print('tool failed'); sys.exit(3)"]
    for _ in range(2):
        record = run.run_stage("export", argv, {"out": tmp_path / "out"}, reason="tool:missing-addon")
        assert record["status"] == "failed"
        assert record["returncode"] == 3
    ledger = run.read()
    assert ledger["stopped"] is True
    assert ledger["stop_reason"] == "tool:missing-addon"
    assert len(ledger["attempts"]) == 2
    with pytest.raises(RunStopped, match="missing-addon"):
        run.run_stage("export", argv, {"out": tmp_path / "out"})


def test_run_and_attempt_directories_never_reused(tmp_path):
    run, inputs = fixture_run(tmp_path)
    with pytest.raises(FileExistsError):
        RunRecord.create(tmp_path / "runs", "fixture", inputs)
    (run.directory / "attempt-001").mkdir()
    with pytest.raises(FileExistsError):
        run.new_attempt()


def test_verifier_cannot_modify_output_and_mark_verified(tmp_path):
    run, _ = fixture_run(tmp_path)
    output = tmp_path / "out"
    run.run_stage("export", writer(output, tmp_path / "counter"), {"out": output})

    def bad_verifier(files):
        Path(files["out"]).write_text("modified")
        return True

    with pytest.raises(EvidenceMismatch, match="during verification"):
        run.verify_stage("export", bad_verifier)
    assert run.read()["attempts"][0]["stages"]["export"]["status"] == "produced"


def test_stage_named_output_directory_does_not_conflict_with_logs(tmp_path):
    run, _ = fixture_run(tmp_path)
    attempt = run.new_attempt()
    output_directory = attempt / "export"
    output = output_directory / "snapshot.fbx"
    record = run.run_stage("export", writer(output, tmp_path / "counter"),
                           {"fbx": output}, resources=[output_directory])
    assert record["status"] == "produced"
    assert Path(record["stdout"]).parent == attempt / "logs" / "export"
    assert output.read_text() == "exported"


def test_distinct_generic_tool_failures_do_not_trigger_same_cause_stop(tmp_path):
    run, _ = fixture_run(tmp_path)
    for message in ("missing addon", "invalid mesh"):
        argv = [sys.executable, "-c", f"import sys; print({message!r},file=sys.stderr); sys.exit(3)"]
        record = run.run_stage("export", argv, {"out": tmp_path / "missing"})
        assert record["status"] == "failed"
    ledger = run.read()
    assert ledger["stopped"] is False
    assert ledger["attempts"][0]["stages"]["export"]["reason_fingerprint"] != record["reason_fingerprint"]


def test_repeated_identical_generic_stderr_and_exit_code_stop(tmp_path):
    run, _ = fixture_run(tmp_path)
    argv = [sys.executable, "-c", "import sys; print('missing addon',file=sys.stderr); sys.exit(3)"]
    for _ in range(2):
        run.run_stage("export", argv, {"out": tmp_path / "missing"})
    ledger = run.read()
    assert ledger["stopped"] is True
    fingerprints = [a["stages"]["export"]["reason_fingerprint"] for a in ledger["attempts"]]
    assert fingerprints[0] == fingerprints[1]


def test_stage_pid_records_exact_spawned_process(tmp_path):
    run, _ = fixture_run(tmp_path)
    output = tmp_path / "pid.txt"
    argv = [sys._base_executable, "-c", f"import os; from pathlib import Path; Path({str(output)!r}).write_text(str(os.getpid()))"]
    record = run.run_stage("pid", argv, {"pid": output})
    assert record["status"] == "produced"
    assert record["spawned_pid"] == int(output.read_text())
    assert run.read()["attempts"][0]["stages"]["pid"]["spawned_pid"] == int(output.read_text())


def test_cached_earlier_stage_verifies_exact_returned_evidence(tmp_path):
    run, _ = fixture_run(tmp_path)
    first, second = tmp_path / "a", tmp_path / "b"
    counter = tmp_path / "counter"
    argv_a = writer(first, counter)
    run.run_stage("export", argv_a, {"out": first})
    run.run_stage("export", writer(second, counter), {"out": second})
    cached_a = run.run_stage("export", argv_a, {"out": first})
    assert counter.read_text() == "2"
    with pytest.raises(EvidenceMismatch, match="Ambiguous"):
        run.verify_stage("export", lambda _: True)
    verified = run.verify_stage("export", lambda files: Path(files["out"]) == first,
                                expected_signature=cached_a["signature"])
    assert verified["outputs"]["out"]["path"] == str(first.resolve())
    assert run.read()["attempts"][0]["stages"]["export"]["status"] == "verified"
    assert run.read()["attempts"][1]["stages"]["export"]["status"] == "produced"

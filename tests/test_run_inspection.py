import json
from pathlib import Path
import sys

import pytest

from dt_ai.core.adapter_report import AdapterReport, Check
from dt_ai.core.io import digest, json_bytes
from dt_ai.core.run_inspection import inspect_run
from dt_ai.core.run_record import RunRecord, atomic_json, file_evidence


def fixture_run(tmp_path, state="produced"):
    source = tmp_path / "source.txt"
    source.write_text("original")
    inputs = {"source": source}
    context = {"profile": "NPM", "scope": "fixture-only", "tool": "fixture-v1"}
    run = RunRecord.create(tmp_path / "runs", "fixture", inputs, context)
    attempt = run.new_attempt()
    output = attempt / "out.txt"
    output.write_text("exported")
    facts = file_evidence({"out": output})
    argv, cwd = ["fixture-only"], str(tmp_path)
    signature = digest(json_bytes({"fingerprint": run.fingerprint(), "argv": argv,
                                   "cwd": cwd, "outputs": {"out": str(output)}}))
    ledger = run.read()
    ledger["attempts"][0]["stages"]["export"] = {
        "status": state, "signature": signature, "input_fingerprint": run.fingerprint(),
        "argv": argv, "cwd": cwd, "outputs": facts if state in {"produced", "verified"} else {},
    }
    atomic_json(run.path, ledger)
    manifest = attempt / "input-manifest.json"
    atomic_json(manifest, {"inputs": file_evidence(inputs), "context": context})
    return run, manifest, source, output


@pytest.mark.parametrize("state,action", [
    ("produced", "verify_saved_outputs_without_repeating_execution"),
    ("verified", "review_scope_and_acceptance_no_delivery_claim"),
    ("running", "confirm_process_and_artifacts_before_retry"),
    ("interrupted", "classify_failure_before_new_attempt"),
])
def test_scoped_states_do_not_mean_delivery(tmp_path, state, action):
    run, manifest, _, _ = fixture_run(tmp_path, state)
    result = inspect_run(run.directory, manifest)
    assert result["next_action"] == action
    assert result["stages"][0]["state"] == ("uncertain" if state == "running" else state)
    if state in {"running", "interrupted"}:
        assert result["evidence_integrity"] == "incomplete"
    assert result["delivery_passed"] is False


@pytest.mark.parametrize("target,mutation", [
    ("input", "tamper"), ("input", "missing"), ("output", "tamper"), ("output", "missing"),
])
def test_actual_files_are_checked(tmp_path, target, mutation):
    run, manifest, source, output = fixture_run(tmp_path, "verified")
    path = source if target == "input" else output
    path.write_text("changed") if mutation == "tamper" else path.unlink()
    result = inspect_run(run.directory, manifest)
    assert result["evidence_integrity"] == "failed"
    assert result["errors_total"] == 1
    assert result["stages"][0]["evidence_integrity"] == "failed"
    assert "fresh_outputs" in result["next_action"]


def test_manifest_and_stage_signatures_are_bound(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path)
    data = json.loads(manifest.read_text())
    data["context"]["scope"] = "different"
    atomic_json(manifest, data)
    with pytest.raises(ValueError, match="not bound"):
        inspect_run(run.directory, manifest)
    data["context"]["scope"] = "fixture-only"
    atomic_json(manifest, data)
    ledger = run.read()
    ledger["attempts"][0]["stages"]["export"]["argv"] = ["changed-command"]
    atomic_json(run.path, ledger)
    assert inspect_run(run.directory, manifest)["errors_total"] == 1


def test_latest_failed_attempt_supersedes_old_verified(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path, "verified")
    run.new_attempt()
    ledger = run.read()
    ledger["attempts"][-1]["stages"]["export"] = {"status": "failed", "outputs": {}}
    atomic_json(run.path, ledger)
    result = inspect_run(run.directory, manifest)
    assert result["stages"][0]["attempt"] == 2
    assert result["next_action"] == "classify_failure_before_new_attempt"


def test_repeated_failure_stop_is_never_reset(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path, "failed")
    ledger = run.read()
    ledger.update(stopped=True, stop_reason="same_failure")
    atomic_json(run.path, ledger)
    result = inspect_run(run.directory, manifest)
    assert result["stopped"] is True
    assert result["stop_reason"] == "same_failure"
    assert result["next_action"] == "investigate_stop_preserve_evidence"


def test_report_pass_strings_do_not_prove_native_checks(tmp_path):
    run, manifest, _, output = fixture_run(tmp_path, "verified")
    report_path = manifest.parent / "report.json"
    report = AdapterReport(operation="fixture", tool_version="v1", scope="fixture",
                           execution="completed", input_manifest=str(manifest),
                           output_manifest=str(output), checks=(
                               Check(id="native", status="pass", evidence="Native app reported OK"),
                               Check(id="visual", status="not_run", evidence="Awaiting human")),
                           pending_decisions=("Approve render",))
    atomic_json(report_path, report.model_dump(mode="json"))
    result = inspect_run(run.directory, manifest, report_path, ["native", "checker"])
    gates = {gate["id"]: gate for gate in result["unresolved_gates"]}
    assert result["report"]["form"] == "valid"
    assert result["report"]["evidence_claims_verified"] is False
    assert gates["native"]["status"] == "reported_pass_unverified"
    assert gates["checker"]["reported_status"] == "missing"
    assert gates["visual"]["status"] == "pending"
    assert result["delivery_passed"] is False


def test_required_checks_pending_without_report(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path, "verified")
    result = inspect_run(run.directory, manifest, required_checks=["agr"])
    assert result["unresolved_gates"][0]["reported_status"] == "missing"
    assert result["next_action"] == "review_required_evidence_and_pending_decisions"


def test_external_stage_output_rejected(tmp_path):
    run, manifest, source, _ = fixture_run(tmp_path)
    ledger = run.read()
    ledger["attempts"][0]["stages"]["export"]["outputs"] = file_evidence({"out": source})
    atomic_json(run.path, ledger)
    with pytest.raises(ValueError, match="outside"):
        inspect_run(run.directory, manifest)


def test_source_copy_tamper_is_not_hidden_by_intact_original(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path)
    copy = manifest.parent / "copied-source"
    copy.write_text("original")
    data = json.loads(manifest.read_text())
    data["source_copy"] = file_evidence({"copy": copy})
    atomic_json(manifest, data)
    copy.write_text("different")
    result = inspect_run(run.directory, manifest)
    assert result["current_inputs"] == "intact"
    assert result["evidence_integrity"] == "failed"


def test_report_wrong_manifest_is_not_evidence_for_this_run(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path, "verified")
    report_path = manifest.parent / "report.json"
    report = AdapterReport(operation="fixture", tool_version="v1", scope="fixture",
                           execution="completed", input_manifest=str(manifest.parent / "different-manifest.json"))
    atomic_json(report_path, report.model_dump(mode="json"))
    result = inspect_run(run.directory, manifest, report_path)
    assert result["report"]["form"] == "valid"
    assert result["report"]["input_manifest_binding"] == "different_or_relative"
    assert result["evidence_integrity"] == "failed"


@pytest.mark.parametrize("kind,integrity", [("missing", "missing"), ("unbound", "not_checked")])
def test_declared_report_output_is_not_silently_accepted(tmp_path, kind, integrity):
    run, manifest, _, _ = fixture_run(tmp_path, "verified")
    claimed = manifest.parent / "unbound-manifest.json"
    if kind == "unbound":
        claimed.write_text('{"claimed": "pass"}')
    report_path = manifest.parent / "report.json"
    report = AdapterReport(operation="fixture", tool_version="v1", scope="fixture",
                           execution="completed", input_manifest=str(manifest), output_manifest=str(claimed))
    atomic_json(report_path, report.model_dump(mode="json"))
    result = inspect_run(run.directory, manifest, report_path)
    assert result["report"]["output_manifest"]["binding"] == "not_stage_bound"
    assert result["report"]["output_manifest"]["integrity"] == integrity
    assert any(gate["id"] == "output_manifest" for gate in result["unresolved_gates"])
    assert result["errors_total"] == (1 if kind == "missing" else 0)
    assert result["next_action"] != "review_scope_and_acceptance_no_delivery_claim"


@pytest.mark.parametrize("kind", ["bound", "null", "outside", "relative"])
def test_report_output_binding_contract(tmp_path, kind):
    run, manifest, source, output = fixture_run(tmp_path, "verified")
    claim = {"bound": str(output), "null": None, "outside": str(source), "relative": "out.txt"}[kind]
    report_path = manifest.parent / "report.json"
    report = AdapterReport(operation="fixture", tool_version="v1", scope="fixture",
                           execution="completed", input_manifest=str(manifest), output_manifest=claim)
    atomic_json(report_path, report.model_dump(mode="json"))
    result = inspect_run(run.directory, manifest, report_path)
    info = result["report"]["output_manifest"]
    if kind == "bound":
        assert info["binding"] == "stage_output"
        assert info["integrity"] == "intact"
        assert result["report"]["evidence_claims_verified"] is False
    elif kind == "null":
        assert info["binding"] == "no_claim"
        assert result["unresolved_gates"] == []
    else:
        assert info["binding"] == "invalid_reference"
        assert info["integrity"] == "not_checked"
        assert result["errors_total"] == 1
        assert result["unresolved_gates"][0]["id"] == "output_manifest"


def test_cli_readonly_and_controlled_rejection(tmp_path, capsys, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from harness_status import main
    run, manifest, _, _ = fixture_run(tmp_path)
    lock = run.directory / "orphan.orchestration.lock"
    lock.write_text("preserve")
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    # A read-only inspector must not execute even a valid argv from a ledger.
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("Inspector executed subprocess"))
    assert main(["--run", str(run.directory), "--manifest", str(manifest)]) == 0
    assert json.loads(capsys.readouterr().out)["delivery_passed"] is False
    assert {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
    manifest.write_text("[]")
    assert main(["--run", str(run.directory), "--manifest", str(manifest)]) == 2
    assert "must be an object" in json.loads(capsys.readouterr().out)["error"]


def test_error_output_is_bounded(tmp_path):
    run, manifest, _, _ = fixture_run(tmp_path)
    ledger = run.read()
    stage = ledger["attempts"][0]["stages"]["export"]
    original = stage["outputs"]["out"]
    stage["outputs"] = {str(i): {**original, "path": str(manifest.parent / f"missing-{i}")} for i in range(8)}
    stage["signature"] = digest(json_bytes({"fingerprint": run.fingerprint(), "argv": stage["argv"],
                                            "cwd": stage["cwd"], "outputs": {k: v["path"] for k, v in stage["outputs"].items()}}))
    atomic_json(run.path, ledger)
    result = inspect_run(run.directory, manifest)
    assert result["errors_total"] == 8
    assert len(result["errors"]) == 5


@pytest.mark.parametrize("invalid_status", [[], {}])
def test_cli_malformed_stage_state_is_controlled(tmp_path, capsys, invalid_status):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from harness_status import main
    run, manifest, _, _ = fixture_run(tmp_path)
    ledger = run.read()
    ledger["attempts"][0]["stages"]["export"]["status"] = invalid_status
    atomic_json(run.path, ledger)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert main(["--run", str(run.directory), "--manifest", str(manifest)]) == 2
    assert json.loads(capsys.readouterr().out) == {"error": "Invalid stage state", "delivery_passed": False}
    assert {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before

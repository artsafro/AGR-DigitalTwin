"""Read-only inspection of a file-bound run; never an execution or delivery gate."""
from pathlib import Path
import re

from dt_ai.core.adapter_report import AdapterReport
from dt_ai.core.io import digest, json_bytes, read_json
from dt_ai.core.run_record import file_evidence, input_fingerprint


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _path(value, label, root=None):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a nonempty absolute path")
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    path = path.resolve()
    if root is not None and not path.is_relative_to(root):
        raise ValueError(f"{label} points outside the run directory")
    return path


def _facts(value, label, root=None):
    facts = _object(value, label)
    result = {}
    for key, item in facts.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{label} has an invalid key")
        item = _object(item, label + ":" + key)
        path = _path(item.get("path"), label + ":" + key, root)
        size, sha = item.get("bytes"), item.get("sha256")
        if type(size) is not int or size < 0 or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError(f"{label}:{key} has invalid size/hash")
        result[key] = {"path": str(path), "bytes": size, "sha256": sha}
    return result


def inspect_run(run_directory, manifest_path, report_path=None, required_checks=()):
    """Return evidence integrity and a safe next action without executing anything.

    Ledger and manifest are a consistency envelope, not authenticated attestations.
    Native or visual checks reported as pass remain claims requiring review.
    """
    root = Path(run_directory).resolve()
    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.is_relative_to(root):
        raise ValueError("Manifest points outside the run directory")
    ledger = _object(read_json((root / "run.json").read_bytes()), "ledger")
    manifest = _object(read_json(manifest_path.read_bytes()), "manifest")
    if ledger.get("version") != 1 or type(ledger.get("version")) is not int:
        raise ValueError("Unsupported ledger version")
    run_id = ledger.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", run_id):
        raise ValueError("Invalid run_id")
    baseline = ledger.get("input_fingerprint")
    if not isinstance(baseline, str) or not re.fullmatch(r"[0-9a-f]{64}", baseline):
        raise ValueError("Invalid ledger fingerprint")
    if type(ledger.get("stopped")) is not bool:
        raise ValueError("Invalid stopped state")
    inputs = _facts(manifest.get("inputs"), "inputs")
    if not inputs:
        raise ValueError("Manifest must declare inputs")
    context = _object(manifest.get("context"), "context")
    if digest(json_bytes({"inputs": inputs, "context": context})) != baseline:
        raise ValueError("Manifest inputs/context are not bound to the ledger fingerprint")
    requested = list(dict.fromkeys(required_checks))
    if any(not isinstance(key, str) or not key or len(key) > 120 for key in requested):
        raise ValueError("Invalid required check identifier")
    errors = []

    def compare(facts, label):
        ok = True
        for key, expected in facts.items():
            try:
                actual = file_evidence({key: expected["path"]})[key]
                if actual != expected:
                    errors.append(f"{label}:{key}: bytes/hash changed")
                    ok = False
            except OSError:
                errors.append(f"{label}:{key}: file missing or unreadable")
                ok = False
        return ok

    current_inputs = compare(inputs, "input")
    if current_inputs:
        try:
            current_inputs = input_fingerprint({key: fact["path"] for key, fact in inputs.items()}, context) == baseline
        except OSError:
            current_inputs = False
        if not current_inputs:
            errors.append("Inputs changed during inspection")
    if "source_copy" in manifest:
        compare(_facts(manifest["source_copy"], "source_copy", root), "source_copy")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list):
        raise ValueError("Attempts must be a list")
    latest = {}
    for number, attempt in enumerate(attempts, 1):
        attempt = _object(attempt, "attempt")
        if type(attempt.get("number")) is not int or attempt["number"] != number:
            raise ValueError("Attempt numbers must be consecutive")
        directory = _path(attempt.get("directory"), "attempt directory", root)
        if directory != root / f"attempt-{number:03d}":
            raise ValueError("Attempt directory is not bound to its number")
        for name, stage in _object(attempt.get("stages"), "stages").items():
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
                raise ValueError("Invalid stage identifier")
            stage = _object(stage, "stage")
            if not isinstance(stage.get("status"), str) or stage["status"] not in {"running", "produced", "verified", "failed", "interrupted"}:
                raise ValueError("Invalid stage state")
            outputs = _facts(stage.get("outputs"), "stage outputs", root)
            for log in ("stdout", "stderr"):
                if log in stage:
                    _path(stage[log], log, root)
            latest[name] = (number, stage, outputs)
    stages = []
    for name, (number, stage, outputs) in sorted(latest.items()):
        state = stage["status"]
        integrity = "not_checked"
        if state in {"produced", "verified"}:
            if not outputs:
                raise ValueError("Produced/verified stage must declare outputs")
            argv, cwd = stage.get("argv"), stage.get("cwd")
            if not isinstance(argv, list) or not argv or any(not isinstance(x, str) for x in argv):
                raise ValueError("Invalid stage argv")
            _path(cwd, "stage cwd")
            expected = digest(json_bytes({"fingerprint": baseline, "argv": argv, "cwd": cwd,
                                         "outputs": {key: fact["path"] for key, fact in outputs.items()}}))
            bound = stage.get("input_fingerprint") == baseline and stage.get("signature") == expected
            if not bound:
                errors.append(f"stage:{name}: signature/input binding changed")
            intact = compare(outputs, "stage:" + name)
            integrity = "intact" if intact and bound and current_inputs else "failed"
        stages.append({"stage": name, "attempt": number, "state": "uncertain" if state == "running" else state,
                       "recorded_state": state, "evidence_integrity": integrity,
                       "output_paths": {key: fact["path"] for key, fact in outputs.items()}})
    gates = []
    report_info = {"form": "not_supplied", "evidence_claims_verified": False}
    paths = {"run": str(root), "ledger": str(root / "run.json"), "manifest": str(manifest_path)}
    if report_path is not None:
        report_path = _path(str(Path(report_path).resolve()), "report", root)
        report = AdapterReport.model_validate(read_json(report_path.read_bytes()))
        paths["report"] = str(report_path)
        report_info.update(form="valid", operation=report.operation, execution=report.execution,
                           scope=report.scope, declared_input_manifest=report.input_manifest,
                           declared_output_manifest=report.output_manifest,
                           input_manifest_binding="matches" if Path(report.input_manifest).is_absolute()
                           and Path(report.input_manifest).resolve() == manifest_path else "different_or_relative")
        if report_info["input_manifest_binding"] != "matches":
            errors.append("Report input manifest is not bound to the supplied manifest")
        report_info["output_manifest"] = {"binding": "no_claim", "integrity": "not_checked"}
        if report.output_manifest is not None:
            claim = Path(report.output_manifest)
            output_info = {"binding": "not_stage_bound", "integrity": "not_checked"}
            output_gate = None
            if not claim.is_absolute() or not claim.resolve().is_relative_to(root):
                output_info.update(binding="invalid_reference", integrity="not_checked")
                errors.append("Report output manifest must reference an absolute path inside the run")
                output_gate = "invalid_reference"
            else:
                claim = claim.resolve()
                output_info["path"] = str(claim)
                bound_stage = next((s for s in stages if str(claim) in s["output_paths"].values()), None)
                if bound_stage:
                    output_info.update(binding="stage_output", integrity=bound_stage["evidence_integrity"])
                    if output_info["integrity"] != "intact":
                        output_gate = "stage_evidence_not_intact"
                else:
                    try:
                        # Establish readability only; no independent hash/provenance claim.
                        with claim.open("rb") as stream:
                            stream.read(1)
                        output_gate = "output_manifest_not_stage_bound"
                    except FileNotFoundError:
                        output_info["integrity"] = "missing"
                        errors.append("Report output manifest is missing")
                        output_gate = "missing"
                    except OSError:
                        output_info["integrity"] = "unreadable"
                        errors.append("Report output manifest is unreadable")
                        output_gate = "unreadable"
            report_info["output_manifest"] = output_info
            if output_gate:
                gates.append({"id": "output_manifest", "status": "pending", "detail": output_gate})
        by_id = {check.id: check for check in report.checks}
        if len(by_id) != len(report.checks):
            raise ValueError("Duplicate report check identifiers")
        keys = list(dict.fromkeys([*requested, *(c.id for c in report.checks if c.required)]))
        for key in keys:
            check = by_id.get(key)
            bound_stage = None
            if check and Path(check.evidence).is_absolute():
                claimed_path = str(Path(check.evidence).resolve())
                bound_stage = next((s for s in stages if claimed_path in s["output_paths"].values()), None)
            gates.append({"id": key, "reported_status": check.status if check else "missing",
                          "status": "reported_pass_unverified" if check and check.status == "pass" else "pending",
                          "evidence_claim": check.evidence if check else None,
                          "evidence_file_binding": "stage_output" if bound_stage else "not_stage_bound",
                          "evidence_file_integrity": bound_stage["evidence_integrity"] if bound_stage else "not_checked"})
        gates.extend({"id": "decision", "status": "pending", "detail": item} for item in report.pending_decisions)
        if report.execution != "completed":
            gates.append({"id": "report_execution", "status": "pending", "detail": report.execution})
    else:
        gates.extend({"id": key, "status": "pending", "reported_status": "missing"} for key in requested)
    if ledger["stopped"]:
        action = "investigate_stop_preserve_evidence"
    elif errors:
        action = "investigate_changed_or_missing_evidence_use_fresh_outputs"
    elif any(s["state"] == "uncertain" for s in stages):
        action = "confirm_process_and_artifacts_before_retry"
    elif any(s["state"] in {"failed", "interrupted"} for s in stages):
        action = "classify_failure_before_new_attempt"
    elif any(s["state"] == "produced" for s in stages):
        action = "verify_saved_outputs_without_repeating_execution"
    elif gates:
        action = "review_required_evidence_and_pending_decisions"
    elif stages:
        action = "review_scope_and_acceptance_no_delivery_claim"
    else:
        action = "plan_authorized_stage"
    return {"run_id": run_id, "profile": context.get("profile"), "scope": context.get("scope"),
            "stopped": ledger["stopped"], "stop_reason": ledger.get("stop_reason"),
            "current_inputs": "intact" if current_inputs else "failed",
            "evidence_integrity": "failed" if errors else ("intact" if stages and all(
                stage["evidence_integrity"] == "intact" for stage in stages) else "incomplete"), "stages": stages,
            "report": report_info, "unresolved_gates": gates, "next_action": action, "paths": paths,
            "errors_total": len(errors), "errors": errors[:5], "delivery_passed": False,
            "limits": ["Consistency of supplied files is not authenticated provenance",
                       "Recorded verification is scoped; native and visual claims require independent review",
                       "No process liveness or DCC scene recovery checked"]}

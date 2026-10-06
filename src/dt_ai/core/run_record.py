"""Local stage evidence ledger. A produced stage is not a delivery verdict.

Callers include relevant code, tool versions, parameters and profile hashes in
``context``. Verification callbacks must inspect the saved outputs themselves.
Locks fail closed after a crash: remove an orphan only after checking its owner.
"""

from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import re
import subprocess
import tempfile

from dt_ai.core.io import digest, json_bytes, read_json


class OwnershipConflict(RuntimeError):
    pass


class EvidenceMismatch(RuntimeError):
    pass


class RunStopped(RuntimeError):
    pass


def _name(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError(f"Unsafe identifier: {value}")
    return value


def file_evidence(paths):
    """Hash actual files; absent inputs/outputs are errors, never cache hits."""
    result = {}
    for key, value in sorted(paths.items()):
        path = Path(value).resolve()
        data = path.read_bytes()
        result[key] = {"path": str(path), "bytes": len(data), "sha256": digest(data)}
    return result


def input_fingerprint(inputs, context):
    return digest(json_bytes({"inputs": file_evidence(inputs), "context": context}))


def atomic_json(path, value):
    """Replace on the same filesystem, flush bytes, and read back exact data."""
    path = Path(path)
    data = json_bytes(value)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if path.read_bytes() != data or read_json(path.read_bytes()) != value:
            raise EvidenceMismatch(f"Ledger readback failed: {path}")
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def resource_lock(resource, owner):
    """Exclusive filesystem claim shared across runs, including directory claims."""
    resource = Path(resource).resolve()
    resource.parent.mkdir(parents=True, exist_ok=True)
    lock = resource.with_name(f".{resource.name}.orchestration.lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise OwnershipConflict(f"Resource already owned: {resource}; lock={lock}") from error
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(json_bytes({"owner": owner, "pid": os.getpid(), "resource": str(resource)}))
        yield
    finally:
        lock.unlink(missing_ok=True)


class RunRecord:
    """Fresh attempts with resumable, hash-bound stage evidence."""

    def __init__(self, directory, inputs, context):
        self.directory = Path(directory).resolve()
        self.inputs = {key: str(Path(value).resolve()) for key, value in inputs.items()}
        self.context = context
        self.path = self.directory / "run.json"

    @classmethod
    def create(cls, root, run_id, inputs, context=None):
        directory = Path(root).resolve() / _name(run_id)
        directory.mkdir(parents=True, exist_ok=False)
        run = cls(directory, inputs, context or {})
        atomic_json(run.path, {"version": 1, "run_id": run_id,
                              "input_fingerprint": run.fingerprint(),
                              "attempts": [], "stopped": False})
        return run

    @classmethod
    def open(cls, directory, inputs, context=None):
        run = cls(directory, inputs, context or {})
        run.read()
        return run

    def fingerprint(self):
        return input_fingerprint(self.inputs, self.context)

    def read(self):
        return read_json(self.path.read_bytes())

    def _attempt(self, ledger):
        number = len(ledger["attempts"]) + 1
        directory = self.directory / f"attempt-{number:03d}"
        directory.mkdir(exist_ok=False)
        attempt = {"number": number, "directory": str(directory), "stages": {}}
        ledger["attempts"].append(attempt)
        atomic_json(self.path, ledger)
        return attempt

    def new_attempt(self):
        with resource_lock(self.directory, str(self.directory)):
            ledger = self.read()
            if ledger["stopped"]:
                raise RunStopped(ledger.get("stop_reason", "stopped"))
            return Path(self._attempt(ledger)["directory"])

    def _matching(self, ledger, stage, signature):
        for attempt in reversed(ledger["attempts"]):
            record = attempt["stages"].get(stage)
            if record and record["signature"] == signature and record["status"] in {"produced", "verified"}:
                actual = file_evidence({key: value["path"] for key, value in record["outputs"].items()})
                if actual != record["outputs"]:
                    raise EvidenceMismatch(f"Stale output for stage {stage}; start a fresh run/output")
                return record
        return None

    def run_stage(self, stage, argv, outputs, *, cwd=None, timeout=None,
                  reason="tool_error", resources=()):
        """Run a deterministic command or reuse produced/verified exact evidence.

        A failed stage retries in a fresh attempt. Existing output files are never
        overwritten on a retry. Callers must choose new outputs for that attempt.
        Windows timeout terminates only the tree rooted at the spawned child PID.
        POSIX timeout kills the direct child; detached helpers are unsupported.
        """
        _name(stage)
        argv = [str(part) for part in argv]
        cwd = str(Path(cwd or Path.cwd()).resolve())
        outputs = {key: str(Path(value).resolve()) for key, value in outputs.items()}
        if not outputs:
            raise ValueError("Stage must declare at least one evidence output")
        with ExitStack() as stack:
            stack.enter_context(resource_lock(self.directory, str(self.directory)))
            for resource in sorted({*outputs.values(), *(str(Path(p).resolve()) for p in resources)}):
                stack.enter_context(resource_lock(resource, str(self.directory)))
            ledger = self.read()
            if ledger["stopped"]:
                raise RunStopped(ledger.get("stop_reason", "stopped"))
            fingerprint = self.fingerprint()
            signature = digest(json_bytes({"fingerprint": fingerprint, "argv": argv,
                                           "cwd": cwd, "outputs": outputs}))
            cached = self._matching(ledger, stage, signature)
            if cached:
                return cached
            if any(Path(path).exists() for path in outputs.values()):
                raise EvidenceMismatch("Unverified or changed-input output exists; use fresh output paths")
            if not ledger["attempts"] or stage in ledger["attempts"][-1]["stages"]:
                attempt = self._attempt(ledger)
            else:
                attempt = ledger["attempts"][-1]
            log_dir = Path(attempt["directory"]) / "logs" / stage
            log_dir.mkdir(parents=True, exist_ok=False)
            record = {"status": "running", "signature": signature,
                      "input_fingerprint": fingerprint, "argv": argv,
                      "cwd": cwd, "outputs": {},
                      "stdout": str(log_dir / "stdout.log"), "stderr": str(log_dir / "stderr.log")}
            attempt["stages"][stage] = record
            atomic_json(self.path, ledger)
            with Path(record["stdout"]).open("wb") as stdout, Path(record["stderr"]).open("wb") as stderr:
                try:
                    child = subprocess.Popen(argv, cwd=cwd, stdout=stdout, stderr=stderr)
                    record["spawned_pid"] = child.pid
                    atomic_json(self.path, ledger)
                    try:
                        returncode = child.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        if os.name == "nt":
                            cleanup_argv = ["taskkill", "/PID", str(child.pid), "/T", "/F"]
                            record["timeout_cleanup_argv"] = cleanup_argv
                            try:
                                cleanup = subprocess.run(cleanup_argv, capture_output=True, timeout=10, check=False)
                                record["timeout_cleanup_returncode"] = cleanup.returncode
                                record["timeout_cleanup_stdout"] = cleanup.stdout.decode("utf-8", errors="replace")
                                record["timeout_cleanup_stderr"] = cleanup.stderr.decode("utf-8", errors="replace")
                                if cleanup.returncode:
                                    record["timeout_cleanup_error"] = "Process tree cleanup failed; descendant termination unverified"
                            except (OSError, subprocess.TimeoutExpired) as error:
                                record["timeout_cleanup_error"] = str(error)
                        else:
                            child.kill()
                        try:
                            child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait(timeout=5)
                            record["timeout_cleanup_error"] = "Tree cleanup did not terminate root promptly; direct root killed"
                        if record.get("timeout_cleanup_error"):
                            ledger.update(stopped=True, stop_reason="timeout_cleanup_failed")
                        record["returncode"] = child.returncode
                        raise
                    record["returncode"] = returncode
                    if returncode:
                        record.update(status="failed", reason=reason)
                    else:
                        record["outputs"] = file_evidence(outputs)
                        if self.fingerprint() != record["input_fingerprint"]:
                            raise EvidenceMismatch("Inputs changed while stage ran")
                        record["status"] = "produced"
                except subprocess.TimeoutExpired:
                    record.update(status="interrupted", reason="timeout", timeout_seconds=timeout)
                except (OSError, EvidenceMismatch) as error:
                    record.update(status="failed", reason=reason, error=str(error))
            if record["status"] in {"failed", "interrupted"}:
                cause = {"reason": record["reason"]}
                if record["reason"] == "tool_error":
                    cause.update(returncode=record.get("returncode"),
                                 stderr_sha256=digest(Path(record["stderr"]).read_bytes()),
                                 error=record.get("error"))
                record["reason_fingerprint"] = digest(json_bytes(cause))
                prior = [a["stages"][stage] for a in ledger["attempts"] if stage in a["stages"]]
                if len(prior) >= 2 and all(r.get("reason_fingerprint") == record["reason_fingerprint"] for r in prior[-2:]):
                    ledger.update(stopped=True, stop_reason=ledger.get("stop_reason", record["reason"]))
            atomic_json(self.path, ledger)
            return record

    def verify_stage(self, stage, verifier, *, expected_signature=None):
        """Read saved files and record a scoped verifier result, never passed=true."""
        with resource_lock(self.directory, str(self.directory)):
            ledger = self.read()
            candidates = [attempt["stages"][stage] for attempt in ledger["attempts"]
                          if stage in attempt["stages"]
                          and attempt["stages"][stage]["status"] in {"produced", "verified"}
                          and (expected_signature is None or
                               attempt["stages"][stage]["signature"] == expected_signature)]
            if len(candidates) > 1:
                raise EvidenceMismatch("Ambiguous stage evidence; pass the returned record signature")
            for record in candidates:
                if record:
                    if record["input_fingerprint"] != self.fingerprint():
                        raise EvidenceMismatch("Verification inputs changed")
                    paths = {key: value["path"] for key, value in record["outputs"].items()}
                    if file_evidence(paths) != record["outputs"]:
                        raise EvidenceMismatch("Verification outputs changed")
                    verdict = verifier(paths)
                    if verdict is not True:
                        raise EvidenceMismatch("Scoped verifier did not return True")
                    if file_evidence(paths) != record["outputs"] or self.fingerprint() != record["input_fingerprint"]:
                        raise EvidenceMismatch("Evidence changed during verification")
                    record["status"] = "verified"
                    atomic_json(self.path, ledger)
                    return record
            raise EvidenceMismatch(f"No produced evidence for {stage}")

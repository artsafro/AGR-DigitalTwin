# Ported from AGR src/dt_ai/core/models.py (sha256 7d257e4ecc00) on 2026-10-06;
# changes: only Finding/ValidationReport kept, as dataclasses (no pydantic, no BuildJob);
# findings grouped into V001-V017 stages from DELIVERY_VALIDATOR.yaml; `passed` is computed.
"""Validation findings and report (statuses per DELIVERY_VALIDATOR.yaml output.statuses)."""
from dataclasses import asdict, dataclass, field

STATUSES = ("pass", "fail", "review", "not_run")
# Stage status = worst finding: fail > review > not_run > pass. A stage without findings is not_run.
RANK = {"pass": 0, "not_run": 1, "review": 2, "fail": 3}


@dataclass
class Finding:
    name: str
    status: str
    observed: str
    expected: str
    source_pdf_pages: list[int]
    evidence: str = ""
    conflicts: list[int] = field(default_factory=list)

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"Unknown status {self.status}")


@dataclass
class Stage:
    id: str
    check: str
    gate: str  # blocking | manual_review
    source_pdf_pages: list[int]
    findings: list[Finding] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.findings:
            return "not_run"
        return max((f.status for f in self.findings), key=RANK.__getitem__)


@dataclass
class ValidationReport:
    profile: str
    target: str
    target_sha256: str
    source_sha256: str
    source_pdf_verified: bool
    stages: list[Stage]
    notes: list[str] = field(default_factory=list)

    @property
    def machine_stages(self):
        return [s for s in self.stages if s.gate == "blocking"]

    @property
    def passed(self) -> bool:
        """True only if every mandatory machine check ran and passed (no fail/review/not_run)."""
        return bool(self.machine_stages) and all(s.status == "pass" for s in self.machine_stages)

    @property
    def exit_code(self) -> int:
        if self.passed:
            return 0
        if any(f.status == "fail" for s in self.stages for f in s.findings):
            return 1
        return 2

    def to_dict(self) -> dict:
        stages = []
        for s in self.stages:
            d = asdict(s)
            d["status"] = s.status
            stages.append(d)
        counts = {k: sum(s.status == k for s in self.machine_stages) for k in STATUSES}
        return {"profile": self.profile, "target": self.target, "target_sha256": self.target_sha256,
                "source_sha256": self.source_sha256, "source_pdf_verified": self.source_pdf_verified,
                "passed": self.passed, "exit_code": self.exit_code, "machine_stage_counts": counts,
                "manual_reviews_pending": [s.id for s in self.stages if s.gate == "manual_review"],
                "stages": stages, "notes": self.notes}

    def summary(self) -> str:
        lines = [f"Target:  {self.target}", f"SHA256:  {self.target_sha256}", f"Profile: {self.profile.upper()}",
                 f"Regulation sha256 {self.source_sha256[:12]}... "
                 + ("verified" if self.source_pdf_verified else "(PDF not found; hash from lock only)"), ""]
        for s in self.stages:
            lines.append(f"{s.id} [{s.status.upper():7}] {s.gate:13} {s.check}")
            for f in s.findings:
                if f.status != "pass" or len(s.findings) <= 3:
                    tag = f" conflict #{','.join(map(str, f.conflicts))}" if f.conflicts else ""
                    lines.append(f"     - {f.status:7} {f.name}: {f.observed} (expected: {f.expected}; reg p.{','.join(map(str, f.source_pdf_pages))}{tag})")
        lines += [""] + [f"Note: {n}" for n in self.notes]
        verdict = "PASSED" if self.passed else "NOT PASSED"
        lines.append(f"Verdict: {verdict} (exit {self.exit_code}); manual checks "
                     f"{', '.join(s.id for s in self.stages if s.gate == 'manual_review')} still need signed review.")
        return "\n".join(lines)

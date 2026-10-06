"""Operation evidence, deliberately separate from delivery certification."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Check(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1, max_length=120)
    status: Literal["pass", "fail", "not_run", "review"]
    required: bool = True
    evidence: str = Field(min_length=1, max_length=1000)


class AdapterReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0.0"] = "1.0.0"
    operation: str = Field(min_length=1, max_length=120)
    tool_version: str = Field(min_length=1, max_length=120)
    scope: str = Field(min_length=1, max_length=1000)
    execution: Literal["completed", "failed", "not_run"]
    input_manifest: str = Field(min_length=1, max_length=1000)
    output_manifest: str | None = Field(default=None, max_length=1000)
    checks: tuple[Check, ...] = ()
    pending_decisions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    # This evidence envelope must never certify delivery.
    delivery_passed: Literal[False] = False

    def summary(self):
        required = [check for check in self.checks if check.required]
        checks_passed = (self.execution == "completed" and bool(required)
                         and all(check.status == "pass" for check in required)
                         and not self.pending_decisions)
        problems = [check for check in self.checks if check.status != "pass"]
        return {
            "operation": self.operation,
            "execution": self.execution,
            "required_checks_passed": checks_passed,
            "checks_total": len(self.checks),
            "issues_total": len(problems),
            "issues": [{"id": c.id, "status": c.status} for c in problems[:5]],
            "pending_decisions_total": len(self.pending_decisions),
            "limitations_total": len(self.limitations),
            "output_manifest": self.output_manifest,
            "delivery_passed": False,
        }


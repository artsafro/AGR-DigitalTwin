from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Byte = Annotated[int, Field(ge=0, le=255, strict=True)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Name = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$", max_length=120)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)
    schema_version: Literal["1.0.0"] = "1.0.0"


class SourceRef(Contract):
    kind: Literal["synthetic", "pdf", "model", "user"]
    reference: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1, le=100000)
    sha256: Hash | None = None
    region: list[Finite] | None = Field(default=None, min_length=4, max_length=4)

    @model_validator(mode="after")
    def pdf_has_page(self):
        if self.kind == "pdf" and (self.page is None or self.sha256 is None):
            raise ValueError("PDF provenance requires page and sha256")
        return self


class Approval(Contract):
    actor: str = Field(min_length=1)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    scope: Literal["synthetic_fixture", "project"]
    note: str = Field(min_length=1)


class Material(Contract):
    id: Name
    label: str = Field(min_length=1)
    status: Literal["proposed", "approved", "conflict"]
    source: SourceRef
    approval: Approval | None = None
    diffuse_rgb: list[Byte] = Field(min_length=3, max_length=3)
    emissive: Byte
    roughness: Byte
    metallic: Byte
    pattern_delta: Byte = 12
    normal_opengl_rgb: list[Byte] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def approved_has_evidence(self):
        if self.status == "approved" and self.approval is None:
            raise ValueError("approved requires an explicit decision")
        if self.approval and self.source.kind == "synthetic" and self.approval.scope != "synthetic_fixture":
            raise ValueError("Synthetic material cannot carry project approval")
        return self


class MaterialRegistry(Contract):
    materials: list[Material] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({m.id for m in self.materials}) != len(self.materials):
            raise ValueError("Duplicate material IDs")
        return self


class WindowType(Contract):
    id: Name
    width_m: Positive
    height_m: Positive
    source: SourceRef
    status: Literal["proposed", "approved", "conflict"]
    approval: Approval | None = None

    @model_validator(mode="after")
    def approved_has_evidence(self):
        if self.status == "approved" and not self.approval:
            raise ValueError("Window approval is missing")
        return self


class Placement(Contract):
    coordinate_system: Literal["SYNTHETIC_LOCAL", "MSK-77"]
    project_zero_m: Finite | None = None
    insertion_xy: list[Finite] | None = Field(default=None, min_length=2, max_length=2)
    source: SourceRef
    status: Literal["unknown", "proposed", "approved"]
    approval: Approval | None = None

    @model_validator(mode="after")
    def confirmed_coordinates(self):
        if self.status == "approved" and (self.project_zero_m is None or self.insertion_xy is None or not self.approval):
            raise ValueError("Approved placement requires coordinates, elevation, and approval")
        return self


class ProjectManifest(Contract):
    project_id: Name
    synthetic: bool
    address_token: Name
    standards_sha256: Hash
    profile_versions: dict[Literal["NPM", "VPM"], str]
    inputs: dict[str, Hash] = Field(min_length=1)
    placement: Placement

    @model_validator(mode="after")
    def profiles_and_placement(self):
        if set(self.profile_versions) != {"NPM", "VPM"}:
            raise ValueError("Both profile versions required")
        if not self.synthetic and self.placement.coordinate_system == "SYNTHETIC_LOCAL":
            raise ValueError("Real project cannot use synthetic coordinates")
        return self


class Surface(Contract):
    id: Name
    material_id: Name
    vertices: list[list[Finite]] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def xyz(self):
        if any(len(v) != 3 for v in self.vertices):
            raise ValueError("Expected XYZ vertices")
        return self


class MasterBuilding(Contract):
    synthetic: bool
    source: SourceRef
    surfaces: list[Surface] = Field(min_length=1)

    @model_validator(mode="after")
    def stable_ids(self):
        if len({s.id for s in self.surfaces}) != len(self.surfaces):
            raise ValueError("Duplicate surface IDs")
        if self.synthetic != (self.source.kind == "synthetic"):
            raise ValueError("Master/source synthetic status mismatch")
        return self


class BuildJob(Contract):
    project: ProjectManifest
    registry: MaterialRegistry
    master: MasterBuilding

    @model_validator(mode="after")
    def references(self):
        known = {m.id for m in self.registry.materials}
        used = {s.material_id for s in self.master.surfaces}
        if known != used:
            raise ValueError("Each material must be used; every surface must reference a known material")
        if self.project.synthetic != self.master.synthetic:
            raise ValueError("Project/master synthetic mismatch")
        if not self.project.synthetic and any(m.source.kind == "synthetic" for m in self.registry.materials):
            raise ValueError("Real project cannot use synthetic provenance")
        return self


class Finding(Contract):
    id: str
    status: Literal["pass", "fail", "review", "not_applicable", "not_run"]
    source_pdf_pages: list[int] = Field(min_length=1)
    observed: str
    expected: str
    evidence: str


class ValidationReport(Contract):
    synthetic: bool
    source_sha256: Hash
    checks: list[Finding]
    development_checks_passed: bool
    # This first slice deliberately cannot certify customer delivery.
    passed: Literal[False] = False
    limitations: list[str] = Field(min_length=1)


SCHEMAS = {c.__name__: c for c in [ProjectManifest, MaterialRegistry, WindowType,
                                   Placement, BuildJob, ValidationReport, MasterBuilding]}


from dt_ai.core.adapter_report import AdapterReport
SCHEMAS["AdapterReport"] = AdapterReport


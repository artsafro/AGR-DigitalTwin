"""Intake formats (docs/HARNESS_PLAN.md §15, user decisions 2026-10-11): what "study the sources" writes to
jobs/<JOB>/intake/ — sources.json (the inventory) and spec-draft.json (a spec whose blocks may be null,
each with a confidence and its sources). picture.md and questions.md are Markdown (dt_ai.intake.check).
Pattern: none — intake code (REVIEW_CHECKLIST Q1: new-case, HARNESS_PLAN §15).
"""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Confidence = Literal["measured", "read_from_drawing", "estimated", "unknown"]
Read = Literal["geometry", "dimensions", "image", "materials", "metadata"]
Format = Literal["rvt", "ifc", "skp", "max", "fbx", "blend", "obj", "dwg", "dxf", "pdf", "image", "pptx", "other"]

# source priority (§15): BIM -> 3D -> 2D with dimensions -> PDF -> images only; lower rank = better
RANK = {"rvt": 1, "ifc": 1, "skp": 2, "max": 2, "fbx": 2, "blend": 2, "obj": 2, "dwg": 3, "dxf": 3,
        "pdf": 4, "pptx": 5, "image": 5, "other": 6}
# spec blocks a draft carries; the first three must be filled before a spec is built
BLOCKS = ("frame", "levels", "floors", "roof", "terraces", "attachments", "opening_depth_default_m",
          "plate_gap_m", "plate_overlap_m")
REQUIRED = ("frame", "levels", "floors", "roof")
# what a format can give (review 1 of PR #71): geometry only from BIM, 3D and CAD; a picture never measures
_SOLID = {"geometry", "dimensions", "image", "materials", "metadata"}
ALLOWED_READS = {
    **{f: _SOLID for f in ("rvt", "ifc", "skp", "max", "fbx", "blend", "obj")},
    "dwg": {"geometry", "dimensions", "materials", "metadata"}, "dxf": {"geometry", "dimensions", "materials", "metadata"},
    "pdf": {"dimensions", "image", "materials", "metadata"}, "pptx": {"dimensions", "image", "materials", "metadata"},
    "image": {"image", "materials", "metadata"}, "other": {"metadata"},
}


class Part(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SourceEntry(Part):
    path: str = Field(min_length=1, description="relative to jobs/<JOB>/sources/")
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    bytes: int | None = Field(default=None, ge=0)
    format: Format
    reads: list[Read] = Field(description="what was read from it; empty when it did not open")
    units: str | None = None
    frame: str | None = Field(default=None, description="coordinate system / zero / up axis as found")
    version: str | None = None
    opened: bool
    not_opened_reason: str | None = None
    role: Literal["primary", "check", "materials", "none"] = Field(
        description="primary: the best-ranked source that gives geometry or dimensions; lower-ranked sources "
                    "only check it or give materials (§15)")

    @model_validator(mode="after")
    def consistent(self):
        beyond = sorted(set(self.reads) - ALLOWED_READS[self.format])
        if beyond:
            raise ValueError(f"{self.path}: a {self.format} file cannot give {beyond} (geometry only from BIM, 3D or "
                             "CAD; images and PDF never measure)")
        if not self.opened and (self.reads or not self.not_opened_reason):
            raise ValueError(f"{self.path}: a source that did not open reads nothing and says why")
        if self.opened and self.not_opened_reason:
            raise ValueError(f"{self.path}: opened, yet a reason it did not open")
        return self


class SourcesFile(Part):
    object: str = Field(min_length=1)
    made: str = Field(description="ISO date of the inventory")
    files: list[SourceEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def roles(self):
        paths = [f.path for f in self.files]
        if len(set(paths)) != len(paths):
            raise ValueError("a source is listed twice")
        shaped = [f for f in self.files if f.opened and {"geometry", "dimensions"} & set(f.reads)]
        best = min((RANK[f.format] for f in shaped), default=None)
        for f in self.files:
            if f.role == "primary" and (f not in shaped or RANK[f.format] != best):
                raise ValueError(f"{f.path}: primary only for the best-ranked source with geometry or dimensions "
                                 f"(rank {best}); lower-ranked ones check it or give materials (§15)")
        if shaped and not any(f.role == "primary" for f in self.files):
            raise ValueError("no primary source although some give geometry or dimensions")
        return self


class Block(Part):
    value: Any = None
    confidence: Confidence
    sources: list[str] = Field(default_factory=list, description="paths of sources.json, optionally #locator")
    note: str | None = None

    @model_validator(mode="after")
    def null_is_unknown(self):
        if (self.value is None) != (self.confidence == "unknown"):
            raise ValueError("a block is null exactly when its confidence is unknown (no default, no guess)")
        if self.value is not None and not self.sources:
            raise ValueError("a filled block names its sources")
        return self


class Anchor(Part):
    needed: bool = Field(description="true when only images / PDF without dimensions give the shape")
    confirmed: bool = False
    what: str | None = Field(default=None, description="the dimension the user confirmed, e.g. 'door height 2.1 m'")
    question: str | None = Field(default=None, description="the questions.md id that asks for it")

    @model_validator(mode="after")
    def asked(self):
        if self.needed and not self.question:          # asked, and confirmed only through the user's answer
            raise ValueError("a needed anchor is asked in questions.md (its question id), also once confirmed")
        if self.confirmed and not self.what:
            raise ValueError("a confirmed anchor says what was confirmed")
        return self


class SpecDraft(Part):
    object: str = Field(min_length=1)
    profile: Literal["npm_min", "mid"] | None = None
    spec_version: str | None = None
    anchor: Anchor
    blocks: dict[str, Block]

    @model_validator(mode="after")
    def known_blocks(self):
        unknown = sorted(set(self.blocks) - set(BLOCKS))
        missing = [b for b in REQUIRED if b not in self.blocks]
        if unknown or missing:
            raise ValueError(f"spec-draft blocks: unknown {unknown}, missing {missing}")
        return self

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Finite = Annotated[float, Field(allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class SpecPart(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Frame(SpecPart):
    """Mandatory: source and the 4x4 matrix from source coordinates to the object system."""
    object: str = Field(min_length=1)
    source: str = Field(min_length=1)
    to_object: list[list[Finite]] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def is_affine(self):
        if any(len(row) != 4 for row in self.to_object) or self.to_object[3] != [0, 0, 0, 1]:
            raise ValueError("to_object must be a 4x4 affine matrix with last row 0 0 0 1")
        return self


class Level(SpecPart):
    name: str = Field(pattern=r"^[A-Za-z0-9_]+$")
    elev_m: Finite


class Opening(SpecPart):
    wall: int = Field(ge=0)
    x_m: NonNegative
    sill_m: Finite
    w_m: Positive
    h_m: Positive
    depth_m: NonNegative
    window_type: int | None = None
    # anchor that found it (user decision 2026-10-08, #7): a hole in the body, a glass pane, or both
    source: Literal["hole", "glass", "hole+glass"] | None = None
    # material id of an opening plane in it (group `opening`, ADR 0001); not the window type
    material_id: int | None = None
    # two overlapping opening planes with different ids: material_id is left null
    plane_conflict: bool = False


class Floor(SpecPart):
    level: str
    # [x, y] or [x, y, {"r": radius}] for a rounded corner (HARNESS_PLAN §3)
    contour: list[list[Finite | dict[str, Positive]]] | None = None
    openings: list[Opening] = []
    typical_of: str | None = None
    repeat_to: str | None = None

    @model_validator(mode="after")
    def contour_or_typical(self):
        if (self.contour is None) == (self.typical_of is None):
            raise ValueError(f"floor {self.level}: give either a contour or typical_of")
        for p in self.contour or []:
            if len(p) not in (2, 3) or any(isinstance(c, dict) for c in p[:2]) or (
                    len(p) == 3 and set(p[2]) != {"r"}):
                raise ValueError(f"floor {self.level}: contour point must be [x, y] or [x, y, {{'r': r}}]")
        if self.contour is not None and len(self.contour) < 3:
            raise ValueError(f"floor {self.level}: contour needs at least 3 points")
        for o in self.openings:
            if self.contour is not None and o.wall >= len(self.contour):
                raise ValueError(f"floor {self.level}: opening on wall {o.wall}, the contour has {len(self.contour)}")
        return self


class Roof(SpecPart):
    parapet_h_m: NonNegative


class Spec(SpecPart):
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)+$")
    spec_version: Literal["0.1"] = "0.1"
    profile: Literal["npm_min", "mid"]
    frame: Frame
    levels: list[Level] = Field(min_length=2)
    floors: list[Floor] = Field(min_length=1)
    roof: Roof | None = None
    attachments: list[dict] = []
    opening_depth_default_m: NonNegative = 0.2

    @model_validator(mode="after")
    def consistent(self):
        names = [lv.name for lv in self.levels]
        if len(set(names)) != len(names):
            raise ValueError("level names must be unique")
        if [lv.elev_m for lv in self.levels] != sorted(lv.elev_m for lv in self.levels):
            raise ValueError("levels must be sorted by elevation")
        for f in self.floors:
            for ref in (f.level, f.typical_of, f.repeat_to):
                if ref is not None and ref not in names:
                    raise ValueError(f"floor refers to unknown level {ref}")
        full = {f.level for f in self.floors if f.contour is not None}
        owner = {}
        for f in self.floors:
            first = last = names.index(f.level)
            if f.typical_of is not None:
                if f.typical_of not in full or names.index(f.typical_of) >= first:
                    raise ValueError(f"floor {f.level}: typical_of must be a full floor below it")
                if f.openings:
                    raise ValueError(f"floor {f.level}: a typical entry carries no openings of its own")
                last = names.index(f.repeat_to) if f.repeat_to is not None else first
                if last < first:
                    raise ValueError(f"floor {f.level}: repeat_to is below the floor")
            if last >= len(names) - 1:
                raise ValueError(f"floor {f.level}: floors stop below the top level {names[-1]}")
            for i in range(first, last + 1):
                if i in owner:
                    raise ValueError(f"level {names[i]} is given twice ({owner[i]} and {f.level})")
                owner[i] = f.level
        return self

    def expanded_floors(self):
        """Every floor in full, typical runs copied from their template (round trip of #8)."""
        from dt_ai.spec.floors import expand
        names = [lv.name for lv in self.levels]
        return [Floor.model_validate(f) for f in expand([f.model_dump() for f in self.floors], names)]

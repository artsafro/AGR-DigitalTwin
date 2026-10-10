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
    # the hole in the wall with its frame (spec v0.3, user decision 2026-10-08, #36): position along
    # the wall, sill from the floor's level, width and height of the rough opening
    wall: int = Field(ge=0)
    x_m: NonNegative
    sill_m: Finite
    w_m: Positive
    h_m: Positive
    # only an exception to the spec's opening_depth_default_m (#36); None = the default
    depth_m: NonNegative | None = None
    # the glass in it, when there is glass: extent of its panes (#36)
    glass_w: Positive | None = None
    glass_h: Positive | None = None
    window_type: int | None = None
    # door: a recess from the floor >= 1.9 m high, 0.7-3 m wide (user decision 2026-10-08, #31)
    # grille: a vent grille, position and size only (user decision 2026-10-09; pattern vent-grille)
    kind: Literal["window", "door", "grille"] | None = None
    # panes of one frame (gap <= 0.15 m) grouped into this opening: a curtain wall is one opening (#31)
    panes: int | None = Field(default=None, ge=1)
    # an opening across a level is one record (spec v0.2, user decision 2026-10-08): kept by the
    # floor of level_from, sill from that level, height up to level_to's floor and above
    level_from: str | None = None
    level_to: str | None = None
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


class Terrace(SpecPart):
    """A ledge at a floor step used as a terrace, with a parapet (upstand) along its outer edges
    (spec v0.4, pattern terrace, user decision 2026-10-10). The height is measured from the level."""
    level: str
    parapet_h_m: Positive


class Spec(SpecPart):
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)+$")
    # 0.2: openings across levels (level_from / level_to); 0.3: opening = hole with frame, glass_w /
    # glass_h, depth_m only as an exception to opening_depth_default_m (#36)
    # 0.4: terraces with a parapet at floor steps (pattern terrace, user decision 2026-10-10)
    spec_version: Literal["0.1", "0.2", "0.3", "0.4"] = "0.3"
    profile: Literal["npm_min", "mid"]
    frame: Frame
    levels: list[Level] = Field(min_length=2)
    floors: list[Floor] = Field(min_length=1)
    roof: Roof | None = None
    terraces: list[Terrace] = []
    attachments: list[dict] = []
    opening_depth_default_m: NonNegative = 0.2

    @model_validator(mode="after")
    def consistent(self):
        names = [lv.name for lv in self.levels]
        if self.terraces and self.spec_version != "0.4":
            raise ValueError("terraces need spec_version 0.4")
        seen = set()
        for tr in self.terraces:
            if tr.level not in names[1:-1]:
                raise ValueError(f"terrace at {tr.level}: a terrace lies at a level between the first and the roof")
            if tr.level in seen:
                raise ValueError(f"terrace at {tr.level} is given twice")
            seen.add(tr.level)
        if len(set(names)) != len(names):
            raise ValueError("level names must be unique")
        if [lv.elev_m for lv in self.levels] != sorted(lv.elev_m for lv in self.levels):
            raise ValueError("levels must be sorted by elevation")
        for f in self.floors:
            for ref in (f.level, f.typical_of, f.repeat_to):
                if ref is not None and ref not in names:
                    raise ValueError(f"floor refers to unknown level {ref}")
        for f in self.floors:
            for o in f.openings:
                if (o.level_from is None) != (o.level_to is None):
                    raise ValueError(f"floor {f.level}: an opening across levels needs level_from and level_to")
                if o.level_to is not None and (o.level_from != f.level or o.level_to not in names
                                               or names.index(o.level_to) <= names.index(f.level)):
                    raise ValueError(f"floor {f.level}: level_from must be the floor and level_to a level above it")
                if o.level_to is not None and self.spec_version == "0.1":
                    raise ValueError("openings across levels need spec_version 0.2")
                if self.spec_version in ("0.1", "0.2") and o.depth_m is None:
                    raise ValueError(f"spec {self.spec_version}: every opening has depth_m (optional from 0.3)")
                if (o.glass_w is not None or o.glass_h is not None) and self.spec_version not in ("0.3", "0.4"):
                    raise ValueError("glass_w / glass_h need spec_version 0.3")
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

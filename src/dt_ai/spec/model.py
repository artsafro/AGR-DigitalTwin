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
    # spec v0.6 (rule 4, user 2026-10-12): measured from the source's closed parapet section, else the object's
    # parapet_thickness_default_m (the extractor report marks it); None = neither, the build input decides
    parapet_thickness_m: Positive | None = None


class RoofStructure(SpecPart):
    """A structure on the roof (spec v0.7, pattern roof-screen-enclosure, user 2026-10-13): kind "screen" - a
    screen enclosure round roof equipment, its outer outline in plan and its top. npm_min builds it as planes
    (walls on the outline from the roof level to z_top and a top plane, no bottom, no thickness), roof ids; it
    is part of the body's silhouette, not an attachment."""
    kind: Literal["screen"]
    outline: list[list[float]] = Field(min_length=3)
    z_top_m: float

    @model_validator(mode="after")
    def plan(self):
        if any(len(p) != 2 for p in self.outline):
            raise ValueError("roof structure outline: [x, y] points")
        import shapely
        poly = shapely.Polygon(self.outline)
        if not poly.is_valid or poly.area <= 0:
            raise ValueError("roof structure outline: a simple polygon with an area (review 1 of #92)")
        return self


class Terrace(SpecPart):
    """A ledge at a floor step used as a terrace, with a parapet (upstand) along its outer edges
    (spec v0.4, pattern terrace, user decision 2026-10-10). The height is measured from the level."""
    level: str
    parapet_h_m: Positive


OPENING_DEPTH_DEFAULT_M = 0.4   # OD1 (user 2026-10-11): one opening depth per building unless the source gives one
DECOR_TEXTURE_M = 0.10   # pattern facade-decor-inset (user 2026-10-11): projection <= this is texture, boundary included


class Decor(SpecPart):
    """One facade decor element (spec v0.5, pattern facade-decor-inset, user decisions 2026-10-11/12): a
    simple solid, pieces of a split element merged. Wall-bound kinds by shape in the wall plane: band (width
    >= 3 x height), strip (height >= 3 x width: pilaster, lesene), panel (spandrel and the rest); a column
    stands free of the walls. Position from the floor of `level`: along `wall` of its contour (x_m, w_m) and
    from the level (z_m, h_m); a column by its footprint [x0, y0, x1, y1] in object coordinates."""
    kind: Literal["band", "strip", "panel", "column"]
    level: str
    wall: int | None = Field(default=None, ge=0)
    x_m: Finite | None = None
    w_m: Positive
    z_m: Finite
    h_m: Positive
    projection_m: Positive | None = None
    footprint: list[Finite] | None = Field(default=None, min_length=4, max_length=4)
    # projection <= DECOR_TEXTURE_M: texture on the wall, nothing built
    texture: bool = False
    # material id from the source when all its faces carry one decor id: metal 16-20 or plaster / stone / tile
    # 26-30, by the element's material (user 2026-10-12)
    material_id: int | None = None
    # source pieces merged into it (same cross-section, one axis, seams <= plate_gap_m x 12)
    pieces: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def placed(self):
        if self.kind == "column":
            if self.footprint is None or self.wall is not None or self.x_m is not None:
                raise ValueError("a column has a footprint and no wall")
            if self.footprint[0] >= self.footprint[2] or self.footprint[1] >= self.footprint[3]:
                raise ValueError("a column footprint is [x0, y0, x1, y1] with x0 < x1, y0 < y1")
            if self.texture:
                raise ValueError("a free-standing column is never texture")
        else:
            if self.wall is None or self.x_m is None or self.projection_m is None or self.footprint is not None:
                raise ValueError(f"a {self.kind} has wall, x_m and projection_m and no footprint")
            if self.texture != (self.projection_m <= DECOR_TEXTURE_M):
                raise ValueError(f"texture is projection <= {DECOR_TEXTURE_M} m (boundary included)")
        return self


class Spec(SpecPart):
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)+$")
    # 0.2: openings across levels (level_from / level_to); 0.3: opening = hole with frame, glass_w /
    # glass_h, depth_m only as an exception to opening_depth_default_m (#36)
    # 0.4: terraces with a parapet at floor steps (pattern terrace, user decision 2026-10-10)
    # 0.5: facade decor (pattern facade-decor-inset, user decisions 2026-10-11/12)
    # 0.6: roof.parapet_thickness_m (rule 4, user 2026-10-12)
    # 0.7: roof_structures (pattern roof-screen-enclosure, user 2026-10-13)
    spec_version: Literal["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7"] = "0.3"
    profile: Literal["npm_min", "mid"]
    frame: Frame
    levels: list[Level] = Field(min_length=2)
    floors: list[Floor] = Field(min_length=1)
    roof: Roof | None = None
    terraces: list[Terrace] = []
    attachments: list[dict] = []
    roof_structures: list[RoofStructure] = []
    decor: list[Decor] = []
    opening_depth_default_m: NonNegative = OPENING_DEPTH_DEFAULT_M
    # pattern roof-inset-plane (user 2026-10-10): every slab is a separate plate plate_gap_m above its level
    # that overlaps its hole by plate_overlap_m; building parameters, the etalons' 5 mm / 20 mm by default
    plate_gap_m: Positive = 0.005
    plate_overlap_m: Positive = 0.02
    # the building's weld (user 2026-10-13): vertices and cut lines closer than this (inclusive) are one - in the
    # engine's grid, the checkers' readback and the extractor's contour points; how the user welds by hand
    weld_m: Positive = 0.003

    @model_validator(mode="after")
    def consistent(self):
        names = [lv.name for lv in self.levels]
        # a gap is never welded: every gap of the spec (the inset plate's, the decor seams' plate_gap_m x 12)
        # lies beyond weld_m (user 2026-10-13)
        if self.plate_gap_m <= self.weld_m:
            raise ValueError(f"plate_gap_m {self.plate_gap_m} m must be larger than weld_m {self.weld_m} m")
        if self.terraces and self.spec_version not in ("0.4", "0.5", "0.6", "0.7"):
            raise ValueError("terraces need spec_version 0.4")
        if self.decor and self.spec_version not in ("0.5", "0.6", "0.7"):
            raise ValueError("decor needs spec_version 0.5")
        if self.roof_structures and self.spec_version != "0.7":
            raise ValueError("roof_structures need spec_version 0.7")
        for rs in self.roof_structures:
            if rs.z_top_m <= self.levels[-1].elev_m:
                raise ValueError(f"roof structure: top {rs.z_top_m} m is not above the roof level")
        if self.roof is not None and self.roof.parapet_thickness_m is not None and self.spec_version not in ("0.6", "0.7"):
            raise ValueError("roof.parapet_thickness_m needs spec_version 0.6")
        for d in self.decor:
            if d.level not in names[:-1]:
                raise ValueError(f"decor at {d.level}: a decor element stands on a floor level")
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
                if (o.glass_w is not None or o.glass_h is not None) and self.spec_version not in ("0.3", "0.4", "0.5", "0.6", "0.7"):
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
        if self.decor:
            sides = {f.level: len(f.contour) for f in self.expanded_floors()}
            for d in self.decor:
                if d.level not in sides:
                    raise ValueError(f"decor at {d.level}: no floor at that level")
                if d.wall is not None and d.wall >= sides[d.level]:
                    raise ValueError(f"decor at {d.level}: wall {d.wall}, the contour has {sides[d.level]}")
        return self

    def expanded_floors(self):
        """Every floor in full, typical runs copied from their template (round trip of #8)."""
        from dt_ai.spec.floors import expand
        names = [lv.name for lv in self.levels]
        return [Floor.model_validate(f) for f in expand([f.model_dump() for f in self.floors], names)]

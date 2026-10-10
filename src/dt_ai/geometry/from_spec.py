"""Build the exterior mesh of a building from its spec (docs/HARNESS_PLAN.md §9): the only engine.

Input: a `Spec` (written by an extractor) and the build inputs the spec does not carry — the
parapet wall thickness and the material IDs of the object (`jobs/<object>/materials.json`, ADR 0001).
Nothing else is assumed; anything this step cannot build is an error, never a guess.

What it builds (patterns wall-from-contour, opening-plane, typical-floor-repeat, parapet):
- one outer wall surface per contour edge, from the bottom level to the parapet top; no Shell
  (wall thickness is open, conflict C23);
- every window / door / untyped opening as a hole with reveals and a plane closing them, ID by the
  opening's own `material_id`, else its window type, else the object's default opening ID (never
  under `plane_conflict`). Seating by profile (conflict C24, final user decision 2026-10-10): `npm_min`
  at the full opening depth (`depth_m` or `opening_depth_default_m`) — the plane is the back polygon
  of the opening's extrusion; `mid` at half of it, where the detailed window is built from the plane. The reveals end at the plane: their part behind an opaque NPM plane is hidden and
  is not built (docs/domain/geometry.md, hidden parts of reveals), and a reveal running past the
  plane would leave an edge of three faces. Grilles stay texture (`vent-grille`);
- the roof plane at the top input level inside the parapet, parapet inner walls and cap;
- a contour per floor (pattern floor-step): walls of each floor by its own contour, and at each
  level line a ledge facing up (roof ID) where the floor below reaches out and a soffit facing down
  (facade ID, user 2026-10-10) where the floor above overhangs.

Topology: quads only, welded, no T-junctions. Wall cuts run at every contour vertex and opening
edge, Z cuts at every level, sill, head, roof and parapet top, and cuts are propagated through the
roof and cap until every shared edge splits the same way (docs/domain/geometry.md, BODY quad
layout). The shape comes only from the contour polygons. Supported now: axis-parallel walls, no
rounded corners, openings inside one wall that touch neither its
ends, nor each other, nor the roof level, no attachments; anything else is a BuildError.

Output: a mesh dump in the format of tools/source/measure_spec_blender.py (one mesh `body` with
vertices, triangles, material ids, polygon sizes, plus LEVEL_<name> helpers), so the benchmark
checkers read the built model exactly as they read an etalon; `polygons` (the quads) let
tools/export/export_mesh_blender.py write it as a Blender scene and FBX.
"""
from dataclasses import dataclass

import numpy as np
import shapely
from shapely.geometry import Point, Polygon
from shapely.geometry.polygon import orient

from dt_ai.spec.model import Spec

KEY_M = 1e-6          # vertices on one 1 µm grid are one vertex
BUILT_KINDS = ("window", "door", None)
SEAT_SHARE = {"npm_min": 1.0, "mid": 0.5}   # plane seat as a share of the opening depth (C24 final, user 2026-10-10)


class BuildError(ValueError):
    pass


@dataclass
class BuildInputs:
    parapet_thickness_m: float
    facade_id: int
    reveal_id: int
    roof_id: int
    opening_id: int                       # default plane ID when the opening has none of its own
    opening_ids_by_type: dict | None = None  # window_type -> plane ID

    @classmethod
    def from_object(cls, obj_cfg: dict) -> "BuildInputs":
        """The `build` block of object.json: {"parapet_thickness_m", "ids": {"facade", "reveal", "roof",
        "opening"}, "opening_ids_by_type"?}. Missing values are an error, never a default."""
        b = obj_cfg.get("build")
        if not b:
            raise BuildError(f"object {obj_cfg.get('id', '?')}: object.json has no build block (parapet thickness, IDs)")
        try:
            ids = b["ids"]
            by_type = {int(k): int(v) for k, v in (b.get("opening_ids_by_type") or {}).items()}
            return cls(float(b["parapet_thickness_m"]), int(ids["facade"]), int(ids["reveal"]), int(ids["roof"]),
                       int(ids["opening"]), by_type or None)
        except (KeyError, TypeError, ValueError) as exc:
            raise BuildError(f"object.json build block: {exc!r}") from exc


class _Mesh:
    def __init__(self):
        self.index, self.vertices, self.faces = {}, [], []

    def vertex(self, p):
        key = tuple(int(round(c / KEY_M)) for c in p)
        if key not in self.index:
            self.index[key] = len(self.vertices)
            self.vertices.append([float(c) for c in p])
        return self.index[key]

    def quad(self, pts, mid, facing):
        """Quad with its normal turned to `facing` (outward for walls, up for roofs)."""
        pts = [np.asarray(p, float) for p in pts]
        n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        if float(n @ np.asarray(facing, float)) < 0:
            pts = pts[::-1]
        self.faces.append(([self.vertex(p) for p in pts], mid))

    def dump(self, levels):
        tris, mids = [], []
        for ids, mid in self.faces:
            tris += [[ids[0], ids[1], ids[2]], [ids[0], ids[2], ids[3]]]
            mids += [mid, mid]
        body = {"name": "body", "vertices": self.vertices, "triangles": tris, "material_ids": mids,
                "polygon_sizes": [4] * len(self.faces), "polygons": [ids for ids, _ in self.faces]}
        return {"source": "from_spec", "units": "m", "meshes": [body],
                "helpers": [{"name": f"LEVEL_{lv.name}", "location": [0.0, 0.0, lv.elev_m]} for lv in levels]}


def _cuts(values, lo, hi):
    return sorted({round(v, 9) for v in [*values, lo, hi] if lo - KEY_M <= v <= hi + KEY_M})


def _contours(spec: Spec):
    """Floors in level order and their contours (pattern floor-step: a contour per floor)."""
    names = [lv.name for lv in spec.levels]
    floors = sorted(spec.expanded_floors(), key=lambda f: names.index(f.level))   # records may come in any order
    if any(len(p) == 3 for f in floors for p in f.contour):
        raise BuildError("rounded corners are not built yet (pattern non-90-corner)")
    if [f.level for f in floors] != names[:-1]:
        raise BuildError(f"floors {[f.level for f in floors]} must cover every level below the top: {names[:-1]}")
    if spec.attachments:
        raise BuildError("attachments are not built yet")
    templates = {f.typical_of for f in spec.floors if f.typical_of is not None}
    for f in spec.floors:
        if f.level in templates and any(o.level_to is not None for o in f.openings):
            raise BuildError(f"floor {f.level} repeats an opening across levels: ask the user before copying it "
                             "up the run (typical-floor-repeat, user decision 2026-10-09)")
    contours = []
    for f in floors:
        pts = np.asarray(f.contour, float)
        for i in range(len(pts)):
            d = pts[(i + 1) % len(pts)] - pts[i]
            if min(abs(d[0]), abs(d[1])) > KEY_M:
                raise BuildError(f"floor {f.level} wall {i} is not axis-parallel; corners other than 90° are not "
                                 "built yet (non-90-corner)")
        if Polygon(pts).exterior.is_ccw is False:
            raise BuildError(f"floor {f.level}: contour must be counter-clockwise (spec contract)")
        contours.append(pts)
    return floors, contours


def _openings(spec, floors, contours, inputs):
    """Openings with their wall line in plan (start point, direction, length), so a hole is cut in
    every wall on that line it crosses: the wall of its own floor and, across a level, the next."""
    elev = {lv.name: lv.elev_m for lv in spec.levels}
    out = []
    for f, pts in zip(floors, contours):
        for o in f.openings:
            if o.kind not in BUILT_KINDS:
                continue
            if o.plane_conflict:
                raise BuildError(f"floor {f.level} wall {o.wall} x {o.x_m}: plane_conflict, the plane ID is the user's")
            if o.material_id is not None:
                mid = o.material_id
            elif o.window_type is not None and inputs.opening_ids_by_type and o.window_type in inputs.opening_ids_by_type:
                mid = inputs.opening_ids_by_type[o.window_type]
            else:
                mid = inputs.opening_id
            z0 = elev[f.level] + o.sill_m
            depth = (spec.opening_depth_default_m if o.depth_m is None else o.depth_m) * SEAT_SHARE[spec.profile]
            if depth <= KEY_M:
                raise BuildError(f"floor {f.level} wall {o.wall} x {o.x_m}: depth 0 has no reveal to build")
            a, b = pts[o.wall], pts[(o.wall + 1) % len(pts)]
            length = float(np.linalg.norm(b - a))
            out.append({"wall": o.wall, "level": f.level, "a": a, "u": (b - a) / length, "length": length,
                        "s0": o.x_m, "s1": o.x_m + o.w_m, "z0": z0, "z1": z0 + o.h_m, "id": mid,
                        "depth": depth, "where": f"floor {f.level} wall {o.wall} x {o.x_m}"})
    for i, a in enumerate(out):
        for b in out[i + 1:]:
            span = _on_line(b, a["a"], a["u"])              # b on a's wall line, in a's coordinates
            if (span is not None and a["s0"] <= span[1] + KEY_M and span[0] <= a["s1"] + KEY_M
                    and a["z0"] <= b["z1"] + KEY_M and b["z0"] <= a["z1"] + KEY_M):   # any floors
                raise BuildError(f"openings touch or overlap ({a['where']}, {b['where']}); not built yet")
    return out


def _on_line(o, a, u):
    """The opening's span in the coordinates of a wall starting at a with direction u, or None when
    the opening is not on that wall's line."""
    if float(np.dot(o["u"], u)) < 1 - 1e-9:
        return None
    rel = o["a"] - a
    if abs(rel[0] * u[1] - rel[1] * u[0]) > KEY_M:
        return None
    off = float(np.dot(rel, u))
    return off + o["s0"], off + o["s1"]


def _check_steps(floors, polys):
    """Two floors must meet over area only: floors touching along an edge or at a corner (a floor beside
    the one below, walls back to back), alone or next to an overlap, are not built (reviews of PR #55).
    Several separate overlap areas (opposite U shapes) are fine."""
    for k in range(len(polys) - 1):
        meet = polys[k].intersection(polys[k + 1])
        parts = list(shapely.get_parts(meet))
        if meet.is_empty or meet.area <= KEY_M or any(p.geom_type != "Polygon" for p in parts):
            raise BuildError(f"floors {floors[k].level} and {floors[k + 1].level} do not meet over area only "
                             f"({meet.geom_type}); edge- or corner-only contact is not built yet (floor-step)")


def _check_openings_on_walls(openings, contours, elev, top):
    """Every wall an opening crosses must hold the whole opening span strictly inside it (Codex review 1
    of PR #55): a frame across a level onto a shorter upper wall is a corner opening, not built yet."""
    for o in openings:
        for k, pts in enumerate(contours):
            z_lo, z_hi = elev[k], (elev[k + 1] if k < len(contours) - 1 else top)
            if min(o["z1"], z_hi) - max(o["z0"], z_lo) <= KEY_M:
                continue
            held = False
            for w in range(len(pts)):
                a, b = pts[w], pts[(w + 1) % len(pts)]
                length = float(np.linalg.norm(b - a))
                span = _on_line(o, a, (b - a) / length)
                if span is not None and span[0] > KEY_M and span[1] < length - KEY_M:
                    held = True
                    break
            if not held:
                raise BuildError(f"{o['where']}: no wall of floor {k} holds the whole opening between "
                                 f"{max(o['z0'], z_lo):.3f} and {min(o['z1'], z_hi):.3f} m; not built yet")


def build(spec: Spec, inputs: BuildInputs) -> dict:
    """Mesh dump of the spec's exterior (see module docstring)."""
    floors, contours = _contours(spec)
    openings = _openings(spec, floors, contours, inputs)
    elev = [lv.elev_m for lv in spec.levels]
    bottom, roof = elev[0], elev[-1]
    parapet = spec.roof.parapet_h_m if spec.roof else 0.0
    top = round(roof + parapet, 9)
    t = inputs.parapet_thickness_m if parapet > 0 else 0.0
    polys = [orient(Polygon(pts), sign=1.0) for pts in contours]
    _check_steps(floors, polys)
    outer = polys[-1]
    inner = outer.buffer(-t, join_style="mitre") if t > 0 else outer
    if t > 0 and (inner.geom_type != "Polygon" or inner.is_empty):
        raise BuildError("parapet thickness leaves no single roof polygon")
    inner = orient(inner, sign=1.0)
    in_pts = np.asarray(inner.exterior.coords)[:-1]

    # global cut lines: every contour (all floors) / inset vertex and opening edge, propagated through
    # the roof, the cap and the faces at the floor steps
    xs = set(in_pts[:, 0]) | {float(x) for pts in contours for x in pts[:, 0]}
    ys = set(in_pts[:, 1]) | {float(y) for pts in contours for y in pts[:, 1]}
    for o in openings:
        for s_ in (o["s0"], o["s1"]):
            if s_ <= KEY_M or s_ >= o["length"] - KEY_M:
                raise BuildError(f"{o['where']}: the opening reaches the wall end; corner openings are not built yet")
            x, y = o["a"] + o["u"] * s_
            (xs if abs(o["u"][0]) > 0.5 else ys).add(x if abs(o["u"][0]) > 0.5 else y)
        if o["z1"] >= roof - KEY_M or o["z0"] < bottom - KEY_M:
            raise BuildError(f"{o['where']}: the opening must lie between the bottom level and below the roof level")
    _check_openings_on_walls(openings, contours, elev, top)
    xs, ys = sorted(round(v, 9) for v in xs), sorted(round(v, 9) for v in ys)
    zs_all = _cuts(elev + [top] + [z for o in openings for z in (o["z0"], o["z1"])], bottom, top)

    mesh = _Mesh()
    for k, pts in enumerate(contours):
        z_lo, z_hi = elev[k], (elev[k + 1] if k < len(contours) - 1 else top)
        zs = [z for z in zs_all if z_lo - KEY_M <= z <= z_hi + KEY_M]
        n = len(pts)
        for w in range(n):
            a, b = pts[w], pts[(w + 1) % n]
            length = float(np.linalg.norm(b - a))
            u = (b - a) / length
            out_n = np.array([u[1], -u[0], 0.0])
            along = xs if abs(u[0]) > 0.5 else ys
            coord = 0 if abs(u[0]) > 0.5 else 1
            ss = sorted({round(abs(v - a[coord]), 9) for v in along
                         if min(a[coord], b[coord]) - KEY_M <= v <= max(a[coord], b[coord]) + KEY_M})
            P = lambda s, z, a=a, u=u: [*(a + u * s), z]  # noqa: E731
            holes = [(o, span) for o in openings if (span := _on_line(o, a, u)) is not None]

            def hole_at(s, z, holes=holes):
                return next((o for o, (h0, h1) in holes if h0 < s < h1 and o["z0"] < z < o["z1"]), None)

            eps = 1e-4
            for s0, s1 in zip(ss, ss[1:]):
                for z0, z1 in zip(zs, zs[1:]):
                    sm, zm = (s0 + s1) / 2, (z0 + z1) / 2
                    o = hole_at(sm, zm)
                    if o is None:
                        mesh.quad([P(s0, z0), P(s1, z0), P(s1, z1), P(s0, z1)], inputs.facade_id, out_n)
                        continue
                    d = o["depth"]
                    Q = lambda s, z, a=a, u=u, d=d, out_n=out_n: [*(a + u * s - out_n[:2] * d), z]  # noqa: E731
                    mesh.quad([Q(s0, z0), Q(s1, z0), Q(s1, z1), Q(s0, z1)], o["id"], out_n)
                    # a reveal on each side of the cell that borders the wall, facing into the opening
                    for (sa, za), (sb, zb), outside, face in (
                            ((s0, z0), (s1, z0), (sm, z0 - eps), [0, 0, 1]),
                            ((s0, z1), (s1, z1), (sm, z1 + eps), [0, 0, -1]),
                            ((s0, z0), (s0, z1), (s0 - eps, zm), [u[0], u[1], 0]),
                            ((s1, z0), (s1, z1), (s1 + eps, zm), [-u[0], -u[1], 0])):
                        if hole_at(*outside) is o:
                            continue
                        mesh.quad([P(sa, za), P(sb, zb), Q(sb, zb), Q(sa, za)], inputs.reveal_id, face)

    if t > 0:
        # parapet inner walls along the inset contour, roof to top
        m = len(in_pts)
        for w in range(m):
            a, b = in_pts[w], in_pts[(w + 1) % m]
            length = float(np.linalg.norm(b - a))
            u = (b - a) / length
            coord = 0 if abs(u[0]) > 0.5 else 1
            along = xs if coord == 0 else ys
            ss = sorted({round(abs(v - a[coord]), 9) for v in along
                         if min(a[coord], b[coord]) - KEY_M <= v <= max(a[coord], b[coord]) + KEY_M})
            facing = np.array([-u[1], u[0], 0.0])           # into the roof
            for s0, s1 in zip(ss, ss[1:]):
                p0, p1 = a + u * s0, a + u * s1
                mesh.quad([[*p0, roof], [*p1, roof], [*p1, top], [*p0, top]], inputs.roof_id, facing)
    # horizontal faces on the cut grid: the roof plane (inside the inset) and cap (between contour and
    # inset); at each floor step (pattern floor-step) a ledge facing up where the floor below reaches out
    # (roof ID) and a soffit facing down where the floor above overhangs (facade ID, user 2026-10-10)
    ring = outer.difference(inner) if t > 0 else None
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            c = Point((x0 + x1) / 2, (y0 + y1) / 2)
            cell = lambda z: [[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]]  # noqa: E731
            if inner.contains(c):
                mesh.quad(cell(roof), inputs.roof_id, [0, 0, 1])
            elif ring is not None and ring.contains(c):
                mesh.quad(cell(top), inputs.roof_id, [0, 0, 1])
            for k in range(len(polys) - 1):
                below, above = polys[k].contains(c), polys[k + 1].contains(c)
                if below and not above:
                    mesh.quad(cell(elev[k + 1]), inputs.roof_id, [0, 0, 1])
                elif above and not below:
                    mesh.quad(cell(elev[k + 1]), inputs.facade_id, [0, 0, -1])
    return mesh.dump(spec.levels)

"""Build the exterior mesh of a building from its spec (docs/HARNESS_PLAN.md §9): the only engine.

Input: a `Spec` (written by an extractor) and the build inputs the spec does not carry — the
parapet wall thickness and the material IDs of the object (`jobs/<object>/materials.json`, ADR 0001).
Nothing else is assumed; anything this step cannot build is an error, never a guess.

What it builds (patterns wall-from-contour, opening-plane, typical-floor-repeat, parapet):
- one outer wall surface per contour edge, from the bottom level to the parapet top; no Shell
  (wall thickness is open, conflict C23);
- every window / door / untyped opening as a hole with reveals and a plane closing them, ID by the
  opening's own `material_id`, else its window type, else the object's default opening ID (never
  under `plane_conflict`). Seating is conflict C24 (open), so it is a required input: `spec_depth`
  puts the plane at the opening depth (`depth_m` or `opening_depth_default_m`), `half_depth` at
  half of it. Grilles stay texture (`vent-grille`);
- the roof plane at the top input level inside the parapet, parapet inner walls and cap.

Topology: quads only, welded, no T-junctions. Wall cuts run at every contour vertex and opening
edge, Z cuts at every level, sill, head, roof and parapet top, and cuts are propagated through the
roof and cap until every shared edge splits the same way (docs/domain/geometry.md, BODY quad
layout). The shape comes only from the contour polygon. Supported now: one contour for every
floor, axis-parallel walls, no rounded corners, openings inside one wall that touch neither its
ends, nor each other, nor the roof level, no attachments; anything else is a BuildError.

Output: a mesh dump in the format of tools/source/measure_spec_blender.py (one mesh `body` with
vertices, triangles, material ids, polygon sizes, plus LEVEL_<name> helpers), so the benchmark
checkers read the built model exactly as they read an etalon.
"""
from dataclasses import dataclass

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.geometry.polygon import orient

from dt_ai.spec.model import Spec

KEY_M = 1e-6          # vertices on one 1 µm grid are one vertex
BUILT_KINDS = ("window", "door", None)
SEATS = {"spec_depth": 1.0, "half_depth": 0.5}   # conflict C24 is open: the caller chooses


class BuildError(ValueError):
    pass


@dataclass
class BuildInputs:
    parapet_thickness_m: float
    facade_id: int
    reveal_id: int
    roof_id: int
    opening_id: int                       # default plane ID when the opening has none of its own
    plane_seat: str                       # "spec_depth" or "half_depth" (C24 open, no default)
    opening_ids_by_type: dict | None = None  # window_type -> plane ID


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
                "polygon_sizes": [4] * len(self.faces)}
        return {"source": "from_spec", "units": "m", "meshes": [body],
                "helpers": [{"name": f"LEVEL_{lv.name}", "location": [0.0, 0.0, lv.elev_m]} for lv in levels]}


def _cuts(values, lo, hi):
    return sorted({round(v, 9) for v in [*values, lo, hi] if lo - KEY_M <= v <= hi + KEY_M})


def _contour(spec: Spec):
    floors = spec.expanded_floors()
    contours = {tuple(map(tuple, (p[:2] for p in f.contour))) for f in floors}
    if any(len(p) == 3 for f in floors for p in f.contour):
        raise BuildError("rounded corners are not built yet (pattern non-90-corner)")
    if len(contours) != 1:
        raise BuildError("floors have different contours; steps between floors are not built yet (contour-niche)")
    names = [lv.name for lv in spec.levels]
    if [f.level for f in floors] != names[:-1]:
        raise BuildError(f"floors {[f.level for f in floors]} must cover every level below the top: {names[:-1]}")
    if spec.attachments:
        raise BuildError("attachments are not built yet")
    templates = {f.typical_of for f in spec.floors if f.typical_of is not None}
    for f in spec.floors:
        if f.level in templates and any(o.level_to is not None for o in f.openings):
            raise BuildError(f"floor {f.level} repeats an opening across levels: ask the user before copying it "
                             "up the run (typical-floor-repeat, user decision 2026-10-09)")
    pts = np.asarray(floors[0].contour, float)
    for i in range(len(pts)):
        d = pts[(i + 1) % len(pts)] - pts[i]
        if min(abs(d[0]), abs(d[1])) > KEY_M:
            raise BuildError(f"wall {i} is not axis-parallel; corners other than 90° are not built yet (non-90-corner)")
    if Polygon(pts).exterior.is_ccw is False:
        raise BuildError("contour must be counter-clockwise (spec contract)")
    return pts, floors


def _openings(spec, floors, inputs):
    elev = {lv.name: lv.elev_m for lv in spec.levels}
    out = []
    for f in floors:
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
            depth = (spec.opening_depth_default_m if o.depth_m is None else o.depth_m) * SEATS[inputs.plane_seat]
            if depth <= KEY_M:
                raise BuildError(f"floor {f.level} wall {o.wall} x {o.x_m}: depth 0 has no reveal to build")
            out.append({"wall": o.wall, "s0": o.x_m, "s1": o.x_m + o.w_m, "z0": z0, "z1": z0 + o.h_m, "id": mid,
                        "depth": depth, "where": f"floor {f.level} wall {o.wall} x {o.x_m}"})
    for i, a in enumerate(out):
        for b in out[i + 1:]:
            if (a["wall"] == b["wall"] and a["s0"] <= b["s1"] + KEY_M and b["s0"] <= a["s1"] + KEY_M
                    and a["z0"] <= b["z1"] + KEY_M and b["z0"] <= a["z1"] + KEY_M):
                raise BuildError(f"openings touch or overlap ({a['where']}, {b['where']}); not built yet")
    return out


def build(spec: Spec, inputs: BuildInputs) -> dict:
    """Mesh dump of the spec's exterior (see module docstring)."""
    if inputs.plane_seat not in SEATS:
        raise BuildError(f"plane_seat must be one of {sorted(SEATS)} (conflict C24 is open)")
    pts, floors = _contour(spec)
    openings = _openings(spec, floors, inputs)
    bottom, roof = spec.levels[0].elev_m, spec.levels[-1].elev_m
    parapet = spec.roof.parapet_h_m if spec.roof else 0.0
    top = round(roof + parapet, 9)
    t = inputs.parapet_thickness_m if parapet > 0 else 0.0
    outer = orient(Polygon(pts), sign=1.0)
    inner = outer.buffer(-t, join_style="mitre") if t > 0 else outer
    if t > 0 and (inner.geom_type != "Polygon" or inner.is_empty):
        raise BuildError("parapet thickness leaves no single roof polygon")
    inner = orient(inner, sign=1.0)
    in_pts = np.asarray(inner.exterior.coords)[:-1]
    n = len(pts)

    # global cut lines: every contour / inset vertex and opening edge, propagated through the roof
    xs, ys = set(pts[:, 0]) | set(in_pts[:, 0]), set(pts[:, 1]) | set(in_pts[:, 1])
    for o in openings:
        a, b = pts[o["wall"]], pts[(o["wall"] + 1) % n]
        u = (b - a) / np.linalg.norm(b - a)
        for s in (o["s0"], o["s1"]):
            if s <= KEY_M or s >= np.linalg.norm(b - a) - KEY_M:
                raise BuildError(f"{o['where']}: the opening reaches the wall end; corner openings are not built yet")
            x, y = a + u * s
            (xs if abs(u[0]) > 0.5 else ys).add(x if abs(u[0]) > 0.5 else y)
    xs, ys = sorted(round(v, 9) for v in xs), sorted(round(v, 9) for v in ys)
    zs = _cuts([lv.elev_m for lv in spec.levels] + [top] + [z for o in openings for z in (o["z0"], o["z1"])], bottom, top)
    for o in openings:
        if o["z1"] >= roof - KEY_M or o["z0"] < bottom - KEY_M:
            raise BuildError(f"{o['where']}: the opening must lie between the bottom level and below the roof level")

    mesh = _Mesh()
    for w in range(n):
        a, b = pts[w], pts[(w + 1) % n]
        length = float(np.linalg.norm(b - a))
        u = (b - a) / length
        out_n = np.array([u[1], -u[0], 0.0])
        along = xs if abs(u[0]) > 0.5 else ys
        coord = 0 if abs(u[0]) > 0.5 else 1
        ss = sorted({round(abs(v - a[coord]), 9) for v in along
                     if min(a[coord], b[coord]) - KEY_M <= v <= max(a[coord], b[coord]) + KEY_M})
        P = lambda s, z: [*(a + u * s), z]  # noqa: E731
        holes = [o for o in openings if o["wall"] == w]

        def hole_at(s, z):
            return next((o for o in holes if o["s0"] < s < o["s1"] and o["z0"] < z < o["z1"]), None)

        eps = 1e-4
        for s0, s1 in zip(ss, ss[1:]):
            for z0, z1 in zip(zs, zs[1:]):
                sm, zm = (s0 + s1) / 2, (z0 + z1) / 2
                o = hole_at(sm, zm)
                if o is None:
                    mesh.quad([P(s0, z0), P(s1, z0), P(s1, z1), P(s0, z1)], inputs.facade_id, out_n)
                    continue
                d = o["depth"]
                Q = lambda s, z: [*(a + u * s - out_n[:2] * d), z]  # noqa: E731
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
    # roof plane (inside the inset) and cap (between contour and inset) on the cut grid
    ring = outer.difference(inner) if t > 0 else None
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            c = Point((x0 + x1) / 2, (y0 + y1) / 2)
            if inner.contains(c):
                z = roof
            elif ring is not None and ring.contains(c):
                z = top
            else:
                continue
            mesh.quad([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]], inputs.roof_id, [0, 0, 1])
    return mesh.dump(spec.levels)

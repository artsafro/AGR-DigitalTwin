"""Spec from a mesh dump (tools/source/measure_spec_blender.py). Pure Python; never run in Blender.

Body = connected part with the largest surface area. Level contour = walls over the full storey
height: the body section shape found at both storey ends; cuts are made once per interval between
vertex heights, so every element is seen with its exact height. Cuts through openings (open rings)
decide nothing, and a storey with no closed section is an error, not a guess. Anything not over
the full height becomes a question. Levels are input (LEVEL_<name> helpers or the object's levels from Revit), never guessed;
the roof plane must lie at the top input level. Decisions: docs/HARNESS_PLAN.md §3-§4 (2026-10-08).
"""
from collections import defaultdict
from itertools import product

import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import polygonize

from dt_ai.spec import floors as fl
from dt_ai.spec import openings as op
from dt_ai.spec.model import Spec

LEVEL_PREFIX = "LEVEL_"
SAME_CONTOUR_M = 0.005    # sections closer than this (Hausdorff) are one contour; < the 1 cm acceptance
WELD_M = 1e-4             # vertices closer than WELD_M / 2 on every axis are always welded
SIMPLIFY_M = 0.0005       # numeric noise only; kinks and arcs are decided by angle below
KINK_DEG = 5.0            # a facade kink is a turn over 5 degrees (HARNESS_PLAN §3)
ARC_TURN_MAX_DEG = 22.0   # arc tessellation turns at most this per vertex (a quarter in >= 5 chords);
                          # the circle fit and wall tangency below decide, not this gate
ARC_MIN_VERTICES = 3
ARC_MIN_TURN_DEG = 20.0
ARC_FIT_M = 0.005         # arc points and both walls must fit one circle within 5 mm + 0.5 % of r
ARC_FIT_SHARE = 0.005
EVENT_MIN_M = 0.001       # vertex heights closer than this share one interval
BIN_M = 0.05              # height bins of storey triangles, so each cut reads only nearby triangles
SHARE_TOL_M = 0.005       # a piece shares a wall when its boundary lies within 5 mm of it
PRIORITY_SHARE = 0.10     # question priority high: >= 2 levels or > 10 % of the facade length
ROOF_LEVEL_TOL_M = 0.10   # roof surfaces lie within this of the top input level (user decision 2026-10-08, #9)
ROOF_SLOPE_MAX_DEG = 10.0 # drainage slopes up to this are a flat roof; steeper roof parts are a question
ROOF_SLOPE_BAND_M = 2.0   # faces of a sloped roof surface reach this far below the input level
ROOF_STEEP_SHARE = 0.01   # steep up-facing roof area above this share of the floor stops the extractor
ROOF_PART_SLIVER_M2 = 0.05  # a separate roof part with more than this both inside and outside is a question
ROOF_SEARCH_M = 0.3       # only to name nearby surfaces in the error message
ROOF_OWN = 0.25           # share of the top floor the roof plane itself must cover (else roof or cap?)
HOLE_MIN_M2 = 0.01        # uncovered pieces of the top floor smaller than this are numeric slivers
SHAFT_UPPER = 0.85        # ... and again at this share of the top storey's height
SHAFT_WALL_SHARE = 0.9    # a roof hole is a shaft when body walls line this share of its edge at mid top storey
ROOF_CLOSED = 0.9         # share of the top floor the roof and surfaces above it must close
PARAPET_EDGE_M = 0.05     # parapet top is read only on the outer wall line of the top floor
PARAPET_SAMPLE_M = 0.25   # the roof is compared with the wall top at least this often along the outer wall line
# user decisions 2026-10-08 (#31): a recess open from the storey floor, at least DOOR_MIN_H_M high
# and DOOR_W_M wide at its mouth, is a door opening and leaves the contour (depth is no criterion);
# a bump or notch with both sizes <= RELIEF_M is relief, not a kink; the same in section: a projection or
# recess with depth and height both <= RELIEF_M is relief, not a question (user decision 2026-10-09)
DOOR_MIN_H_M = 1.9
DOOR_W_M = (0.7, 3.0)
DOOR_FLOOR_M = 0.05       # "from the floor": open from within this of the storey floor (user, 2026-10-08)
RELIEF_M = 0.10
DOOR_HOST_M = 0.02        # a source door is a facade door when its ends lie within half its host + this of the contour
SLAB_GAP_M = (0.002, 0.010)  # an inset slab plate lies this far above its level (pattern roof-inset-plane)
PLATE_SAME_M = 0.0005    # the inset plates of one building share plate_gap_m / plate_overlap_m within this
TERRACE_COVER = 0.02      # terrace: the walkable part at the level and the parapet cap together cover the ledge
                          # within this share of its area (pattern terrace, user plan 2026-10-10)


class SpecError(ValueError):
    pass


def _matrix(obj_cfg, source=None):
    """The source's frame: frames[<source>] when the object has several sources, else frame."""
    frames = obj_cfg.get("frames")
    if frames is not None:
        if obj_cfg.get("frame"):
            raise SpecError("object.json gives both frame and frames; keep one")
        frame = frames.get(source)
        if frame is None:
            raise SpecError(f"object.json has no frame for source {source!r}; frames are for {sorted(frames)}")
    else:
        frame = obj_cfg.get("frame")
    if not frame or "to_object" not in frame:
        raise SpecError(f"object {obj_cfg.get('id', '?')}: object.json has no frame.to_object; "
                        "every spec needs a frame (HARNESS_PLAN §3)")
    m = np.asarray(frame["to_object"], dtype=float)
    if m.shape != (4, 4):
        raise SpecError("frame.to_object must be 4x4")
    return m


def _apply(m, pts):
    pts = np.asarray(pts, dtype=float).reshape(-1, 3)
    return pts @ m[:3, :3].T + m[:3, 3]


def _levels(dump, obj_cfg, m):
    helpers = [h for h in dump.get("helpers", []) if h["name"].startswith(LEVEL_PREFIX)]
    given = obj_cfg.get("levels")
    if helpers and given:
        raise SpecError("levels given twice: LEVEL_ helpers in the source and levels in object.json")
    if helpers:
        z = _apply(m, [h["location"] for h in helpers])[:, 2]
        levels = [{"name": h["name"][len(LEVEL_PREFIX):], "elev_m": round(float(e), 4)}
                  for h, e in zip(helpers, z)]
    elif given:
        levels = [{"name": lv["name"], "elev_m": float(lv["elev_m"])} for lv in given]
    else:
        raise SpecError("no levels: add LEVEL_<name> helpers to the source or levels to object.json; "
                        "the extractor does not guess levels")
    levels.sort(key=lambda lv: lv["elev_m"])
    if len(levels) < 2:
        raise SpecError("need at least two levels (a floor and the roof)")
    return levels


class _Sets:
    def __init__(self, n):
        self.parent = np.arange(n)

    def find(self, a):
        p = self.parent
        while p[a] != a:
            p[a] = p[p[a]]
            a = p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _weld(v):
    """Representative vertex index per vertex. Eight half-shifted grids guarantee that points
    within WELD_M / 2 on every axis share a cell in at least one grid. A cluster that chains wider
    than WELD_M (dense vertices) falls back to one plain grid, so no vertex moves more than WELD_M."""
    sets = _Sets(len(v))
    grids = []
    for shift in product((0.0, 0.5), repeat=3):
        keys = np.floor(v / WELD_M + np.asarray(shift)).astype(np.int64)
        _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
        grids.append(first[inverse.ravel()])
        for i, j in enumerate(grids[-1]):
            if i != j:
                sets.union(int(j), i)
    rep = np.array([sets.find(i) for i in range(len(v))])
    lo, hi = np.full_like(v, np.inf), np.full_like(v, -np.inf)
    np.minimum.at(lo, rep, v)
    np.maximum.at(hi, rep, v)
    wide = (hi[rep] - lo[rep]).max(axis=1) > WELD_M
    rep[wide] = grids[0][wide]
    return rep


def _opening_ids():
    """Material ids of the `opening` group (standards/material_id_ranges.yaml, ADR 0001)."""
    from functools import lru_cache

    @lru_cache(maxsize=1)
    def load():
        import yaml
        from dt_ai.core.io import repo_root
        g = yaml.safe_load((repo_root() / "standards/material_id_ranges.yaml").read_text(encoding="utf-8"))
        return frozenset(range(g["groups"]["opening"]["first"], g["groups"]["opening"]["last"] + 1))
    return load()


def _mesh(dump, m, with_materials=False):
    """All non-collision triangles in object coordinates, vertices welded by position. With
    with_materials, also the material id and the source mesh name per triangle."""
    verts, tris, mats, owners, base = [], [], [], [], 0
    for mesh in dump["meshes"]:
        if mesh["name"].upper().startswith("UCX_") or not mesh["triangles"]:
            continue
        verts.append(_apply(m, mesh["vertices"]))
        tris.append(np.asarray(mesh["triangles"], dtype=np.int64) + base)
        ids = mesh.get("material_ids")
        if ids and len(ids) != len(mesh["triangles"]):
            raise SpecError(f"mesh {mesh['name']}: {len(ids)} material ids for {len(mesh['triangles'])} triangles")
        mats.append(np.asarray(ids or [0] * len(mesh["triangles"]), dtype=np.int64))
        owners += [mesh["name"]] * len(mesh["triangles"])
        base += len(mesh["vertices"])
    if not tris:
        raise SpecError("the source holds no mesh triangles")
    v = np.vstack(verts)
    rep = _weld(v)
    used, inverse = np.unique(rep, return_inverse=True)
    t = inverse.ravel()[np.vstack(tris)]
    if np.linalg.det(m[:3, :3]) < 0:  # a mirroring frame flips facing; restore outward normals
        t = t[:, ::-1]
    return (v[used], t, np.concatenate(mats), np.array(owners)) if with_materials else (v[used], t)


def _areas(v, tris):
    p = v[tris]
    return np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1) / 2


def _parts(v, tris):
    """Connected parts as arrays of triangle indices, largest surface area first."""
    sets = _Sets(len(v))
    for a, b, c in tris:
        sets.union(int(a), int(b))
        sets.union(int(a), int(c))
    groups = defaultdict(list)
    for i, t in enumerate(tris):
        groups[sets.find(int(t[0]))].append(i)
    area = _areas(v, tris)
    return sorted((np.array(g) for g in groups.values()), key=lambda g: area[g].sum(), reverse=True)


def _clear_height(v, tris, z):
    """Move a cut height off rows of vertices so edge-on triangles cannot drop out of the section."""
    zs = v[np.unique(tris), 2]
    while np.any(np.abs(zs - z) < 1e-6):
        z += 1e-4
    return z


def _section(v, tris, z, p=None):
    """Segments where the plane z cuts the triangles (p: the triangles' points, if already taken)."""
    p = v[tris] if p is None else p
    d = p[:, :, 2] - z
    cut = (d.min(axis=1) < 0) & (d.max(axis=1) > 0)
    segments = []
    for tri, dist in zip(p[cut], d[cut]):
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if (dist[i] < 0) != (dist[j] < 0):
                t = dist[i] / (dist[i] - dist[j])
                pts.append(tri[i, :2] + t * (tri[j, :2] - tri[i, :2]))
        # snap to 1 um so cuts of neighbouring triangles meet exactly and the ring can close
        pts = np.round(pts, 6)
        if len(pts) == 2 and np.hypot(*(pts[0] - pts[1])) > 1e-9:
            segments.append(LineString(pts))
    return segments


def _turns(pts):
    """Signed turn in degrees (left positive) at every vertex of a closed ring."""
    d1 = pts - np.roll(pts, 1, axis=0)
    d2 = np.roll(pts, -1, axis=0) - pts
    return np.degrees(np.arctan2(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0], (d1 * d2).sum(axis=1)))


def _line_cross(p1, p2, q1, q2):
    d, e = p2 - p1, q2 - q1
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-12:
        return None
    t = ((q1[0] - p1[0]) * e[1] - (q1[1] - p1[1]) * e[0]) / den
    return p1 + t * d


def _line_distance(c, p1, p2):
    d = p2 - p1
    return abs(d[0] * (c[1] - p1[1]) - d[1] * (c[0] - p1[0])) / float(np.linalg.norm(d))


def _circle(pts):
    """Least-squares (Kasa) circle through the points: centre and radius."""
    a = np.column_stack([2 * pts[:, 0], 2 * pts[:, 1], np.ones(len(pts))])
    cx, cy, c = np.linalg.lstsq(a, (pts ** 2).sum(axis=1), rcond=None)[0]
    return np.array([cx, cy]), float(np.sqrt(c + cx * cx + cy * cy))


def _arc_corner(pts, run, before, after):
    """Corner point and radius when the run is a circular arc tangent to both neighbouring walls."""
    corner = _line_cross(pts[before], pts[run[0]], pts[run[-1]], pts[after])
    if corner is None:
        return None
    centre, r = _circle(pts[run])
    tol = ARC_FIT_M + ARC_FIT_SHARE * r
    off_circle = np.abs(np.linalg.norm(pts[run] - centre, axis=1) - r).max()
    tangent = (abs(_line_distance(centre, pts[before], pts[run[0]]) - r) <= tol and
               abs(_line_distance(centre, pts[run[-1]], pts[after]) - r) <= tol)
    return (corner, r) if off_circle <= tol and tangent else None


def _rounded_corners(pts):
    """Replace a tessellated arc between two straight walls by the corner point with its radius,
    only when the points fit a circle tangent to both walls (faceted corners stay facets).
    Returns a list of (xy, r or None)."""
    pts = pts[np.abs(_turns(pts)) >= 0.05]   # collinear section points (triangle diagonals) split arcs
    n = len(pts)
    turn = _turns(pts)
    arc = np.abs(turn) <= ARC_TURN_MAX_DEG
    if arc.all() or not arc.any():
        return [(p, None) for p in pts]
    start = int(np.flatnonzero(~arc)[0])
    order = [(start + k) % n for k in range(n)]
    out, k = [], 0
    while k < n:
        i = order[k]
        if not arc[i]:
            out.append((pts[i], None))
            k += 1
            continue
        run = [i]
        while k + len(run) < n and arc[order[k + len(run)]] and np.sign(turn[order[k + len(run)]]) == np.sign(turn[i]):
            run.append(order[k + len(run)])
        found = None
        if len(run) >= ARC_MIN_VERTICES and abs(turn[run].sum()) >= ARC_MIN_TURN_DEG:
            found = _arc_corner(pts, run, (run[0] - 1) % n, (run[-1] + 1) % n)
        if found is None:
            out.extend((pts[j], None) for j in run)
        else:
            out.append(found)
        k += len(run)
    return out


def _drop_small_kinks(points):
    """Keep vertices turning over KINK_DEG in the section itself, and rounded corners; drop the rest.
    Deciding on the original angles keeps a 7 degree kink next to a 4.5 degree one (PR #19 review)."""
    turn = np.abs(_turns(np.array([p for p, _ in points])))
    keep = [pt for pt, t in zip(points, turn) if t > KINK_DEG or pt[1] is not None]
    return keep if len(keep) >= 3 else list(points)


def _contour_points(poly):
    poly = orient(poly.simplify(SIMPLIFY_M, preserve_topology=True), sign=1.0)
    pts = _drop_small_kinks(_rounded_corners(np.array(poly.exterior.coords)[:-1]))
    out = [[round(float(x), 3) + 0.0, round(float(y), 3) + 0.0] + ([{"r": round(r, 3)}] if r else [])
           for (x, y), r in pts]
    start = min(range(len(out)), key=lambda i: (out[i][1], out[i][0]))
    return out[start:] + out[:start]


def _spans(v, tris, z0, z1):
    """Height intervals of the storey between consecutive vertex heights: for vertical walls every
    horizontal section inside one interval has the same shape, so one cut per interval sees every
    element with its heights. Vertex heights closer than EVENT_MIN_M are coalesced (a densely
    subdivided wall keeps its intervals; PR #19 review 2), never dropped."""
    zs = [float(z) for z in np.unique(np.round(v[np.unique(tris), 2], 6)) if z0 < z < z1]
    cuts = [z0]
    for z in zs:
        if z - cuts[-1] >= EVENT_MIN_M:
            cuts.append(z)
    if z1 - cuts[-1] < EVENT_MIN_M and len(cuts) > 1:
        cuts.pop()
    cuts.append(z1)
    out = []
    for a, b in zip(cuts, cuts[1:]):
        rows = [a] + [z for z in zs if a < z < b] + [b]     # cut in the largest gap between vertex rows,
        lo, hi = max(zip(rows, rows[1:]), key=lambda g: g[1] - g[0])   # never in a sub-mm sliver (PR #19 r3)
        out.append((a, b, (lo + hi) / 2))
    return out


def _runs(spans):
    """Contiguous height runs of a shape's intervals: one shape at 0-0.6 and 3.0-3.3 is two elements."""
    runs = []
    for a, b in sorted(spans):
        if runs and a - runs[-1][-1][1] < 1e-6:
            runs[-1].append((a, b))
        else:
            runs.append([(a, b)])
    return runs


def _deviations(groups, contour):
    """Pieces where other section shapes of the storey differ from its contour (not full height),
    one piece per contiguous height run of the shape."""
    pieces = []
    for g in groups:
        for kind, diff in (("projection", g["poly"].difference(contour)), ("recess", contour.difference(g["poly"]))):
            for part in shapely.get_parts(diff):
                if part.is_empty or _is_relief(part):      # relief is no question (#31)
                    continue
                far = max(contour.exterior.distance(shapely.Point(xy)) for xy in part.exterior.coords)
                if far >= SAME_CONTOUR_M:
                    pieces.extend({"kind": kind, "geom": part, "spans": run} for run in _runs(g["spans"]))
    return pieces


def _relief(poly):
    """Parts of a contour shape with both sizes <= RELIEF_M (bumps out and notches in), and the
    shape without them. Found by a mitred opening and closing, kept only when both sides of the
    part's minimum rectangle are small, so a thin but deep fin is not relief."""
    r = RELIEF_M / 2 + 1e-4
    opened = poly.buffer(-r, join_style="mitre").buffer(r, join_style="mitre")
    closed = poly.buffer(r, join_style="mitre").buffer(-r, join_style="mitre")
    bumps = [g for g in shapely.get_parts(poly.difference(opened)) if g.area > 1e-8 and _is_relief(g)]
    notches = [g for g in shapely.get_parts(closed.difference(poly)) if g.area > 1e-8 and _is_relief(g)]
    if not bumps and not notches:
        return poly, 0
    out = poly.difference(shapely.unary_union([g.buffer(1e-7) for g in bumps]) if bumps else Polygon())
    out = out.union(shapely.unary_union([g.buffer(1e-7) for g in notches])) if notches else out
    out = max(shapely.get_parts(out.buffer(0)), key=lambda x: x.area)
    return Polygon(out.exterior).simplify(SIMPLIFY_M, preserve_topology=True), len(bumps) + len(notches)


def _is_relief(geom):
    box = np.array(geom.minimum_rotated_rectangle.exterior.coords)[:-1]
    return max(float(np.linalg.norm(box[i] - box[i - 1])) for i in range(len(box))) <= RELIEF_M + 1e-6


def _mouth(n, base, edge):
    """Width of a recess n at its mouth, or None when the mouth is not proven on the facade."""
    free = shapely.line_merge(n.boundary.difference(edge))
    parts = [g for g in shapely.get_parts(free) if g.length > SHARE_TOL_M]
    if len(parts) != 1:
        return None
    c = np.array(parts[0].coords)
    m0, m1 = c[0], c[-1]
    span = float(np.linalg.norm(m1 - m0))
    if span < 1e-6 or parts[0].length > span * 1.01 + 1e-6:          # bent mouth: not a facade line
        return None
    u = (m1 - m0) / span
    beyond = 4 * SHARE_TOL_M                                         # the edge buffer shortened the mouth
    if any(base.boundary.distance(shapely.Point(q)) > SHARE_TOL_M for q in (m0 - u * beyond, m1 + u * beyond)):
        return None
    along = (np.array(n.exterior.coords) - m0) @ u
    return float(np.ptp(along))


def _door_recesses(closed, base, z0, z1):
    """Recesses of the contour shape open from the storey floor (user rules, #31): returns the
    shape with them filled and the doors [{geom, z0, z1, mouth_m}]. A recess is a region the shape
    at another height covers but this one does not, whose mouth is proven to be on the facade: the
    part of its boundary off the shape is one straight segment and the shape's boundary continues
    along that line beyond both of its ends (PR #33 review 1: a block in the inner corner of an
    L-shaped plan has a bent mouth and stays a question; an outward band has no facade beyond its
    ends). The width is the recess's exact extent along the mouth. Relief is taken off every shape
    first, so frame profiles next to a door neither widen it nor join it."""
    closed = [(a, b, _relief(poly)[0]) for a, b, poly in closed]
    hull = base.convex_hull
    cands = shapely.unary_union([poly.difference(base).intersection(hull) for _, _, poly in closed])
    cands = cands.buffer(-SHARE_TOL_M, join_style="mitre").buffer(SHARE_TOL_M, join_style="mitre")   # no slivers
    edge = base.boundary.buffer(SHARE_TOL_M)
    doors = []
    for n in shapely.get_parts(cands):
        if n.area < 1e-4:
            continue
        mouth = _mouth(n, base, edge)
        if mouth is None or not (DOOR_W_M[0] - 1e-6 <= mouth <= DOOR_W_M[1] + 1e-6):
            continue
        top = None
        for a, b, poly in closed:                # contiguous open heights from the floor up
            covered = poly.intersection(n).area >= 0.5 * n.area
            if top is None:
                if a - z0 > DOOR_FLOOR_M:
                    break
                if covered:
                    continue
                top = b
            elif covered or a - top > EVENT_MIN_M:
                break
            else:
                top = b
        if top is not None and top - z0 >= DOOR_MIN_H_M - 1e-6:
            doors.append({"geom": n, "z0": z0, "z1": top, "mouth_m": round(mouth, 3)})
    if doors:
        base = shapely.unary_union([base] + [d["geom"].buffer(1e-7) for d in doors]).buffer(0)
        base = max(shapely.get_parts(base), key=lambda x: x.area)
        base = Polygon(base.exterior).simplify(SIMPLIFY_M, preserve_topology=True)
    return base, doors


def _span_text(spans):
    merged = []
    for a, b in sorted(spans):
        if merged and a - merged[-1][1] < 1e-6:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return ", ".join(f"{a:.3f}-{b:.3f}" for a, b in merged)


def _flat_region(v, tris, z, region):
    """The plan region (a polygon) of the up-facing horizontal triangles at height z, clipped to region."""
    p = v[tris]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    flat = (np.abs(p[:, :, 2] - z).max(axis=1) < EVENT_MIN_M) & (n[:, 2] > 0)
    tri = [Polygon(t[:, :2]) for t in p[flat]]
    tri = [t for t in tri if t.area > 0]
    return shapely.unary_union(tri).intersection(region) if tri else Polygon()


def _vertical_near(p, line, z0, z1):
    """Vertical triangles (of p, a triangle array) between z0 and z1 lying along line: every vertex within
    10 mm of it, so a face standing across the line is not taken for a face on it (review 3 of PR #61)."""
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    upright = np.abs(n[:, 2]) <= 0.01 * np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    inside = (p[:, :, 2].min(axis=1) >= z0 - EVENT_MIN_M) & (p[:, :, 2].max(axis=1) <= z1 + EVENT_MIN_M)
    if not len(p):
        return upright
    # 2 x 5 mm: the line stops 5 mm short of the ledge outline, where the face's end vertices stand
    near = shapely.distance(line, shapely.points(p[:, :, :2].reshape(-1, 2))).reshape(-1, 3).max(axis=1) <= 2 * SAME_CONTOUR_M
    return upright & inside & near


def _wall_cover(v, tris, line, z0, z1):
    """Area of line x (z0..z1) actually covered by vertical faces: per straight piece of the line
    (collinear pieces merged), the faces lying on it are unrolled to (along, z), united and clipped to the
    piece, so faces covering one place twice never make up for a place covered by none (review 2 of PR
    #61) and a face crossing a piece's end still counts on both sides (review 3)."""
    p = v[tris]
    p = p[_vertical_near(p, line, z0, z1)]
    total = 0.0
    for piece in shapely.get_parts(shapely.line_merge(line) if line.geom_type == "MultiLineString" else line):
        c = np.asarray(piece.simplify(1e-9).coords)
        for a, b in zip(c[:-1], c[1:]):
            length = float(np.linalg.norm(b - a))
            if length <= SAME_CONTOUR_M:
                continue
            u = (b - a) / length
            off = np.abs((p[:, :, 0] - a[0]) * u[1] - (p[:, :, 1] - a[1]) * u[0]).max(axis=1)
            on = p[off <= SAME_CONTOUR_M]
            flat2d = [Polygon(np.column_stack([(t[:, :2] - a) @ u, t[:, 2]])) for t in on]
            cover = shapely.unary_union([f for f in flat2d if f.area > 0]) if len(on) else Polygon()
            total += cover.intersection(shapely.box(0, z0, length, z1)).area
    return total


def _ledge_faces(v, tris, ledge, z0, z1, cap=None, inner_line=None, zt=None):
    """Storey triangles standing on a ledge: centre inside the ledge (off its outline) and above the level.
    On a terrace the parapet itself (its cap and inner face) is left out (Codex review 2 of PR #61)."""
    p = v[tris]
    c = p.mean(axis=1)
    inner = ledge.buffer(-SAME_CONTOUR_M)
    if inner.is_empty:
        return p[:0]
    keep = (c[:, 2] > z0 + EVENT_MIN_M) & (c[:, 2] < z1 - EVENT_MIN_M) & shapely.contains_xy(inner, c[:, 0], c[:, 1])
    if cap is not None:
        on_cap = (np.abs(p[:, :, 2] - zt).max(axis=1) < EVENT_MIN_M) & shapely.contains_xy(
            cap.buffer(SAME_CONTOUR_M), c[:, 0], c[:, 1])
        keep &= ~on_cap & ~_vertical_near(p, inner_line, z0, zt)
    return p[keep]


def _inset_plates(v, extra, z0, region):
    """Inset slab plates over a level (pattern roof-inset-plane, user rules 2026-10-10): the connected
    groups of up-facing triangles of the parts outside the body whose height lies SLAB_GAP_M above z0
    (within the checkers' 0.1 mm weld) and whose centre lies inside region. Each group is one plate,
    flat on its own within WELD_M (reviews of PR #63, #64): returns ([(plan polygon, raw gap)], number of
    groups that are not flat - no plate, never averaged away)."""
    if extra is None or not len(extra):
        return [], 0
    p = v[extra]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    z = p[:, :, 2]
    lo, hi = SLAB_GAP_M
    near = ((n[:, 2] > 0) & (z.mean(axis=1) >= z0 + lo - WELD_M) & (z.mean(axis=1) <= z0 + hi + WELD_M)
            & shapely.contains_xy(region.buffer(SAME_CONTOUR_M), *p[:, :, :2].mean(axis=1).T))
    if not near.any():
        return [], 0
    cand = extra[near]
    plates, bad = [], 0
    for group in _parts(v, cand):
        zz = v[cand[group]][:, :, 2]
        if float(zz.max() - zz.min()) > WELD_M:
            bad += 1
            continue
        tri = [Polygon(t[:, :2]) for t in v[cand[group]]]
        plates.append((shapely.unary_union([t for t in tri if t.area > 0]), float(zz.mean()) - z0))
    return plates, bad


def _holes(v, tris, z):
    """Closed outlines of the body's open edges lying flat at height z (the holes of inset slabs)."""
    e = np.sort(np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]), axis=1)
    edges, count = np.unique(e, axis=0, return_counts=True)
    once = edges[count == 1]
    once = once[np.abs(v[once][:, :, 2] - z).max(axis=1) <= WELD_M]
    return list(polygonize([LineString(v[pair][:, :2]) for pair in once]))


def _plate_params(v, body, extra, z, region):
    """Measured (plate_gap_m, plate_overlap_m) of every inset plate over level z inside region, and the
    problems that make a plate unreadable (pattern roof-inset-plane, user 2026-10-10): its height above the
    level, and how far it overlaps the one hole of the body it lies over, outline to outline, evenly all
    round as the checker wants it (review 1 of PR #64). A slab with no readable plate is a problem too."""
    plates, bad = _inset_plates(v, extra, z, region)
    holes = _holes(v, body, z)
    out, problems = [], ["a plate that is not flat"] * bad
    for part, gap in plates:
        inside = [h for h in holes if part.buffer(-WELD_M).contains(h)]
        if len(inside) != 1:
            problems.append("a plate over no single hole")
            continue
        hole = inside[0]
        overlap = float(hole.exterior.distance(part.exterior))
        grown = hole.buffer(overlap, join_style="mitre", mitre_limit=1e6)
        if float(grown.exterior.hausdorff_distance(part.exterior)) > WELD_M:
            problems.append("a plate that overlaps its hole unevenly")
            continue
        out.append((gap, overlap))
    if not out and not problems:
        problems.append("no inset plate")
    return out, problems


def _terrace(v, tris, groups, closed, z0, z1, below, extra=None):
    """Pattern terrace (user plan 2026-10-10): a storey whose lowest section shape is the floor below's
    contour, from the level up to a parapet top, with the storey's own wall shape above it to the
    storey top. Structure, not a height difference (Codex review 1 of PR #61): the walkable part at the
    level and the parapet cap at its top cover the ledge in plan without overlapping, and the parapet's
    inner face stands along the walkable part's edge off the ledge outline over the full parapet height.
    Returns (wall group, parapet top, areas) or None when the storey is no such terrace."""
    if below is None or len(groups) != 2:
        return None
    low = next(g for g in groups if closed[0][:2] in g["spans"])
    high = next(g for g in groups if g is not low)
    zt = max(b for _, b in low["spans"])
    if (closed[0][0] - z0 >= EVENT_MIN_M or z1 - closed[-1][1] >= EVENT_MIN_M
            or closed[-1][:2] not in high["spans"] or min(a for a, _ in high["spans"]) < zt - EVENT_MIN_M
            or low["poly"].hausdorff_distance(below) >= SAME_CONTOUR_M
            or not high["poly"].buffer(SAME_CONTOUR_M).within(low["poly"].buffer(2 * SAME_CONTOUR_M))):
        return None
    ledge = low["poly"].difference(high["poly"])
    if ledge.area <= HOLE_MIN_M2:
        return None
    walk, cap = _flat_region(v, tris, z0, ledge), _flat_region(v, tris, zt, ledge)
    limit = TERRACE_COVER * ledge.area
    if cap.area <= HOLE_MIN_M2 or walk.intersection(cap).area > limit:
        return None
    # an inset walkable plate (user rule 2026-10-10): a separate plate SLAB_GAP_M above the level, its edge
    # under the parapet; the walkable part is the plate where no cap covers it
    plates, bad = _inset_plates(v, extra, z0, ledge)
    if bad:                                              # a plate that is not flat: no terrace read (the
        return None                                      # checker rejects it too)
    gap = round(float(np.median([g for _, g in plates])), 4) if plates else None
    for plate, _ in plates:
        walk = walk.union(plate.intersection(ledge).difference(cap))
    if walk.area <= HOLE_MIN_M2 or ledge.symmetric_difference(walk.union(cap)).area > limit:
        return None
    inner_line = walk.boundary.difference(ledge.boundary.buffer(SAME_CONTOUR_M))
    h = zt - z0
    if inner_line.length <= SAME_CONTOUR_M:
        return None
    face = _wall_cover(v, tris, inner_line, z0, zt)
    if abs(face - inner_line.length * h) > TERRACE_COVER * inner_line.length * h:
        return None
    return high, zt, cap, inner_line, {"walkable_inset_gap_m": gap, "walkable_m2": round(walk.area, 3), "cap_m2": round(cap.area, 3), "ledge_m2": round(ledge.area, 3),
                      "inner_face_m2": round(face, 3)}


def _level_contour(v, tris, z0, z1, name, at_m=None, below=None, extra=None):
    """Level contour = walls over the full storey height (user decisions 2026-10-08). Accepted only
    when one section shape is at both storey ends and is also the tallest; otherwise the exterior
    shell cannot tell the wall from a plinth, cornice or belt, so the extractor stops with the
    candidate shapes and the user names a height of the wall shape (object.json contour_at_m)."""
    spans = _spans(v, tris, z0, z1)
    p = v[tris]
    p = p[(p[:, :, 2].min(axis=1) < z1) & (p[:, :, 2].max(axis=1) > z0)]   # this storey only, taken once
    lo, hi = np.floor(p[:, :, 2].min(axis=1) / BIN_M).astype(int), np.floor(p[:, :, 2].max(axis=1) / BIN_M).astype(int)
    bins = defaultdict(list)                                               # height bins: a cut reads its own
    for i, (l, h) in enumerate(zip(lo, hi)):
        for k in range(l, h + 1):
            bins[k].append(i)
    closed, mouth_spans = [], []
    for a, b, z in spans:          # wall breaks are bridged as openings, so they do not open the section
        poly, mouths, unresolved = op.close_section(_section(None, None, z, p[bins[int(np.floor(z / BIN_M))]]))
        mouth_spans.append((a, b, mouths, unresolved))
        if poly is not None:
            closed.append((a, b, poly))
    if not closed:
        raise SpecError(f"level {name}: none of {len(spans)} body sections between {z0} and {z1} m "
                        "closes; the contour is not invented (ask the user, HARNESS_PLAN §7 gray zone)")
    groups = []
    for a, b, poly in closed:
        for g in groups:
            if g["poly"].hausdorff_distance(poly) < SAME_CONTOUR_M:
                g["spans"].append((a, b))
                break
        else:
            groups.append({"poly": poly, "spans": [(a, b)]})
    for g in groups:
        g["height"] = sum(b - a for a, b in g["spans"])
    bottom = next(g for g in groups if closed[0][:2] in g["spans"])
    top = next(g for g in groups if closed[-1][:2] in g["spans"])
    at_ends = closed[0][0] - z0 < EVENT_MIN_M and z1 - closed[-1][1] < EVENT_MIN_M
    tallest = max(g["height"] for g in groups)
    terrace = None if at_m is not None else _terrace(v, tris, groups, closed, z0, z1, below, extra)
    if terrace is not None:
        base, zt, cap, inner_line, areas = terrace
        rule = f"terrace: parapet {zt - z0:.3f} m from the level"
    elif at_m is not None:
        base = next((g for g in groups if any(a <= at_m <= b for a, b in g["spans"])), None)
        if base is None:
            raise SpecError(f"level {name}: contour_at_m {at_m} m is not on a closed section of the storey")
        rule = f"user height {at_m} m"
    elif at_ends and bottom is top and bottom["height"] >= tallest - 1e-9:
        base, rule = bottom, "single shape" if len(groups) == 1 else "both storey ends, tallest"
    else:
        shapes = "; ".join(f"shape {i + 1}: {g['poly'].area:.2f} m2 at {_span_text(g['spans'])} m "
                           f"({g['height'] / (z1 - z0):.0%})" for i, g in enumerate(groups))
        ends = "" if at_ends else f"; the storey ends are not closed sections (first closed {closed[0][0]:.3f}, " \
                                  f"last {closed[-1][1]:.3f} m)"
        raise SpecError(f"level {name}: no section shape is both at the two storey ends and the tallest, so the "
                        f"wall over the full height is unclear{ends}. {shapes}. Set contour_at_m.{name} in "
                        "object.json to a height of the wall shape (HARNESS_PLAN §4)")
    report = {"sections": len(spans), "closed_sections": len(closed), "contour_rule": rule,
              "contour_height_share": round(base["height"] / (z1 - z0), 3), "other_contours": len(groups) - 1}
    others = [g for g in groups if g is not base]
    if terrace is not None:                    # the parapet shape is the terrace, not a question
        report["terrace"] = {"parapet_h_m": round(zt - z0, 3), **areas}
        others = []
    if below is not None:                      # anything else standing on a ledge: a question
        on = _ledge_faces(v, tris, below.difference(base["poly"]), z0, z1,
                          *((cap, inner_line, zt) if terrace is not None else ()))
        if len(on):
            c = on.reshape(-1, 3)
            report["ledge_structure"] = {"triangles": int(len(on)), "heights_m": [round(z0, 3), round(float(c[:, 2].max()), 3)],
                                         "at": [round(float(c[:, 0].mean()), 2), round(float(c[:, 1].mean()), 2)]}
    # door recesses leave the contour and become openings; relief is not a kink (#31)
    poly, relief = _relief(base["poly"])
    poly, doors = _door_recesses(closed, poly, z0, z1)
    report["door_recesses"], report["relief_parts"] = len(doors), relief
    # every other shape is not over the full height -> questions
    report["bridged_sections"] = sum(1 for _, _, m, _ in mouth_spans if m)
    return poly, report, _deviations(others, poly), mouth_spans, doors


def _measure(piece, section, contour_pts):
    """Bind a piece to the facet of the source section it shares most boundary with and measure
    along and across that facet (not the simplified contour: a dropped small kink or a rounded
    corner must not change depth). The reported wall is the contour wall nearest to that facet.
    A piece sharing no facet is reported unbound (wall None), never bound to wall 0."""
    ring = np.array(orient(section, sign=1.0).exterior.coords)[:-1]
    ring = ring[np.abs(_turns(ring)) >= 0.05]
    best = None
    for f in range(len(ring)):
        shared = piece["geom"].boundary.intersection(LineString([ring[f], ring[(f + 1) % len(ring)]]).buffer(SHARE_TOL_M))
        if best is None or shared.length > best[1].length:
            best = (f, shared)
    f, shared = best
    coords = np.array([xy for g in shapely.get_parts(piece["geom"]) for xy in g.exterior.coords])
    if shared.length <= 2 * SHARE_TOL_M:
        box = np.array(piece["geom"].minimum_rotated_rectangle.exterior.coords)[:-1]
        sides = sorted(float(np.linalg.norm(box[i] - box[i - 1])) for i in range(4))
        return {"wall": None, "length_m": sides[-1], "depth_m": sides[0], "facade_share": 0.0}
    a, b = ring[f], ring[(f + 1) % len(ring)]
    u = (b - a) / np.linalg.norm(b - a)
    along = (np.array([xy for g in shapely.get_parts(shared) for xy in g.coords]) - a) @ u
    length = float(along.max() - along.min())
    depth = max(_line_distance(xy, a, b) for xy in coords)
    pts = np.array([q[:2] for q in contour_pts], dtype=float)
    mid = shapely.Point(*(a + u * (along.max() + along.min()) / 2))
    wall = min(range(len(pts)), key=lambda w: LineString([pts[w], pts[(w + 1) % len(pts)]]).distance(mid))
    wall_len = float(np.linalg.norm(pts[(wall + 1) % len(pts)] - pts[wall]))
    return {"wall": wall, "length_m": length, "depth_m": depth, "facade_share": length / wall_len}


def _questions(levels, floors, polys, pieces_by_level, stats):
    """Merge pieces into connected components across levels and turn them into questions; a
    component with depth and height both <= RELIEF_M is relief (counted in stats, no question)."""
    items = []
    for li, pieces in enumerate(pieces_by_level):
        for p in pieces:
            items.append({**p, **_measure(p, polys[li], floors[li]["contour"]), "levels": {li}})
    def touch(x, y):  # one element: same kind, overlapping in plan and adjacent in height
        return (x["kind"] == y["kind"] and x["geom"].buffer(0.01).intersects(y["geom"]) and
                any(c <= b + EVENT_MIN_M and a <= d + EVENT_MIN_M for a, b in x["spans"] for c, d in y["spans"]))

    sets = _Sets(len(items))
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if touch(items[i], items[j]):
                sets.union(i, j)
    comps = defaultdict(list)
    for i in range(len(items)):
        comps[sets.find(i)].append(items[i])
    names = [lv["name"] for lv in levels]
    out = []
    for comp in comps.values():
        main = max(comp, key=lambda p: p["length_m"])
        lv = sorted({names[li] for p in comp for li in p["levels"]}, key=names.index)
        spans = [s for p in comp for s in p["spans"]]
        union = shapely.unary_union([p["geom"] for p in comp])
        li = min(main["levels"])
        whole = _measure({"geom": union}, polys[li], floors[li]["contour"])
        share = max(whole["facade_share"], *(p["facade_share"] for p in comp))
        depth = max(p["depth_m"] for p in comp)
        if depth <= RELIEF_M + 1e-6 and max(b for _, b in spans) - min(a for a, _ in spans) <= RELIEF_M + 1e-6:
            stats["section_relief_parts"] = stats.get("section_relief_parts", 0) + 1
            continue
        c = union.centroid
        out.append({"priority": "high" if len(lv) >= 2 or share > PRIORITY_SHARE else "normal",
                    "kind": main["kind"], "levels": lv, "wall": main["wall"],
                    "depth_m": round(depth, 3), "length_m": round(whole["length_m"], 3),
                    "facade_share": round(share, 4),
                    "heights_m": [round(min(a for a, _ in spans), 3), round(max(b for _, b in spans), 3)],
                    "at": [round(c.x, 2), round(c.y, 2)]})
    out.sort(key=lambda q: (q["priority"] != "high", names.index(q["levels"][0]), q["kind"]))
    for n, q in enumerate(out, 1):
        q["n"] = n
    return out


def _source_questions(dump, levels):
    """Questions a source converter already found (Revit attachments, #29), placed on the storeys
    their heights touch."""
    out = []
    for q in dump.get("questions", []):
        z0, z1 = q["heights_m"]
        names = [a["name"] for a, b in zip(levels, levels[1:]) if z0 < b["elev_m"] and z1 > a["elev_m"]]
        out.append({**q, "levels": names or [levels[0]["name"]]})
    return out


def questions_markdown(spec_id, questions):
    """The object's questions file: everything not over the full storey height (HARNESS_PLAN §4)."""
    lines = [f"# Questions — {spec_id}", "",
             "Written by the spec extractor. Each row is geometry that is not over the full storey height,",
             "so it does not change the level contour (user decision 2026-10-08). Priority high = through",
             "2 or more levels or over 10 % of the facade length. Heights are the exact height interval of",
             "the element. A recess at window height may be an opening (separated by issue #7).",
             "Wall `—`: the piece shares no facet with the contour (unbound); measured on its own box.", "",
             "| # | Priority | Kind | Levels | Wall | Depth m | Length m | Facade share | Heights m | At (x, y) | Answer |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]

    def cell(value, fmt=str):
        return "—" if value is None else fmt(value)

    for q in questions:
        lines.append(f"| {q['n']} | {q['priority']} | {q['kind']} | {', '.join(q['levels'])} | {cell(q['wall'])} | "
                     f"{cell(q['depth_m'])} | {cell(q['length_m'])} | {cell(q['facade_share'], lambda s: f'{s:.1%}')} | "
                     f"{cell(q['heights_m'], lambda h: f'{h[0]}–{h[1]}')} | "
                     f"{cell(q['at'], lambda a: f'{a[0]}, {a[1]}')} | |")
    return "\n".join(lines) + "\n"


def _has_parapet(edge, body_pts, roof_tris):
    """A parapet is structure, not a height difference (reviews of PR #54): there is none only when
    the roof surface reaches the wall top all along the outer wall line. The wall top along the line
    is the top of the body points on it, interpolated by arc length; the roof height is read from
    the roof triangles just inside the line, at every PARAPET_SAMPLE_M and at every wall-top point."""
    on = [(edge.project(shapely.Point(x, y)), z) for (x, y, z) in body_pts
          if edge.distance(shapely.Point(x, y)) <= PARAPET_EDGE_M]
    if not on:
        return False
    tops = defaultdict(float)
    for s, z in on:
        key = round(s, 3)
        tops[key] = max(tops.get(key, -1e9), z)
    ss = np.array(sorted(tops))
    zz = np.array([tops[s] for s in ss])
    length = edge.length
    samples = sorted(set(np.round(np.arange(0.0, length, PARAPET_SAMPLE_M), 3)) | set(ss))
    flat = [Polygon(t[:, :2]) for t in roof_tris]
    tree = shapely.STRtree(flat)
    centre = Polygon(edge).centroid
    for s in samples:
        q = edge.interpolate(s)
        inward = np.array([centre.x - q.x, centre.y - q.y])
        inward = inward / max(float(np.linalg.norm(inward)), 1e-9)
        probe = shapely.Point(q.x + inward[0] * PARAPET_EDGE_M / 2, q.y + inward[1] * PARAPET_EDGE_M / 2)
        hits = [i for i in tree.query(probe.buffer(PARAPET_EDGE_M / 2)) if flat[i].distance(probe) <= PARAPET_EDGE_M / 2]
        if not hits:
            return True                      # no roof at the wall line: something stands between
        roof_z = max(_z_at(roof_tris[i], probe) for i in hits)
        wall_z = float(np.interp(s, ss, zz, period=length))   # the outer line is closed (review 4 of PR #54)
        if wall_z - roof_z > SAME_CONTOUR_M:
            return True                      # the wall rises above the roof here: an upstand
    return False


def _z_at(tri, pt):
    """Height of the plane of a triangle at a plan point (barycentric)."""
    (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = tri
    d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(d) < 1e-12:
        return float(max(z0, z1, z2))
    a = ((y1 - y2) * (pt.x - x2) + (x2 - x1) * (pt.y - y2)) / d
    b = ((y2 - y0) * (pt.x - x2) + (x0 - x2) * (pt.y - y2)) / d
    return float(a * z0 + b * z1 + (1 - a - b) * z2)


def _roof(v, tris, below_level, top_level, top_contour, extra=None, above=None):
    """The roof level is input, like every level; geometry only confirms it (issues #16, #9).
    Roof: up-facing body surfaces inside the top floor contour with a slope up to ROOF_SLOPE_MAX_DEG
    (drainage slopes are a flat roof) whose centres lie within ROOF_LEVEL_TOL_M of the top input
    level; the roof height is their area-weighted mean. The roof itself must cover ROOF_OWN of the
    top floor and, with every up-facing surface above it (cap, shaft tops), close ROOF_CLOSED of it.
    Steeper roof parts, no roof, an open roof or a hole that is not a shaft are questions, never a
    guess. extra: separate roof parts joined to the body for this check (#9, option (a)); above:
    every other separate part, whose near-flat tops above the roof (a parapet cap or shaft top
    modelled apart) count only for closing the floor from above, never for the roof height.
    Parapet top: highest body point on the outer wall line of the top floor."""
    every = tris if extra is None or not len(extra) else np.vstack([tris, extra])
    p = v[every]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    length = np.linalg.norm(n, axis=1)
    ok = length > 0
    slope = np.full(len(p), 90.0)
    slope[ok] = np.degrees(np.arccos(np.clip(n[ok, 2] / length[ok], -1.0, 1.0)))
    zc = p[:, :, 2].mean(axis=1)
    level = top_level["elev_m"]
    where = f"level {top_level['name']} ({level} m)"
    floor_area = top_contour.area

    def inside(i):
        face = Polygon(p[i, :, :2])
        return face.area > 0 and face.intersection(top_contour).area >= 0.5 * face.area, face

    edge = top_contour.exterior
    pts = v[np.unique(tris)]
    on_edge = [z for (x, y, z) in pts if edge.distance(shapely.Point(x, y)) <= PARAPET_EDGE_M]
    parapet_top = max(on_edge) if on_edge else level

    def touches_edge(poly):                      # it starts at the outer wall line
        return edge.distance(poly) <= PARAPET_EDGE_M

    every_part = every if above is None or not len(above) else np.vstack([every, above])

    def lined(plan, z):
        """True when the inner edge of `plan` (not the outer wall line) is lined by vertical geometry
        at height z: the inner face of a parapet under a cap, the walls of a shaft under its top.
        An equipment top above the roof has no walls down there (PR #27 review 3)."""
        inner = plan.boundary.difference(edge.buffer(PARAPET_EDGE_M))
        if inner.length < 0.05:
            return False
        segs = _section(v, every_part, _clear_height(v, every_part, z))
        walls = shapely.unary_union(segs) if segs else LineString()
        return walls.intersection(inner.buffer(PARAPET_EDGE_M)).length >= SHAFT_WALL_SHARE * inner.length

    def surfaces_of(faces, vids):
        """Faces sharing vertices form one surface: (faces, area-weighted height, plan)."""
        sets = _Sets(len(faces))
        first = {}
        for k, ids in enumerate(vids):
            for vid in ids:
                if int(vid) in first:
                    sets.union(first[int(vid)], k)
                else:
                    first[int(vid)] = k
        groups = defaultdict(list)
        for k in range(len(faces)):
            groups[sets.find(k)].append(faces[k])
        out = []
        for members in groups.values():
            w = np.array([a for _, _, a, _ in members])
            z = float(np.dot([zz for _, _, _, zz in members], w) / w.sum())
            out.append((members, z, shapely.unary_union([f for _, f, _, _ in members])))
        return out

    near_flat, steep = [], 0.0
    for i in np.flatnonzero(ok & (n[:, 2] > 0) & (zc >= level - ROOF_SLOPE_BAND_M)):
        is_in, face = inside(i)
        if not is_in:
            continue
        if slope[i] <= ROOF_SLOPE_MAX_DEG:
            near_flat.append((i, face))
        elif slope[i] < 80.0 and zc[i] <= level + 1.5 and not (abs(zc[i] - parapet_top) <= 0.3 and touches_edge(face)):
            steep += float(length[i]) / 2
    if steep > ROOF_STEEP_SHARE * floor_area:
        raise SpecError(f"roof parts steeper than {ROOF_SLOPE_MAX_DEG:.0f} degrees cover {steep:.1f} m2 at {where}: "
                        "a pitched roof is not read automatically; ask the user")
    # Near-flat faces form surfaces; each surface has its own area-weighted height, and the roof is
    # the surfaces within ROOF_LEVEL_TOL_M of the input level. A surface is a cap, not roof, when it
    # starts at the outer edge, lies above another candidate and its inner edge is lined by a
    # parapet face down to it (structure, not a matching height: PR #27 review 3).
    faces = [(i, f, float(length[i]) / 2, float(zc[i])) for i, f in near_flat]
    surfaces = surfaces_of(faces, [every[i] for i, _ in near_flat])
    candidates = [c for c in surfaces if abs(c[1] - level) <= ROOF_LEVEL_TOL_M]

    def is_cap(c):
        lower = [o[1] for o in candidates if o[1] < c[1] - 0.01]
        return bool(lower) and touches_edge(c[2]) and lined(c[2], (c[1] + max(lower)) / 2)

    roof_surfaces = [c for c in candidates if not is_cap(c)] or candidates
    roof = [(i, f) for c in roof_surfaces for i, f, _, _ in c[0]]
    if not roof:
        nearby = sorted({round(c[1], 2) for c in surfaces})[:10]
        raise SpecError(f"no up-facing roof surface within {ROOF_LEVEL_TOL_M} m of {where}; "
                        f"near-flat surfaces at {nearby or 'none'} — check the roof level")
    idx = np.array([i for i, _ in roof])
    areas = length[idx] / 2
    roof_z = float((zc[idx] * areas).sum() / areas.sum())
    own = shapely.unary_union([f for _, f in roof]).intersection(top_contour).area / floor_area
    if own < ROOF_OWN:
        raise SpecError(f"roof at {roof_z:.3f} m covers only {own:.0%} of the top floor (< {ROOF_OWN:.0%}); "
                        f"surfaces above it at {sorted({round(c[1], 2) for c in surfaces if c[1] > level + ROOF_LEVEL_TOL_M})[:10]}"
                        " — roof or cap? ask the user")
    # The floor is closed by the roof and by surfaces above it whose inner edge is lined by walls
    # down to the roof (caps, shaft tops), in the body or as separate parts. Nothing below the roof
    # and no unsupported top (equipment) closes it (PR #27 reviews 1-3, P1).
    others = [c for c in surfaces if c not in roof_surfaces]
    if above is not None and len(above):
        q = v[above]
        qn = np.cross(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0])
        ql = np.linalg.norm(qn, axis=1)
        lid_faces, lid_vids = [], []
        for i in np.flatnonzero((ql > 0) & (qn[:, 2] >= np.cos(np.radians(ROOF_SLOPE_MAX_DEG)) * ql)
                                & (q[:, :, 2].mean(axis=1) > roof_z)):
            face = Polygon(q[i, :, :2])
            if face.area > 0 and face.intersection(top_contour).area >= 0.5 * face.area:
                lid_faces.append((i, face, float(ql[i]) / 2, float(q[i, :, 2].mean())))
                lid_vids.append(above[i])
        others += surfaces_of(lid_faces, lid_vids)
    closers = [f for _, f in roof] + [c[2] for c in others
                                      if c[1] > roof_z + 0.01 and lined(c[2], (c[1] + roof_z) / 2)]
    cover = shapely.unary_union(closers).intersection(top_contour)
    closed = cover.area / floor_area
    if closed < ROOF_CLOSED:
        raise SpecError(f"roof at {roof_z:.3f} m and the surfaces above it close only {closed:.0%} of the top "
                        f"floor (< {ROOF_CLOSED:.0%}): roof missing or open; ask the user")
    holes = [h for h in shapely.get_parts(top_contour.difference(cover)) if h.area >= HOLE_MIN_M2]
    if holes:
        # lined at mid storey and in the storey's upper part: walls that stop well below the roof
        # line nothing (PR #35 review 2, P1)
        cuts = [_clear_height(v, tris, below_level["elev_m"] + share * (roof_z - below_level["elev_m"]))
                for share in (0.5, SHAFT_UPPER)]
        sections = [shapely.unary_union(_section(v, tris, z) or [LineString()]) for z in cuts]
        for hole in holes:
            lined = min(w.intersection(hole.buffer(PARAPET_EDGE_M)).length for w in sections) / hole.exterior.length
            z_mid = cuts[0]
            if lined < SHAFT_WALL_SHARE:
                c = hole.centroid
                raise SpecError(f"roof at {roof_z:.3f} m has an opening of {hole.area:.2f} m2 at ({c.x:.2f}, {c.y:.2f}) "
                                f"that is not a shaft (walls line {lined:.0%} of it at {z_mid:.2f} m): "
                                "roof missing there? ask the user")
    # a parapet is structure, not a height difference (Codex review 2 of PR #54): there is none when the
    # roof surface itself runs out to the outer wall line and reaches the wall top there
    parapet = _has_parapet(edge, pts, p[idx])
    stats = {"parapet": parapet,
             "surface_z_min_m": round(float(p[idx][:, :, 2].min()), 3), "surface_z_max_m": round(float(p[idx][:, :, 2].max()), 3),
             "slope_max_deg": round(float(slope[idx].max()), 2),
             "slope_mean_deg": round(float((slope[idx] * areas).sum() / areas.sum()), 2)}
    return roof_z, parapet_top if on_edge else roof_z, round(closed, 3), stats


def _roof_parts(v, parts, top_level, top_contour):
    """Separate parts that are roof (#9, option (a)): their near-flat up-facing faces lie, on area
    average, within ROOF_LEVEL_TOL_M of the top level and at least half of them inside the top
    floor contour. A roof modelled as a separate object is normal."""
    out = []
    for part in parts:
        p = v[part]
        n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        length = np.linalg.norm(n, axis=1)
        flat = (length > 0) & (n[:, 2] >= np.cos(np.radians(ROOF_SLOPE_MAX_DEG)) * length)
        if not flat.any():
            continue
        a = length[flat] / 2
        z = float((p[flat][:, :, 2].mean(axis=1) * a).sum() / a.sum())
        faces = [Polygon(t[:, :2]) for t in p[flat]]
        plan = shapely.unary_union([f for f in faces if f.area > 0])
        if abs(z - top_level["elev_m"]) > ROOF_LEVEL_TOL_M or plan.area <= 0:
            continue
        inner = plan.intersection(top_contour).area
        outer = plan.area - inner
        if outer <= ROOF_PART_SLIVER_M2:
            out.append(part)
        elif inner > ROOF_PART_SLIVER_M2:
            c = plan.centroid
            raise SpecError(f"a separate part at the roof level ({z:.3f} m) lies {outer:.2f} m2 outside and {inner:.2f} m2 "
                            f"inside the top floor contour at ({c.x:.2f}, {c.y:.2f}): roof or not? ask the user")
    return out


def _glass(dump, m):
    """Vertical glass panes of meshes named *glass* (any case), each a connected part."""
    glass = {**dump, "meshes": [x for x in dump["meshes"] if "glass" in x["name"].lower()
                                and not x["name"].upper().startswith("UCX_") and x["triangles"]]}
    if not glass["meshes"]:
        return [], 0
    v, t = _mesh(glass, m)
    return op.vertical_parts(v, t, _parts(v, t))


def _plane_suspects(dump, m, levels, polys):
    """Separate flat vertical source objects (not glass) without an opening material id, small
    enough to be an opening plane and lying on a wall of their level: they may close a hole and hide
    an opening. Shape alone cannot prove it, so they become questions; the geometry is left as it
    is (PR #20 reviews 2-3, N8/R5/R8)."""
    out = []
    for mesh in dump["meshes"]:
        name = mesh["name"]
        if (name.upper().startswith("UCX_") or "glass" in name.lower() or not mesh["triangles"]
                or any(i in _opening_ids() for i in (mesh.get("material_ids") or []))):
            continue
        used = np.unique(np.asarray(mesh["triangles"], dtype=np.int64))      # referenced vertices only
        pts = _apply(m, np.asarray(mesh["vertices"], dtype=float)[used])
        centred = pts - pts.mean(axis=0)
        sv = np.linalg.svd(centred, full_matrices=False)
        normal, flatness = sv[2][-1], sv[1][-1]
        size = np.ptp(pts, axis=0)
        if (flatness > 1e-6 * max(len(pts), 1) or abs(normal[2]) > 0.5
                or max(size[0], size[1]) > op.OPENING_MAX_M or size[2] > 4.0):
            continue
        zc = float(pts[:, 2].mean())
        li = next((i for i in range(len(levels) - 1) if levels[i]["elev_m"] <= zc < levels[i + 1]["elev_m"]), None)
        c = pts.mean(axis=0)
        if li is None or polys[li].exterior.distance(shapely.Point(c[0], c[1])) > op.ON_WALL_M + 0.25:
            continue                                  # not on a wall of a storey: an attachment, not a plane
        out.append({"priority": "high", "kind": "flat-object-in-wall", "levels": [levels[li]["name"]],
                    "wall": None, "depth_m": None, "length_m": round(float(max(size[0], size[1])), 3),
                    "facade_share": None, "heights_m": [round(float(pts[:, 2].min()), 3), round(float(pts[:, 2].max()), 3)],
                    "at": [round(float(c[0]), 2), round(float(c[1]), 2)]})
    return out


def _planes(v, tris):
    """Vertical opening planes (faces with an opening material id), each with its material id."""
    if not len(tris):
        return []
    out = []
    for part in _parts(v, tris[:, :3]):
        found, _ = op.vertical_parts(v, tris[:, :3], [part])
        if found:
            pts, normal = found[0]
            ids = set(tris[part, 3].tolist())
            out.append((pts, normal, ids.pop() if len(ids) == 1 else None))   # mixed ids: no id is invented
    return out


def extract_spec(dump, obj_cfg, profile="npm_min", thresholds=None):
    """Return (Spec, report) for one building. dump: measure_spec_blender output; obj_cfg: object.json;
    thresholds: the `spec_extract` section of a benchmark's tolerances.json (defaults in openings.py)."""
    m = _matrix(obj_cfg, dump.get("source"))
    levels = _levels(dump, obj_cfg, m)
    if dump.get("kind") == "revit-data":                 # the box route of #10, removed after #29
        raise SpecError("revit-data (bounding boxes, #10) is no longer read; export with "
                        "tools/source/measure_spec_revit_twin.mjs and pass its twin-data.json (#29)")
    v, tris, mats, owners = _mesh(dump, m, with_materials=True)
    plane = np.isin(mats, list(_opening_ids()))        # opening planes are not body: the hole stays the anchor
    plane_tris = np.column_stack([tris[plane], mats[plane]])
    tris, owners = tris[~plane], owners[~plane]
    if dump.get("body"):                                 # a source that names its body (Revit boxes do
        mine = np.isin(owners, list(dump["body"]))      # not share vertices): body = those meshes
        parts = [np.flatnonzero(mine)] + _parts(v, tris[~mine]) if (~mine).any() else [np.flatnonzero(mine)]
        if len(parts) > 1:
            rest = np.flatnonzero(~mine)
            parts = [parts[0]] + [rest[pt] for pt in parts[1:]]
    else:
        parts = _parts(v, tris)
    body = tris[parts[0]]
    report = {"parts": len(parts), "body_triangles": int(len(body)),
              "body_area_m2": round(float(_areas(v, body).sum()), 3),
              "attachment_parts_ignored": len(parts) - 1, "floors": {}}
    floors, polys, pieces, mouths, doors = [], [], [], [], []
    at_m = obj_cfg.get("contour_at_m", {})
    for lv, nxt in zip(levels, levels[1:]):
        poly, rep, dev, ms, dr = _level_contour(v, body, lv["elev_m"], nxt["elev_m"], lv["name"], at_m.get(lv["name"]),
                                                below=polys[-1] if polys else None,
                                                extra=np.vstack([tris[pt] for pt in parts[1:]]) if len(parts) > 1 else None)
        mouths.append(ms)
        doors.append(dr)
        rep["area_m2"] = round(poly.area, 3)
        report["floors"][lv["name"]] = rep
        floors.append({"level": lv["name"], "contour": _contour_points(poly), "openings": []})
        polys.append(poly)
        pieces.append(dev)
    panes, flat_glass = _glass(dump, m)
    source_skipped, sources = 0, [[] for _ in floors]
    for d in dump.get("openings", []):                   # openings a source gives explicitly (Revit, #29, #36)
        q0, q1 = _apply(m, [[*d["p0"], d["z0"]], [*d["p1"], d["z1"]]])
        li = next((i for i in range(len(floors)) if levels[i]["elev_m"] - op.LEVEL_JOINT_M <= q0[2]
                   < levels[i + 1]["elev_m"] - op.LEVEL_JOINT_M), None)
        run = q1[:2] - q0[:2]
        if li is None or np.linalg.norm(run) < 1e-6:
            source_skipped += 1
            continue
        _, _, u, _ = op._wall_frame(floors[li]["contour"], (q0[:2] + q1[:2]) / 2)
        # a door is on the facade when both its ends lie within half its host's thickness of the
        # contour (PR #35 review 2); a glazed frame (curtain wall) may sit behind the facade face
        reach = (d.get("host_thickness") or 0.0) / 2 + DOOR_HOST_M if d["kind"] == "door" else op.PANE_WALL_M
        if (abs(float(u @ run)) / float(np.linalg.norm(run)) < np.cos(np.radians(op.ALONG_DEG))
                or max(polys[li].exterior.distance(shapely.Point(*q[:2])) for q in (q0, q1)) > reach):
            source_skipped += 1                          # not a facade opening
            continue
        glass = []
        for g in d.get("glass", []):
            g0, g1 = _apply(m, [[g[0], g[1], g[4]], [g[2], g[3], g[5]]])
            glass.append((float(g0[0]), float(g0[1]), float(g1[0]), float(g1[1]), float(g0[2]), float(g1[2])))
        sources[li].append({"p0": q0[:2], "p1": q1[:2], "z0": float(q0[2]), "z1": float(q1[2]), "depth": d["depth"],
                            "kind": d["kind"], "glass": glass, "panes": d.get("panes"), "glazed": d.get("glazed")})
    recesses = [[pc for pc in pcs if pc["kind"] == "recess"] for pcs in pieces]
    per_floor, footprints, breaks, glass_report = op.assemble(levels, floors, polys, mouths, panes,
                                                              _planes(v, plane_tris), doors, recesses, sources,
                                                              obj_cfg.get("opening_depth_default_m", 0.2), thresholds)
    cleared = 0
    for li, floor in enumerate(floors):
        floor["openings"] = per_floor[li]
        kept = [pc for pc in pieces[li] if not (pc["kind"] == "recess" and op.is_opening_recess(pc, li, footprints))]
        cleared += len(pieces[li]) - len(kept)
        pieces[li] = kept
    report["openings"] = {"count": sum(len(f["openings"]) for f in floors), **glass_report,
                          "source_openings_skipped": source_skipped,
                          "horizontal_glass_parts": flat_glass, "recesses_cleared_as_openings": cleared}
    suspects = _plane_suspects(dump, m, levels, polys)
    report["openings"]["planes_without_material_id"] = len(suspects)
    stats = {"section_relief_parts": 0}
    questions = (_questions(levels, floors, polys, pieces, stats) + op.break_questions(breaks, levels) + suspects
                 + _source_questions(dump, levels))
    for name, rep in report["floors"].items():        # structure on a ledge that is no terrace (review 1 of PR #61)
        if "ledge_structure" in rep:
            q = rep["ledge_structure"]
            questions.append({"priority": "high", "kind": "ledge-structure", "levels": [name], "wall": None,
                              "depth_m": None, "length_m": None, "facade_share": None,
                              "heights_m": q["heights_m"], "at": q["at"]})
    names = [lv["name"] for lv in levels]
    questions.sort(key=lambda q: (q["priority"] != "high", names.index(q["levels"][0]), q["kind"]))
    for n, q in enumerate(questions, 1):
        q["n"] = n
    report["questions"] = questions
    report["section_relief_parts"] = stats["section_relief_parts"]
    others = [tris[pt] for pt in parts[1:]]
    roof_parts = _roof_parts(v, others, levels[-1], polys[-1])
    roof_z, top_z, closed, roof_stats = _roof(v, body, levels[-2], levels[-1], polys[-1],
                                              np.vstack(roof_parts) if roof_parts else None,
                                              np.vstack(others) if others else None)
    report["roof"] = {"plane_m": round(roof_z, 3), "parapet_top_m": round(top_z, 3), "closed_share": closed,
                      "separate_roof_parts": len(roof_parts), **roof_stats,
                      "top_level": levels[-1]["name"], "top_level_m": levels[-1]["elev_m"],
                      "plane_vs_top_level_m": round(roof_z - levels[-1]["elev_m"], 3)}
    written, report["floor_classes"] = fl.collapse(levels, floors)
    terraces = [{"level": n, "parapet_h_m": rep["terrace"]["parapet_h_m"]}
                for n, rep in report["floors"].items() if "terrace" in rep]
    # inset plates (pattern roof-inset-plane, user 2026-10-10): plate_gap_m / plate_overlap_m are building
    # parameters read from the source; plates that disagree by more than PLATE_SAME_M between themselves,
    # or that cannot be read, are a question; none read leaves the defaults (review 1 of PR #64)
    extra = np.vstack(others) if others else None
    plates, problems = {}, {}
    if roof_stats["parapet"]:
        plates[levels[-1]["name"]], problems[levels[-1]["name"]] = _plate_params(
            v, body, extra, levels[-1]["elev_m"], polys[-1])
    for t in terraces:
        k = names.index(t["level"])
        plates[t["level"]], problems[t["level"]] = _plate_params(
            v, body, extra, levels[k]["elev_m"], polys[k - 1].difference(polys[k]))
    measured = [p for ps in plates.values() for p in ps]
    report["plates"] = {name: {"plates": [{"gap_m": round(g, 4), "overlap_m": round(o, 4)} for g, o in ps],
                               "problems": problems[name]} for name, ps in plates.items()}
    plate = {}
    asked = sorted({name for name, pr in problems.items() if pr}, key=names.index)
    if measured:
        gaps, overlaps = [g for g, _ in measured], [o for _, o in measured]
        plate = {"plate_gap_m": round(float(np.median(gaps)), 4),
                 "plate_overlap_m": round(float(np.median(overlaps)), 4)}
        if max(gaps) - min(gaps) > PLATE_SAME_M or max(overlaps) - min(overlaps) > PLATE_SAME_M:
            asked = sorted(set(asked) | {name for name, ps in plates.items() if ps}, key=names.index)
    if asked:
        questions.append({"priority": "high", "kind": "plate-params", "levels": asked, "wall": None,
                          "depth_m": None, "length_m": None, "facade_share": None, "heights_m": None, "at": None})
        questions.sort(key=lambda q: (q["priority"] != "high", names.index(q["levels"][0]), q["kind"]))
        for n, q in enumerate(questions, 1):
            q["n"] = n
    spec = Spec(id=obj_cfg["id"], profile=profile,
                frame={"object": obj_cfg["id"], "source": dump.get("source", "?"), "to_object": m.tolist()},
                # the parapet is measured from the input roof level, never from the roof plane: an inset
                # roof plane (pattern roof-inset-plane, user rule 2026-10-10) sets no height; a roof whose
                # surface reaches the wall top at the outer wall line has no parapet (reviews of PR #54)
                levels=levels, floors=written,
                roof={"parapet_h_m": round(max(top_z - levels[-1]["elev_m"], 0.0), 3) if roof_stats["parapet"] else 0.0},
                # pattern terrace (user plan 2026-10-10): a terrace parapet read from the storey's sections
                **({"spec_version": "0.4", "terraces": terraces} if terraces else {}),
                opening_depth_default_m=obj_cfg.get("opening_depth_default_m", 0.2), **plate)
    return spec, report

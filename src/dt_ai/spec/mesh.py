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

from dt_ai.spec.model import Spec

LEVEL_PREFIX = "LEVEL_"
SAME_CONTOUR_M = 0.005    # sections closer than this (Hausdorff) are one contour; < the 1 cm acceptance
WELD_M = 1e-4             # vertices closer than WELD_M / 2 on every axis are always welded
SIMPLIFY_M = 0.0005       # numeric noise only; kinks and arcs are decided by angle below
KINK_DEG = 5.0            # a facade kink is a turn over 5 degrees (HARNESS_PLAN §3)
ARC_TURN_MAX_DEG = 15.0   # arc tessellation turns at most this per vertex (>= 6 segments per quarter)
ARC_MIN_VERTICES = 3
ARC_MIN_TURN_DEG = 20.0
ARC_FIT_M = 0.005         # arc points and both walls must fit one circle within 5 mm + 0.5 % of r
ARC_FIT_SHARE = 0.005
EVENT_MIN_M = 0.001       # thinner height intervals between vertex heights are not cut
SHARE_TOL_M = 0.005       # a piece shares a wall when its boundary lies within 5 mm of it
PRIORITY_SHARE = 0.10     # question priority high: >= 2 levels or > 10 % of the facade length
ROOF_LEVEL_TOL_M = 0.03   # roof plane vs the top input level: the level tolerance of HARNESS_PLAN §5
ROOF_SEARCH_M = 0.3       # only to name nearby surfaces in the error message
ROOF_OWN = 0.25           # share of the top floor the roof plane itself must cover (else roof or cap?)
HOLE_MIN_M2 = 0.01        # uncovered pieces of the top floor smaller than this are numeric slivers
SHAFT_WALL_SHARE = 0.9    # a roof hole is a shaft when body walls line this share of its edge at mid top storey
ROOF_CLOSED = 0.9         # share of the top floor the roof and surfaces above it must close
PARAPET_EDGE_M = 0.05     # parapet top is read only on the outer wall line of the top floor


class SpecError(ValueError):
    pass


def _matrix(obj_cfg):
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


def _mesh(dump, m):
    """All non-collision triangles in object coordinates, vertices welded by position."""
    verts, tris, base = [], [], 0
    for mesh in dump["meshes"]:
        if mesh["name"].upper().startswith("UCX_") or not mesh["triangles"]:
            continue
        verts.append(_apply(m, mesh["vertices"]))
        tris.append(np.asarray(mesh["triangles"], dtype=np.int64) + base)
        base += len(mesh["vertices"])
    if not tris:
        raise SpecError("the source holds no mesh triangles")
    v = np.vstack(verts)
    rep = _weld(v)
    used, inverse = np.unique(rep, return_inverse=True)
    t = inverse.ravel()[np.vstack(tris)]
    if np.linalg.det(m[:3, :3]) < 0:  # a mirroring frame flips facing; restore outward normals
        t = t[:, ::-1]
    return v[used], t


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


def _section(v, tris, z):
    """Segments where the plane z cuts the triangles."""
    p = v[tris]
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


def _outer(segments):
    """Outer boundary of the closed rings formed by the segments, or None if nothing closes."""
    if not segments:
        return None
    noded = shapely.unary_union(MultiLineString(segments))
    polys = list(shapely.get_parts(shapely.polygonize(shapely.get_parts(noded))))
    if not polys:
        return None
    biggest = max(shapely.get_parts(shapely.unary_union(polys)), key=lambda g: g.area)
    return Polygon(biggest.exterior)


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
    """Height intervals of the storey between consecutive vertex heights: inside one interval every
    horizontal section has the same shape, so one cut per interval sees every element exactly."""
    zs = np.unique(np.round(v[np.unique(tris), 2], 6))
    cuts = [z0] + [float(z) for z in zs if z0 < z < z1] + [z1]
    return [(a, b) for a, b in zip(cuts, cuts[1:]) if b - a > EVENT_MIN_M]


def _deviations(groups, contour):
    """Pieces where other section shapes of the storey differ from its contour (not full height)."""
    pieces = []
    for g in groups:
        for kind, diff in (("projection", g["poly"].difference(contour)), ("recess", contour.difference(g["poly"]))):
            for part in shapely.get_parts(diff):
                if part.is_empty:
                    continue
                far = max(contour.exterior.distance(shapely.Point(xy)) for xy in part.exterior.coords)
                if far >= SAME_CONTOUR_M:
                    pieces.append({"kind": kind, "geom": part, "spans": list(g["spans"])})
    return pieces


def _level_contour(v, tris, z0, z1, name):
    """Level contour = walls over the full storey height (user decision 2026-10-08): the section shape
    found at both ends of the storey. If the ends differ (a plinth at the bottom), the shape over the
    taller end shape is used; a contour-choice question is raised when it covers under half the storey.
    Frequency decides nothing."""
    spans = _spans(v, tris, z0, z1)
    closed = [(a, b, poly) for a, b in spans if (poly := _outer(_section(v, tris, (a + b) / 2))) is not None]
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
    if len(groups) == 1:
        base, rule = groups[0], "single shape"
    elif bottom is top:
        base, rule = bottom, "both storey ends"
    else:  # e.g. a plinth at the bottom: the taller of the two end shapes; ask if it is under half the storey
        base = max((bottom, top), key=lambda g: g["height"])
        rule = "taller storey end" if base["height"] >= 0.5 * (z1 - z0) else "unclear: storey ends differ"
    report = {"sections": len(spans), "closed_sections": len(closed), "contour_rule": rule,
              "contour_height_share": round(base["height"] / (z1 - z0), 3), "other_contours": len(groups) - 1}
    return base["poly"], report, _deviations([g for g in groups if g is not base], base["poly"])


def _measure(piece, contour_pts):
    """Bind a piece to the contour wall it shares most boundary with; measure along and across it."""
    pts = np.array([q[:2] for q in contour_pts], dtype=float)
    best = None
    for w in range(len(pts)):
        shared = piece["geom"].boundary.intersection(LineString([pts[w], pts[(w + 1) % len(pts)]]).buffer(SHARE_TOL_M))
        if best is None or shared.length > best[1].length:
            best = (w, shared)
    w, shared = best
    a, b = pts[w], pts[(w + 1) % len(pts)]
    u = (b - a) / np.linalg.norm(b - a)
    coords = np.array([xy for g in shapely.get_parts(piece["geom"]) for xy in g.exterior.coords])
    along_pts = np.array([xy for g in shapely.get_parts(shared) for xy in g.coords]) if shared.length > 0 else coords
    along = (along_pts - a) @ u
    length = float(along.max() - along.min())
    depth = max(_line_distance(xy, a, b) for xy in coords)
    return {"wall": w, "length_m": length, "depth_m": depth, "facade_share": length / float(np.linalg.norm(b - a))}


def _questions(levels, floors, pieces_by_level, rules):
    """Merge pieces into connected components across levels and turn them into questions."""
    items = []
    for li, pieces in enumerate(pieces_by_level):
        for p in pieces:
            items.append({**p, **_measure(p, floors[li]["contour"]), "levels": {li}})
    sets = _Sets(len(items))
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i]["kind"] == items[j]["kind"] and items[i]["geom"].buffer(0.01).intersects(items[j]["geom"]):
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
        whole = _measure({"geom": union}, floors[min(main["levels"])]["contour"])
        share = max(whole["facade_share"], *(p["facade_share"] for p in comp))
        c = union.centroid
        out.append({"priority": "high" if len(lv) >= 2 or share > PRIORITY_SHARE else "normal",
                    "kind": main["kind"], "levels": lv, "wall": main["wall"],
                    "depth_m": round(max(p["depth_m"] for p in comp), 3), "length_m": round(whole["length_m"], 3),
                    "facade_share": round(share, 4),
                    "heights_m": [round(min(a for a, _ in spans), 3), round(max(b for _, b in spans), 3)],
                    "at": [round(c.x, 2), round(c.y, 2)]})
    for li, rule in enumerate(rules):
        if rule.startswith("unclear"):
            out.append({"priority": "high", "kind": "contour-choice", "levels": [names[li]], "wall": None,
                        "depth_m": None, "length_m": None, "facade_share": None, "heights_m": None, "at": None})
    out.sort(key=lambda q: (q["priority"] != "high", names.index(q["levels"][0]), q["kind"]))
    for n, q in enumerate(out, 1):
        q["n"] = n
    return out


def questions_markdown(spec_id, questions):
    """The object's questions file: everything not over the full storey height (HARNESS_PLAN §4)."""
    lines = [f"# Questions — {spec_id}", "",
             "Written by the spec extractor. Each row is geometry that is not over the full storey height,",
             "so it does not change the level contour (user decision 2026-10-08). Priority high = through",
             "2 or more levels or over 10 % of the facade length. Heights are the exact height interval of",
             "the element. A recess at window height may be an opening (separated by issue #7).",
             "`contour-choice`: the storey ends differ and neither shape covers half the storey height.", "",
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


def _roof(v, tris, below_level, top_level, top_contour):
    """The roof level is input, like every level; geometry only confirms it (issue #16).
    Roof plane: an up-facing horizontal body surface inside the top floor contour within
    ROOF_LEVEL_TOL_M of the top input level; it must itself cover ROOF_OWN of the top floor (a
    patch under a wide cap is "roof or cap?"), and with every up-facing surface above it (cap,
    shaft tops) close ROOF_CLOSED of it, else the roof is missing. Several candidate planes, or
    none, is a question for the user, never a guess. An uncovered hole is allowed only as a shaft:
    body walls line its edge at mid top storey; a hole with no walls below is a missing roof
    (user decision 2026-10-08, PR #18 review 3). Parapet top: highest body point on the outer wall line
    of the top floor."""
    p = v[tris]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    length = np.linalg.norm(n, axis=1)
    up = (length > 0) & (n[:, 2] > 0.999 * length)
    planes = defaultdict(list)
    for tri in p[up]:
        face = Polygon(tri[:, :2])
        if face.area > 0 and face.intersection(top_contour).area >= 0.5 * face.area:
            planes[round(float(tri[0, 2]), 3)].append(face)
    level = top_level["elev_m"]
    found = sorted(z for z in planes if abs(z - level) <= ROOF_LEVEL_TOL_M)
    where = f"level {top_level['name']} ({level} m)"
    if not found:
        near = sorted(z for z in planes if abs(z - level) <= ROOF_SEARCH_M)
        raise SpecError(f"no up-facing roof surface within {ROOF_LEVEL_TOL_M} m of {where}; "
                        f"horizontal surfaces within {ROOF_SEARCH_M} m: {near or 'none'} — check the roof level")
    if len(found) > 1:
        raise SpecError(f"ambiguous roof at {where}: planes {found}; ask the user")
    roof_z = found[0]
    own = shapely.unary_union(planes[roof_z]).intersection(top_contour).area / top_contour.area
    if own < ROOF_OWN:
        raise SpecError(f"roof plane at {roof_z} m covers only {own:.0%} of the top floor (< {ROOF_OWN:.0%}); "
                        f"planes above it: {sorted(z for z in planes if z > roof_z)} — roof or cap? ask the user")
    closing = [f for z, faces in planes.items() if z >= roof_z - 1e-3 for f in faces]
    cover = shapely.unary_union(closing).intersection(top_contour)
    closed = cover.area / top_contour.area
    if closed < ROOF_CLOSED:
        raise SpecError(f"roof at {roof_z} m and the surfaces above it close only {closed:.0%} of the top "
                        f"floor (< {ROOF_CLOSED:.0%}): roof missing or open; ask the user")
    holes = [h for h in shapely.get_parts(top_contour.difference(cover)) if h.area >= HOLE_MIN_M2]
    if holes:
        z_mid = _clear_height(v, tris, (below_level["elev_m"] + roof_z) / 2)
        walls = shapely.unary_union(_section(v, tris, z_mid) or [LineString()])
        for hole in holes:
            lined = walls.intersection(hole.buffer(PARAPET_EDGE_M)).length / hole.exterior.length
            if lined < SHAFT_WALL_SHARE:
                c = hole.centroid
                raise SpecError(f"roof at {roof_z} m has an opening of {hole.area:.2f} m2 at ({c.x:.2f}, {c.y:.2f}) "
                                f"that is not a shaft (walls line {lined:.0%} of it at {z_mid:.2f} m): "
                                "roof missing there? ask the user")
    edge = top_contour.exterior
    pts = v[np.unique(tris)]
    on_edge = [z for (x, y, z) in pts if edge.distance(shapely.Point(x, y)) <= PARAPET_EDGE_M]
    return roof_z, max(on_edge) if on_edge else roof_z, round(closed, 3)


def extract_spec(dump, obj_cfg, profile="npm_min"):
    """Return (Spec, report) for one building. dump: measure_spec_blender output; obj_cfg: object.json."""
    m = _matrix(obj_cfg)
    levels = _levels(dump, obj_cfg, m)
    v, tris = _mesh(dump, m)
    parts = _parts(v, tris)
    body = tris[parts[0]]
    report = {"parts": len(parts), "body_triangles": int(len(body)),
              "body_area_m2": round(float(_areas(v, body).sum()), 3),
              "attachment_parts_ignored": len(parts) - 1, "floors": {}}
    floors, polys, pieces, rules = [], [], [], []
    for lv, nxt in zip(levels, levels[1:]):
        poly, rep, dev = _level_contour(v, body, lv["elev_m"], nxt["elev_m"], lv["name"])
        rep["area_m2"] = round(poly.area, 3)
        report["floors"][lv["name"]] = rep
        floors.append({"level": lv["name"], "contour": _contour_points(poly), "openings": []})
        polys.append(poly)
        pieces.append(dev)
        rules.append(rep["contour_rule"])
    report["questions"] = _questions(levels, floors, pieces, rules)
    roof_z, top_z, closed = _roof(v, body, levels[-2], levels[-1], polys[-1])
    report["roof"] = {"plane_m": round(roof_z, 3), "parapet_top_m": round(top_z, 3), "closed_share": closed,
                      "top_level": levels[-1]["name"], "top_level_m": levels[-1]["elev_m"],
                      "plane_vs_top_level_m": round(roof_z - levels[-1]["elev_m"], 3)}
    spec = Spec(id=obj_cfg["id"], profile=profile,
                frame={"object": obj_cfg["id"], "source": dump.get("source", "?"), "to_object": m.tolist()},
                levels=levels, floors=floors, roof={"parapet_h_m": round(max(top_z - roof_z, 0.0), 3)})
    return spec, report

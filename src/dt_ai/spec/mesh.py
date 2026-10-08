"""Spec from a mesh dump (tools/source/measure_spec_blender.py). Pure Python; never run in Blender.

Body = connected part with the largest surface area. Level contour = outer boundary of the body
cut by horizontal planes inside the storey; the modal closed section wins, so cuts through
openings (open rings) do not decide it, and a storey with no closed section is an error, not a
guess. Levels are input (LEVEL_<name> helpers or the object's levels from Revit), never guessed;
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
SECTION_STEP_M = 0.25
SECTION_OFFSET_M = 0.137  # keeps cuts off whole-number grid heights of hand-made etalons
SAME_CONTOUR_M = 0.005    # sections closer than this (Hausdorff) are one contour; < the 1 cm acceptance
WELD_M = 1e-4             # vertices closer than WELD_M / 2 on every axis are always welded
SIMPLIFY_M = 0.005
ROOF_SEARCH_M = 0.3       # the roof plane must lie within this of the top input level
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
    within WELD_M / 2 on every axis share a cell in at least one grid."""
    sets = _Sets(len(v))
    for shift in product((0.0, 0.5), repeat=3):
        keys = np.floor(v / WELD_M + np.asarray(shift)).astype(np.int64)
        _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
        for i, j in zip(range(len(v)), first[inverse.ravel()]):
            if i != j:
                sets.union(int(j), i)
    return np.array([sets.find(i) for i in range(len(v))])


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
    return v[used], inverse.ravel()[np.vstack(tris)]


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


def _contour_points(poly):
    poly = orient(poly.simplify(SIMPLIFY_M, preserve_topology=True), sign=1.0)
    pts = [(round(x, 3) + 0.0, round(y, 3) + 0.0) for x, y in list(poly.exterior.coords)[:-1]]
    start = min(range(len(pts)), key=lambda i: (pts[i][1], pts[i][0]))
    return [list(p) for p in pts[start:] + pts[:start]]


def _level_contour(v, tris, z0, z1, name):
    heights = [_clear_height(v, tris, float(z))
               for z in (np.arange(z0 + SECTION_OFFSET_M, z1, SECTION_STEP_M) if z1 - z0 > SECTION_OFFSET_M
                         else [(z0 + z1) / 2])]
    closed = [(z, poly) for z in heights if (poly := _outer(_section(v, tris, z))) is not None]
    if not closed:
        raise SpecError(f"level {name}: none of {len(heights)} body sections between {z0} and {z1} m "
                        "closes; the contour is not invented (ask the user, HARNESS_PLAN §7 gray zone)")
    groups = []
    for z, poly in closed:
        for g in groups:
            if g[0][1].hausdorff_distance(poly) < SAME_CONTOUR_M:
                g.append((z, poly))
                break
        else:
            groups.append([(z, poly)])
    best = max(groups, key=len)
    medoid = min(best, key=lambda a: sum(a[1].hausdorff_distance(b[1]) for b in best))
    return medoid[1], {"sections": len(heights), "closed_sections": len(closed),
                       "modal_sections": len(best), "other_contours": len(groups) - 1,
                       "contour_height_m": round(medoid[0], 3)}


def _roof(v, tris, top_level, top_contour):
    """Roof plane: horizontal body area nearest to the top input level; parapet top: highest body
    point on the outer wall line of the top floor. Missing roof geometry is an error."""
    p = v[tris]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    length = np.linalg.norm(n, axis=1)
    flat = (length > 0) & (np.abs(n[:, 2]) > 0.999 * length)
    z_flat = p[flat, 0, 2]
    near = np.abs(z_flat - top_level["elev_m"]) <= ROOF_SEARCH_M
    if not near.any():
        raise SpecError(f"no horizontal roof surface within {ROOF_SEARCH_M} m of level "
                        f"{top_level['name']} ({top_level['elev_m']} m)")
    weight = defaultdict(float)
    for z, a in zip(np.round(z_flat[near], 3), length[flat][near] / 2):
        weight[float(z)] += float(a)
    roof_z = max(weight, key=weight.get)
    edge = top_contour.exterior
    pts = v[np.unique(tris)]
    on_edge = [z for (x, y, z) in pts if edge.distance(shapely.Point(x, y)) <= PARAPET_EDGE_M]
    top_z = max(on_edge) if on_edge else roof_z
    return roof_z, top_z


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
    floors, polys = [], []
    for lv, nxt in zip(levels, levels[1:]):
        poly, rep = _level_contour(v, body, lv["elev_m"], nxt["elev_m"], lv["name"])
        rep["area_m2"] = round(poly.area, 3)
        report["floors"][lv["name"]] = rep
        floors.append({"level": lv["name"], "contour": _contour_points(poly), "openings": []})
        polys.append(poly)
    roof_z, top_z = _roof(v, body, levels[-1], polys[-1])
    report["roof"] = {"plane_m": round(roof_z, 3), "parapet_top_m": round(top_z, 3),
                      "top_level": levels[-1]["name"], "top_level_m": levels[-1]["elev_m"],
                      "plane_vs_top_level_m": round(roof_z - levels[-1]["elev_m"], 3)}
    spec = Spec(id=obj_cfg["id"], profile=profile,
                frame={"object": obj_cfg["id"], "source": dump.get("source", "?"), "to_object": m.tolist()},
                levels=levels, floors=floors, roof={"parapet_h_m": round(max(top_z - roof_z, 0.0), 3)})
    return spec, report

"""Spec from a mesh dump (tools/source/measure_spec_blender.py). Pure Python; never run in Blender.

Body = largest connected part. Level contour = outer boundary of the body cut by horizontal
planes inside the storey; the modal closed section wins, so cuts through openings (open rings)
and odd heights do not decide it. Levels are input (LEVEL_<name> helpers or the object's
levels from Revit), never guessed. Decisions: docs/HARNESS_PLAN.md §3-§4 (2026-10-08).
"""
from collections import Counter

import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.geometry.polygon import orient

from dt_ai.spec.model import Spec

LEVEL_PREFIX = "LEVEL_"
SECTION_STEP_M = 0.25
SECTION_OFFSET_M = 0.137  # keeps cuts off whole-number grid heights of hand-made etalons
SAME_CONTOUR_M = 0.02     # two sections with Hausdorff distance below this are one contour
WELD_M = 1e-4
SIMPLIFY_M = 0.005


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
    key, inverse = np.unique(np.round(v / WELD_M).astype(np.int64), axis=0, return_inverse=True)
    welded = np.zeros((len(key), 3))
    welded[inverse.ravel()] = v
    return welded, inverse.ravel()[np.vstack(tris)]


def _parts(n_verts, tris):
    """Connected parts as arrays of triangle indices, largest first."""
    parent = np.arange(n_verts)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b, c in tris:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(rc)] = ra
    roots = np.array([find(t[0]) for t in tris])
    groups = {}
    for i, r in enumerate(roots):
        groups.setdefault(int(r), []).append(i)
    return sorted((np.array(g) for g in groups.values()), key=len, reverse=True)


def _section(v, tris, z):
    """Segments where the plane z cuts the triangles."""
    p = v[tris]                                      # (n, 3, 3)
    d = p[:, :, 2] - z
    cut = (d.min(axis=1) < 0) & (d.max(axis=1) > 0)
    segments = []
    for tri, dist in zip(p[cut], d[cut]):
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if (dist[i] < 0) != (dist[j] < 0):
                t = dist[i] / (dist[i] - dist[j])
                pts.append(tri[i, :2] + t * (tri[j, :2] - tri[i, :2]))
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
    merged = shapely.unary_union(polys)
    biggest = max(shapely.get_parts(merged), key=lambda g: g.area)
    return Polygon(biggest.exterior)


def _contour_points(poly):
    poly = orient(poly.simplify(SIMPLIFY_M, preserve_topology=True), sign=1.0)
    pts = [(round(x, 3) + 0.0, round(y, 3) + 0.0) for x, y in list(poly.exterior.coords)[:-1]]
    start = min(range(len(pts)), key=lambda i: (pts[i][1], pts[i][0]))
    return [list(p) for p in pts[start:] + pts[:start]]


def _level_contour(v, tris, z0, z1):
    heights = list(np.arange(z0 + SECTION_OFFSET_M, z1, SECTION_STEP_M)) or [(z0 + z1) / 2]
    closed = [(z, poly) for z in heights if (poly := _outer(_section(v, tris, z))) is not None]
    report = {"sections": len(heights), "closed_sections": len(closed)}
    if not closed:
        poly = _outer([s for z in heights for s in _section(v, tris, z)])
        if poly is None:
            raise SpecError(f"no closed body section between {z0} and {z1}")
        report["fallback"] = "union of all sections"
        return poly, report
    groups = []
    for z, poly in closed:
        for g in groups:
            if g[0][1].hausdorff_distance(poly) < SAME_CONTOUR_M:
                g.append((z, poly))
                break
        else:
            groups.append([(z, poly)])
    best = max(groups, key=len)
    report.update(modal_sections=len(best), other_contours=len(groups) - 1,
                  modal_heights_m=[round(float(z), 3) for z, _ in best])
    return best[0][1], report


def _roof(v, tris, levels):
    """Roof plane = horizontal body area of largest extent above the first level; parapet to the top."""
    p = v[tris]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area = np.linalg.norm(n, axis=1) / 2
    flat = (area > 0) & (np.abs(n[:, 2]) > 0.999 * np.linalg.norm(n, axis=1))
    zs = np.round(p[flat, 0, 2], 2)
    weight = Counter()
    for z, a in zip(zs, area[flat]):
        if z > levels[0]["elev_m"] + 0.1:
            weight[float(z)] += float(a)
    top = float(v[np.unique(tris), 2].max())
    if not weight:
        return top, top
    return max(weight, key=weight.get), top


def extract_spec(dump, obj_cfg, profile="npm_min"):
    """Return (Spec, report) for one building. dump: measure_spec_blender output; obj_cfg: object.json."""
    m = _matrix(obj_cfg)
    levels = _levels(dump, obj_cfg, m)
    v, tris = _mesh(dump, m)
    parts = _parts(len(v), tris)
    body = tris[parts[0]]
    report = {"parts": len(parts), "body_triangles": int(len(body)),
              "attachment_parts_ignored": len(parts) - 1, "floors": {}}
    floors = []
    for lv, nxt in zip(levels, levels[1:]):
        poly, rep = _level_contour(v, body, lv["elev_m"], nxt["elev_m"])
        rep["area_m2"] = round(poly.area, 3)
        report["floors"][lv["name"]] = rep
        floors.append({"level": lv["name"], "contour": _contour_points(poly), "openings": []})
    roof_z, top_z = _roof(v, body, levels)
    report["roof"] = {"plane_m": round(roof_z, 3), "top_m": round(top_z, 3),
                      "top_level": levels[-1]["name"], "top_level_m": levels[-1]["elev_m"],
                      "plane_vs_top_level_m": round(roof_z - levels[-1]["elev_m"], 3)}
    spec = Spec(id=obj_cfg["id"], profile=profile,
                frame={"object": obj_cfg["id"], "source": dump.get("source", "?"), "to_object": m.tolist()},
                levels=levels, floors=floors, roof={"parapet_h_m": round(max(top_z - roof_z, 0.0), 3)})
    return spec, report

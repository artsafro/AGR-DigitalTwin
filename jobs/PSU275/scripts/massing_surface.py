"""Full-height exterior surface with openings from massing profiles + sampled wall masks.

    uv run python jobs/PSU275/scripts/massing_surface.py <profiles.json> <wall-masks.npz> <out_dir>

1. Openings per profile: voids of the sampled opaque layer inside the profile, as greedy
   rectangles, edges snapped to source vertices, stacked strips merged, slivers dropped.
   Voids touching the profile boundary are measurement edges (roof junction, wall top) and
   are recorded, not cut.
2. Opening edges are consolidated within CLUSTER (global z, per-plane u).
3. Meshing: every polygon vertex (outer, holes) emits horizontal and vertical cut lines that
   run only until a hole or the profile boundary. Corner lines shared by two profiles pass
   their cut heights to each other until stable. Faces of the resulting rectangular
   partition become quads (T-junction-free by construction; verified below).
Output follows the exterior-surface contract read by tools/run_body_shell.py.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, Polygon, box, shape
from shapely.ops import polygonize, unary_union

STEP_MERGE_OVERLAP, MERGE_GAP, MIN_OPENING, SNAP, CLUSTER = 0.8, 0.3, 0.35, 0.04, 0.012
# Shell 0.4 m moves corner vertices 0.4 m along the neighbour plane: an opening edge closer
# than this to a vertical profile edge would twist the reveal. Trim to keep the clearance.
CORNER_CLEARANCE = 0.41
MERGE_MIN_VOID = 0.85  # a merged strip must stay mostly void (no chaining across wall bands)
EPS = 1e-6

prof_doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
masks = np.load(sys.argv[2])
out = Path(sys.argv[3])
profiles = prof_doc["profiles"]
step = float(masks["step"])


def snap(value, pool):
    if len(pool):
        k = pool[np.argmin(abs(pool - value))]
        if abs(k - value) <= SNAP:
            return float(k)
    return float(value)


# ---------- 1. openings
for k, p in enumerate(profiles):
    poly = shape(json.loads(p["profile_geojson"]))
    p["_poly"] = poly
    us, zs, wall = masks[f"us_{k}"], masks[f"zs_{k}"], masks[f"wall_{k}"]
    U, Z = np.meshgrid(us, zs, indexing="ij")
    inside = shapely.contains_xy(poly.buffer(-step / 2, join_style="mitre"), U, Z)
    void = inside & ~wall
    seen = np.zeros_like(void)
    rects = []
    for i in range(len(us)):
        for j in range(len(zs)):
            if not void[i, j] or seen[i, j]:
                continue
            j1 = j
            while j1 + 1 < len(zs) and void[i, j1 + 1] and not seen[i, j1 + 1]:
                j1 += 1
            i1 = i
            while i1 + 1 < len(us) and void[i1 + 1, j:j1 + 1].all() and not seen[i1 + 1, j:j1 + 1].any():
                i1 += 1
            seen[i:i1 + 1, j:j1 + 1] = True
            su, sz = masks[f"snapu_{k}"], masks[f"snapz_{k}"]
            rects.append([snap(us[i] - step / 2, su), snap(zs[j] - step / 2, sz),
                          snap(us[i1] + step / 2, su), snap(zs[j1] + step / 2, sz)])
    def void_fraction(r):
        """Share of sampled void cells inside rectangle r (u0, z0, u1, z1)."""
        iu = (us > r[0]) & (us < r[2]); iz = (zs > r[1]) & (zs < r[3])
        cells = void[np.ix_(iu, iz)]
        return float(cells.mean()) if cells.size else 0.0

    merged = True
    while merged:
        merged = False
        for a in rects:
            for b in rects:
                if a is b:
                    continue
                ov = min(a[2], b[2]) - max(a[0], b[0])
                width = min(a[2] - a[0], b[2] - b[0])
                gap = max(a[1], b[1]) - min(a[3], b[3])
                cand = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                if width > 0 and ov / width >= STEP_MERGE_OVERLAP and gap <= MERGE_GAP and void_fraction(cand) >= MERGE_MIN_VOID:
                    a[:] = cand
                    rects.remove(b)
                    merged = True
                    break
            if merged:
                break
    p["openings"], p["dropped_slivers"], p["edge_voids"], p["corner_trims"] = [], [], [], []
    ring = list(poly.exterior.coords)
    vertical_edges = [(a[0], min(a[1], b[1]), max(a[1], b[1])) for a, b in zip(ring, ring[1:]) if abs(a[0] - b[0]) < 1e-9]
    for r in rects:
        before = list(r)
        for u_edge, e0, e1 in vertical_edges:
            if min(r[3], e1) - max(r[1], e0) <= 0:
                continue
            if r[0] - CORNER_CLEARANCE < u_edge <= r[0] + 1e-9 or u_edge < r[0] < u_edge + CORNER_CLEARANCE:
                r[0] = max(r[0], u_edge + CORNER_CLEARANCE) if u_edge <= r[0] else r[0]
            if r[2] - 1e-9 <= u_edge < r[2] + CORNER_CLEARANCE:
                r[2] = min(r[2], u_edge - CORNER_CLEARANCE)
        if r != before:
            p["corner_trims"].append({"from": before, "to": list(r)})
        if min(r[2] - r[0], r[3] - r[1]) < MIN_OPENING:
            p["dropped_slivers"].append(r)
        elif not poly.buffer(-0.01, join_style="mitre").contains(box(*r)):
            p["edge_voids"].append(r)
        else:
            p["openings"].append(r)

# ---------- 2. consolidation
zvals = [z for p in profiles for r in p["openings"] for z in (r[1], r[3])]
zanchor = {z for p in profiles for x, z in p["_poly"].exterior.coords}


def consolidate(values, anchors):
    groups = []
    for v in sorted(set(values) | set(anchors)):
        if groups and v - groups[-1][-1] < CLUSTER:
            groups[-1].append(v)
        else:
            groups.append([v])
    mapping = {}
    for g in groups:
        fixed = [v for v in g if v in anchors]
        rep = fixed[0] if fixed else float(np.median(g))
        mapping.update({v: rep for v in g})
    return mapping


zmap = consolidate(zvals, zanchor)
max_move = 0.0
for p in profiles:
    uanchor = {x for x, z in p["_poly"].exterior.coords}
    umap = consolidate([u for r in p["openings"] for u in (r[0], r[2])], uanchor)
    new = []
    for r in p["openings"]:
        q = [umap[r[0]], zmap[r[1]], umap[r[2]], zmap[r[3]]]
        max_move = max(max_move, *(abs(a - b) for a, b in zip(r, q)))
        new.append(q)
    p["openings"] = new
    holes = unary_union([box(*r) for r in new]) if new else Polygon()
    final = p["_poly"].difference(holes)
    if final.geom_type != "Polygon":
        raise ValueError(f"profile {p['plane']} split by openings")
    p["_final"] = final


# ---------- 3. corner lines and meshing
def plane_point(p, u, z):
    q = [0.0, 0.0, z]
    q[p["along_axis"]] = u
    q[p["axis"]] = p["plane"]
    return q


corners = []  # (k1, u_in_k1, k2, u_in_k2, z_lo, z_hi)
for k1, a in enumerate(profiles):
    for k2, b in enumerate(profiles):
        if k2 <= k1 or a["axis"] == b["axis"]:
            continue
        ua, ub = b["plane"], a["plane"]  # corner line position in each profile's u
        def z_spans(poly, u):
            hit = poly.boundary.intersection(LineString([(u, -1), (u, 100)]))
            return [g for g in getattr(hit, "geoms", [hit]) if g.geom_type == "LineString" and g.length > EPS]
        for sa in z_spans(a["_poly"], ua):
            for sb in z_spans(b["_poly"], ub):
                z0 = max(sa.bounds[1], sb.bounds[1]); z1 = min(sa.bounds[3], sb.bounds[3])
                if z1 - z0 > EPS:
                    corners.append((k1, ua, k2, ub, z0, z1))

sources = defaultdict(set)  # k -> {(u, z)} extra cut origins on corner lines


def segments(k):
    """Cut segments of profile k: pieces of vertex lines inside the final face that touch a source."""
    p = profiles[k]
    f = p["_final"]
    pts = {(round(x, 6), round(z, 6)) for ring in [f.exterior, *f.interiors] for x, z in ring.coords}
    pts |= sources[k]
    u0, z0, u1, z1 = f.bounds
    segs = []
    for axis in (0, 1):
        for c in sorted({pt[1 - axis] for pt in pts}):  # horizontal lines z=c (axis 0) / vertical u=c
            line = LineString([(u0 - 1, c), (u1 + 1, c)]) if axis == 0 else LineString([(c, z0 - 1), (c, z1 + 1)])
            pieces = line.intersection(f)
            for piece in getattr(pieces, "geoms", [pieces]):
                if piece.geom_type != "LineString" or piece.length < EPS:
                    continue
                if any(piece.distance(shapely.Point(pt)) < EPS for pt in pts
                       if abs(pt[1 - axis] - c) < EPS):
                    segs.append(piece)
    return segs


for it in range(50):
    new_total = 0
    for k1, ua, k2, ub, z0, z1 in corners:
        for (k_from, u_from, k_to, u_to) in ((k1, ua, k2, ub), (k2, ub, k1, ua)):
            for s in segments(k_from):
                for x, z in s.coords:
                    if abs(x - u_from) < EPS and z0 - EPS <= z <= z1 + EPS:
                        pt = (round(u_to, 6), round(z, 6))
                        if pt not in sources[k_to]:
                            sources[k_to].add(pt)
                            new_total += 1
    if not new_total:
        break
else:
    raise RuntimeError("corner cut propagation did not converge")

vertices, faces, labels, lookup = [], [], [], {}
t_junctions, non_rect, bad_cells = 0, 0, []
report_profiles = []
for k, p in enumerate(profiles):
    f = p["_final"]
    lines = segments(k) + [LineString(r.coords) for r in [f.exterior, *f.interiors]]
    noded = unary_union(shapely.set_precision(MultiLineString([list(l.coords) for l in lines]), 1e-6))
    cells = [c for c in polygonize(noded) if f.buffer(EPS).contains(c) and c.area > 1e-8]
    for c in cells:
        ring = [pt for i, pt in enumerate(list(c.exterior.coords)[:-1])
                if i == 0 or np.hypot(pt[0] - c.exterior.coords[i - 1][0], pt[1] - c.exterior.coords[i - 1][1]) > 1e-7]
        def turn(i):
            a, b = np.subtract(ring[i], ring[i - 1]), np.subtract(ring[(i + 1) % len(ring)], ring[i])
            return abs(a[0] * b[1] - a[1] * b[0]) > 1e-12
        corners4 = [ring[i] for i in range(len(ring)) if turn(i)]
        t_junctions += len(ring) - len(corners4)
        if len(ring) != len(corners4) or len(corners4) != 4:
            bad_cells.append({"profile": k, "ring": [[round(x, 3), round(z, 3)] for x, z in ring]})
        if len(corners4) != 4:
            non_rect += 1
            continue
        uu = sorted({round(x, 6) for x, z in corners4}); zz = sorted({round(z, 6) for x, z in corners4})
        q = np.array([plane_point(p, uu[0], zz[0]), plane_point(p, uu[1], zz[0]),
                      plane_point(p, uu[1], zz[1]), plane_point(p, uu[0], zz[1])])
        normal = np.cross(q[1] - q[0], q[2] - q[0])
        if np.dot(normal[:2], p["outward"]) < 0:
            q = q[::-1]
        idx = []
        for xyz in q:
            key = tuple(np.round(xyz, 6))
            if key not in lookup:
                lookup[key] = len(vertices); vertices.append(xyz)
            idx.append(lookup[key])
        faces.append(idx); labels.append(k + 1)
    area_err = abs(sum(c.area for c in cells) - f.area)
    report_profiles.append({"axis": p["axis"], "along_axis": p["along_axis"], "plane": p["plane"],
                            "outward": p["outward"], "profile_geojson": shapely.to_geojson(f),
                            "openings": [{"bounds_uz": r} for r in p["openings"]],
                            "edge_voids": p["edge_voids"], "dropped_slivers": p["dropped_slivers"], "corner_trims": p["corner_trims"],
                            "cells": len(cells), "area_error_m2": area_err})

out.mkdir(parents=True, exist_ok=False)
np.savez_compressed(out / "exterior-surface.npz", vertices=np.array(vertices), faces=np.array(faces, dtype=np.int32),
                    facade_indices=np.array(labels, dtype=np.int32))
summary = {"method": "massing profiles (union of rectangular masses) minus measured openings; cut lines stop at holes/boundary; corner cuts exchanged",
           "angle_rad": 0.0, "vertices": len(vertices), "quads": len(faces), "profiles_count": len(profiles),
           "openings": sum(len(p["openings"]) for p in profiles),
           "edge_voids": sum(len(p["edge_voids"]) for p in profiles),
           "dropped_slivers": sum(len(p["dropped_slivers"]) for p in profiles),
           "corner_trims": sum(len(p["corner_trims"]) for p in profiles),
           "t_junction_vertices": t_junctions, "bad_cells": bad_cells, "non_rectangular_cells": non_rect,
           "corner_lines": len(corners), "corner_propagation_iterations": it + 1,
           "max_cluster_move_m": max_move, "max_area_error_m2": max(r["area_error_m2"] for r in report_profiles),
           "params": {"merge_overlap": STEP_MERGE_OVERLAP, "merge_gap_m": MERGE_GAP, "min_opening_m": MIN_OPENING,
                      "snap_m": SNAP, "cluster_m": CLUSTER, "corner_clearance_m": CORNER_CLEARANCE, "merge_min_void": MERGE_MIN_VOID},
           "scope": "Exterior BODY surface before Shell; no roofs, portals or windows", "profiles": report_profiles}
(out / "exterior-surface.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in summary.items() if k not in ("profiles", "params")}))

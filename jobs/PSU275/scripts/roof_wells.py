"""Flat roofs, parapet inner faces and well faces for a union of rectangular masses.

    uv run python jobs/PSU275/scripts/roof_wells.py jobs/PSU275/masses.json <out_dir> [--shell 0.4]

Region = connected plan cells with the same (top, roof). Its boundary edges are classified by
the neighbour: lower/outside -> own parapet (roof is inset by the shell thickness, a parapet
inner face rises from roof to top on the inset line); taller -> neighbour's wall (no inset, a
well face covers roof..top on that wall). Roofs are flat at `roof`; slopes are not modelled.
Output: roof-wells.json (mesh, face roles) and roof-wells.npz.
"""
import json
import sys
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2])
T = float(sys.argv[sys.argv.index("--shell") + 1]) if "--shell" in sys.argv else 0.4
EPS = 1e-7
masses = cfg["masses"]
xs = sorted({v for m in masses for v in m["x"]})
ys = sorted({v for m in masses for v in m["y"]})
NX, NY = len(xs) - 1, len(ys) - 1


def cell(i, j):
    if not (0 <= i < NX and 0 <= j < NY):
        return None
    cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
    best = None
    for m in masses:
        if m["x"][0] < cx < m["x"][1] and m["y"][0] < cy < m["y"][1] and (best is None or m["top"] > best["top"]):
            best = m
    return best


grid = {(i, j): cell(i, j) for i in range(NX) for j in range(NY)}
# connected regions of equal (top, roof)
label, regions = {}, []
for start, m in grid.items():
    if m is None or start in label:
        continue
    key = (m["top"], m["roof"])
    stack, cells = [start], []
    label[start] = len(regions)
    while stack:
        c = stack.pop(); cells.append(c)
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + d[0], c[1] + d[1])
            if n in grid and n not in label and grid[n] is not None and (grid[n]["top"], grid[n]["roof"]) == key:
                label[n] = len(regions); stack.append(n)
    regions.append({"top": key[0], "roof": key[1], "cells": cells,
                    "masses": sorted({grid[c]["name"] for c in cells})})


def neighbour_top(x, y):
    """Top of the plan cell containing (x, y); 0 outside."""
    i = np.searchsorted(xs, x) - 1; j = np.searchsorted(ys, y) - 1
    m = grid.get((int(i), int(j)))
    return 0.0 if m is None else m["top"]


verts, faces, roles, lookup = [], [], [], {}


def add_face(pts, normal, role, region):
    q = np.array(pts, dtype=float)
    n = np.cross(q[1] - q[0], q[2] - q[0])
    if np.dot(n, normal) < 0:
        q = q[::-1]
    idx = []
    for p in q:
        key = tuple(np.round(p, 6))
        if key not in lookup:
            lookup[key] = len(verts); verts.append(p.tolist())
        idx.append(lookup[key])
    faces.append(idx); roles.append({"role": role, "region": region})


report = []
for ri, r in enumerate(regions):
    R = unary_union([box(xs[i], ys[j], xs[i + 1], ys[j + 1]) for i, j in r["cells"]]).simplify(0)
    strips, edge_kinds = [], []
    for ring in [R.exterior, *R.interiors]:
        pts = list(ring.coords)
        for a, b in zip(pts, pts[1:]):
            mid = np.add(a, b) / 2
            d = np.subtract(b, a); n = np.array([d[1], -d[0]]) / np.linalg.norm(d)
            # outward normal: the side not in R
            if R.contains(Point(mid + n * 1e-3)):
                n = -n
            outside = mid + n * 1e-3
            # edge may border several neighbours: split at plan cuts
            cuts = sorted({*(xs if abs(d[0]) > 0 else ys)} | {a[0 if abs(d[0]) > 0 else 1], b[0 if abs(d[0]) > 0 else 1]})
            u_ax = 0 if abs(d[0]) > 0 else 1
            lo, hi = sorted((a[u_ax], b[u_ax]))
            cuts = [c for c in cuts if lo - EPS <= c <= hi + EPS]
            for c0, c1 in zip(cuts, cuts[1:]):
                p0 = np.array(a, float); p1 = np.array(a, float)
                p0[u_ax], p1[u_ax] = c0, c1
                m = (p0 + p1) / 2 + n * 1e-3
                kind = "parapet" if neighbour_top(*m) < r["top"] else "well"
                edge_kinds.append((p0, p1, n, kind))
                if kind == "parapet":
                    ext = np.zeros(2); ext[u_ax] = T
                    # extended by T at both ends so inset lines meet at concave corners
                    strips.append(Polygon([p0 - ext, p1 + ext, p1 + ext - n * T, p0 - ext - n * T]))
    roof = R.difference(unary_union(strips)) if strips else R
    roof = shapely.set_precision(roof, 1e-6)
    parts = list(getattr(roof, "geoms", [roof]))
    zr, zt = r["roof"], r["top"]
    # roof quads: full vertex grid of each part (T-free inside the roof)
    for part in parts:
        ux = sorted({round(x, 6) for ring in [part.exterior, *part.interiors] for x, y in ring.coords})
        uy = sorted({round(y, 6) for ring in [part.exterior, *part.interiors] for x, y in ring.coords})
        for x0, x1 in zip(ux, ux[1:]):
            for y0, y1 in zip(uy, uy[1:]):
                if part.contains(Point((x0 + x1) / 2, (y0 + y1) / 2)):
                    add_face([[x0, y0, zr], [x1, y0, zr], [x1, y1, zr], [x0, y1, zr]], [0, 0, 1], "roof", ri)
        # vertical faces on every roof boundary edge, cut at the roof grid lines
        for ring in [part.exterior, *part.interiors]:
            pts = list(ring.coords)
            for a, b in zip(pts, pts[1:]):
                a, b = np.array(a), np.array(b)
                d = b - a; u_ax = 0 if abs(d[0]) > EPS else 1
                n_in = np.array([-d[1], d[0]]) / np.linalg.norm(d)
                if not part.contains(Point(*((a + b) / 2 + n_in * 1e-3))):
                    n_in = -n_in
                on_R = R.boundary.distance(LineString([a, b])) < 1e-6 and \
                    R.boundary.intersection(LineString([a, b]).buffer(1e-6)).length > np.linalg.norm(d) - 1e-5
                if on_R:
                    probe = (a + b) / 2 - n_in * 1e-3
                    if neighbour_top(*probe) <= r["top"]:
                        continue  # parapet sides are inset, so an on-R edge here is the well side only
                    if "--no-wells" in sys.argv:
                        continue  # wells are part of BODY (massing_profiles.py --wells)
                    role, z1 = "well", zt
                else:
                    role, z1 = "parapet_inner", zt
                if z1 - zr < 1e-6:
                    continue
                grid_u = ux if u_ax == 0 else uy
                lo, hi = sorted((a[u_ax], b[u_ax]))
                cuts = [c for c in grid_u if lo - 1e-6 <= c <= hi + 1e-6]
                for c0, c1 in zip(cuts, cuts[1:]):
                    p0 = a.copy(); p1 = a.copy(); p0[u_ax], p1[u_ax] = c0, c1
                    add_face([[*p0, zr], [*p1, zr], [*p1, z1], [*p0, z1]], [*n_in, 0], role, ri)
    report.append({"region": ri, "masses": r["masses"], "top": zt, "roof": zr,
                   "roof_area_m2": round(roof.area, 2), "parts": len(parts),
                   "parapet_edges": sum(1 for e in edge_kinds if e[3] == "parapet"),
                   "well_edges": sum(1 for e in edge_kinds if e[3] == "well")})

out.mkdir(parents=True, exist_ok=False)
mesh = {"name": "ROOF_Flat_ParapetWells", "vertices": verts, "faces": faces, "materials": [0] * len(faces)}
(out / "roof-wells.json").write_text(json.dumps({"mesh": mesh, "face_roles": roles, "regions": report, "shell_m": T,
                                                 "scope": "Flat roofs at roof level; slopes, drains, skylights not modelled"},
                                                ensure_ascii=False), encoding="utf-8")
counts = {k: sum(1 for x in roles if x["role"] == k) for k in ("roof", "parapet_inner", "well")}
print(json.dumps({"regions": len(regions), "faces": len(faces), **counts}))
for r in report:
    print(r)

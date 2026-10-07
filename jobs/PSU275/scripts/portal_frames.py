"""Entrance portals and canopies: front silhouette measured on S3, extruded to the facade.

    uv run python jobs/PSU275/scripts/portal_frames.py <outside_faces.npz> <out_dir>

Portals are blue U- or L-frames around a recessed door/gate, or floating canopies; the door
stays in the facade (BODY opening). Per seed region (facade plane f, outward sign):
  p          outer face plane (largest outward-facing area, outermost)
  silhouette union of the (u, z) bounds of the outward faces lying on p (1 mm precision)
Mesh: the silhouette on p as a T-free vertex-grid of quads, plus side faces along every
silhouette edge from p back to f (11 mm into the wall), split at the same grid lines. No back face.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Point, box
from shapely.ops import unary_union

faces_npz, out = sys.argv[1], Path(sys.argv[2])
MASS_PLANES = None  # facade planes per axis from argv[3] (masses.json)
if len(sys.argv) > 3:
    _m = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))["masses"]
    MASS_PLANES = ({v for m in _m for v in m["x"]}, {v for m in _m for v in m["y"]})
OPAQUE = ("Сэндвич", "Синий (RAL 5015)", "Алюкобонд")
CLUSTER = 0.012
WALL_EMBED = 0.011  # frames go 11 mm into the facade, not touching it (KPP1 v005 lesson: xView overlaps)
PLANE_CLEAR = 0.006  # portal faces closer than xView 5 mm to a facade plane move 6 mm away (KPP1 v005)
# name, region box (x0, x1, y0, y1), facade normal axis, facade plane, outward sign
SEEDS = [
    ("annex_west",  (-58.3, -56.4, -50.7, -43.9), 0, -56.45, -1),
    ("annex_north", (-56.6, -52.0, 2.2, 4.1), 1, 2.28, +1),
    ("vestibule_A", (-39.6, -37.7, 4.1, 12.5), 0, -37.79, -1),
    ("vestibule_B", (-44.9, -38.0, 2.2, 4.0), 1, 2.28, +1),
    ("annex_south", (-44.4, -38.6, -56.1, -54.2), 1, -54.28, -1),
    ("west_1",      (-39.6, -37.7, 16.2, 24.2), 0, -37.79, -1),
    ("west_2",      (-39.9, -37.7, 28.6, 42.0), 0, -37.79, -1),
    ("west_3",      (-39.6, -37.7, 44.8, 48.1), 0, -37.79, -1),
    ("south_1",     (-34.9, -25.3, -56.1, -54.2), 1, -54.28, -1),
    ("south_2",     (17.3, 22.3, -56.1, -54.2), 1, -54.28, -1),
    ("south_3",     (25.5, 28.1, -56.1, -54.2), 1, -54.28, -1),
    ("north",       (43.0, 48.9, 54.2, 56.0), 1, 54.28, +1),
    ("east_1",      (56.4, 58.5, -47.9, -32.9), 0, 56.45, +1),
    ("east_2",      (56.4, 58.2, 8.1, 11.1), 0, 56.45, +1),
    ("east_3",      (56.4, 58.5, 35.3, 42.5), 0, 56.45, +1),
]

d = np.load(faces_npz)
c, area, nr, lo, hi = d["centres"], d["areas"], d["normals"], d["lo"], d["hi"]
names = d["object_names"]
opq = np.array([any(k in str(names[o]) for k in OPAQUE) for o in d["object_ids"]])

verts, faces, roles, lookup = [], [], [], {}


def add(pts, normal, role):
    q = np.array(pts, float)
    if np.dot(np.cross(q[1] - q[0], q[2] - q[0]), normal) < 0:
        q = q[::-1]
    idx = []
    for p in q:
        k = tuple(np.round(p, 6))
        if k not in lookup:
            lookup[k] = len(verts); verts.append(p.tolist())
        idx.append(lookup[k])
    faces.append(idx); roles.append(role)


def planes(mask, axis, sign):
    acc = defaultdict(lambda: [0.0, -1e9])
    for i in np.nonzero(mask & (nr[:, axis] * sign > 0.99))[0]:
        k = round(float(c[i, axis]), 3)
        acc[k][0] += area[i]; acc[k][1] = max(acc[k][1], hi[i, 2])
    return {k: v for k, v in acc.items() if v[0] > 0.3}


report = []
for name, (x0, x1, y0, y1), n_ax, f, s in SEEDS:
    u_ax = 1 - n_ax
    m = opq & (c[:, 0] > x0) & (c[:, 0] < x1) & (c[:, 1] > y0) & (c[:, 1] < y1)
    front = planes(m, n_ax, s)
    best = max(v[0] for v in front.values())
    p = max((k for k, v in front.items() if v[0] > 0.3 * best), key=lambda k: s * k)
    sel = np.nonzero(m & (nr[:, n_ax] * s > 0.99) & (abs(c[:, n_ax] - p) < 0.02))[0]
    raw = [(lo[i, u_ax], lo[i, 2], hi[i, u_ax], hi[i, 2]) for i in sel if hi[i, u_ax] - lo[i, u_ax] > 1e-4 and hi[i, 2] - lo[i, 2] > 1e-4]
    # coordinates closer than CLUSTER share one value: no sub-10 mm faces
    maps = []
    for axis_vals in ([r[0] for r in raw] + [r[2] for r in raw], [r[1] for r in raw] + [r[3] for r in raw]):
        groups = []
        for v in sorted(set(round(float(t), 4) for t in axis_vals)):
            if groups and v - groups[-1][-1] < CLUSTER:
                groups[-1].append(v)
            else:
                groups.append([v])
        maps.append({v: float(np.median(g)) for g in groups for v in g})
    rects = [box(maps[0][round(float(a), 4)], maps[1][round(float(b), 4)], maps[0][round(float(cc), 4)], maps[1][round(float(dd), 4)])
             for a, b, cc, dd in raw]
    rects = [r for r in rects if r.area > 0]
    if MASS_PLANES:
        # silhouette u-edges near a perpendicular facade plane: pull 6 mm into the silhouette
        planes_u = MASS_PLANES[u_ax]
        fixed = []
        for r in rects:
            a0, b0, a1, b1 = r.bounds
            for pl in planes_u:
                if abs(a0 - pl) < PLANE_CLEAR:
                    a0 = pl + PLANE_CLEAR
                if abs(a1 - pl) < PLANE_CLEAR:
                    a1 = pl - PLANE_CLEAR
            if a1 > a0:
                fixed.append(box(a0, b0, a1, b1))
        rects = fixed
    sil = shapely.set_precision(unary_union(rects), 0.001).simplify(0.001)
    parts = [g for g in getattr(sil, "geoms", [sil]) if g.area > 0.05]

    def P(u, z, n):
        if n == f:
            n = f - s * WALL_EMBED
        q = [0.0, 0.0, 0.0 if z < 0.05 else z]; q[u_ax] = u; q[n_ax] = n
        return q

    out_n = [0, 0, 0]; out_n[n_ax] = s
    nf0 = len(faces)
    for part in parts:
        rings = [part.exterior, *part.interiors]
        us = sorted({round(x, 3) for r in rings for x, z in r.coords})
        zs = sorted({round(z, 3) for r in rings for x, z in r.coords})
        for ua, ub in zip(us, us[1:]):
            for za, zb in zip(zs, zs[1:]):
                if part.contains(Point((ua + ub) / 2, (za + zb) / 2)):
                    add([P(ua, za, p), P(ub, za, p), P(ub, zb, p), P(ua, zb, p)], out_n, "front")
        for r in rings:
            pts = [(round(x, 3), round(z, 3)) for x, z in r.coords]
            for (ua, za), (ub, zb) in zip(pts, pts[1:]):
                horizontal = abs(za - zb) < 1e-9
                cuts = [v for v in (us if horizontal else zs) if min(ua, ub) - 1e-9 <= v <= max(ua, ub) + 1e-9] if horizontal                     else [v for v in zs if min(za, zb) - 1e-9 <= v <= max(za, zb) + 1e-9]
                mid = ((ua + ub) / 2, (za + zb) / 2)
                d = np.array([ub - ua, zb - za]); nrm2 = np.array([d[1], -d[0]]) / np.linalg.norm(d)
                if part.contains(Point(mid[0] + nrm2[0] * 1e-3, mid[1] + nrm2[1] * 1e-3)):
                    nrm2 = -nrm2  # outward from the silhouette
                nn = [0, 0, 0]; nn[u_ax] = nrm2[0]; nn[2] = nrm2[1]
                for v0, v1 in zip(cuts, cuts[1:]):
                    if horizontal:
                        q = [P(v0, za, f), P(v1, za, f), P(v1, za, p), P(v0, za, p)]
                    else:
                        q = [P(ua, v0, f), P(ua, v1, f), P(ua, v1, p), P(ua, v0, p)]
                    if q[0][2] == q[1][2] == 0.0 and horizontal:
                        continue  # bottom on the ground: no underside face
                    add(q, nn, "side")
    row = {"name": name, "facade_axis": "xy"[n_ax], "facade_plane": f, "outer_plane": p, "depth_m": round(abs(p - f), 3),
           "silhouette_area_m2": round(sil.area, 2), "parts": len(parts),
           "bounds_uz": [round(v, 3) for v in sil.bounds], "faces": len(faces) - nf0,
           "kind": "frame" if any(g.bounds[1] < 0.05 for g in parts) else "canopy"}
    report.append(row); print(row)

out.mkdir(parents=True, exist_ok=False)
mesh = {"name": "PORTALS_Frames", "vertices": verts, "faces": faces, "materials": [0] * len(faces)}
(out / "portals.json").write_text(json.dumps({"mesh": mesh, "face_roles": roles, "portals": report,
                                              "scope": "Frames and canopies only; doors/gates stay in BODY openings"}, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
print("faces", len(faces), "portals", len(report))

"""Low-poly external steel stairs and ladders for the PSU275 Main, from measured S3 clusters.

    uv run python jobs/PSU275/scripts/build_stairs.py <stairs.json> <masses.json> <out.json>

Switchback towers (KPP1 v005 practice, rebuilt by parameters, not the raw Revit/Max mesh):
- big decking faces (> 10 m2) = landings; small = treads. Run axis from the flight directions.
- tower plan = landing/tread extents (+ half a tread); landings sit at one run end each,
  flights connect consecutive landings on the half of the width where that flight's treads are
  (full width when there is no switchback); a ground flight runs from the free end at 0.000.
- landing: 0.10 m slab box; flight: 0.15 m sloped slab (6 faces) - finish Metal_RAL5015.
- guards: double alpha planes (8 mm apart, both facing out) 1.2 m high on the open sides of flights
  and landings - finish Railing_Alpha_RAL1021, explicit UVs in metres (u along, v = 0.05 + height).
- ladders (clusters made of the '1021' object): one double alpha plane parallel to the nearest
  facade, 0.88 m wide - finish Ladder_Alpha_RAL1021.
Output: {"mesh", "finishes" per face, "uvm" per face (4 UV pairs) or null, "towers"}.
"""
import json
import sys
from pathlib import Path

import numpy as np

stairs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
masses = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))["masses"]
out = Path(sys.argv[3])
SLAB_L, SLAB_F, GUARD, GAP, TREAD = 0.10, 0.15, 1.2, 0.008, 0.0

verts, faces, fins, uvms, lookup = [], [], [], [], {}


def face(pts, finish, normal, uv=None):
    q = np.array(pts, float)
    if np.dot(np.cross(q[1] - q[0], q[2] - q[0]), normal) < 0:
        q = q[::-1]
        uv = uv[::-1] if uv is not None else None
    idx = []
    for p in q:
        k = tuple(np.round(p, 5))
        if k not in lookup:
            lookup[k] = len(verts); verts.append(p.tolist())
        idx.append(lookup[k])
    faces.append(idx); fins.append(finish); uvms.append(uv)


def box(lo, hi, finish):
    x0, y0, z0 = lo; x1, y1, z1 = hi
    P = lambda x, y, z: (x, y, z)
    face([P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], finish, (0, 0, 1))
    face([P(x0, y0, z0), P(x1, y0, z0), P(x1, y1, z0), P(x0, y1, z0)], finish, (0, 0, -1))
    face([P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)], finish, (0, -1, 0))
    face([P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z1), P(x0, y1, z1)], finish, (0, 1, 0))
    face([P(x0, y0, z0), P(x0, y1, z0), P(x0, y1, z1), P(x0, y0, z1)], finish, (-1, 0, 0))
    face([P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)], finish, (1, 0, 0))


def guard(a, b, za, zb, out_n, finish="Railing_Alpha_RAL1021", h=GUARD, u0=0.0):
    """Double alpha plane between plan points a->b, bottom from za to zb, height h, 8 mm apart."""
    if "Ladder" not in finish and near_wall(a, b, min(za, zb)):
        return  # guards are not needed against a wall (ladders stand there by design)
    on = np.array([out_n[0], out_n[1], 0.0])
    a = np.array(a, float) + on[:2] * GUARD_OFF; b = np.array(b, float) + on[:2] * GUARD_OFF
    L = float(np.linalg.norm(b - a))
    uv = [(u0, 0.05), (u0 + L, 0.05), (u0 + L, 0.05 + h), (u0, 0.05 + h)]
    for s in (+1, -1):
        off = on * (GAP / 2) * s
        q = [(a[0] + off[0], a[1] + off[1], za), (b[0] + off[0], b[1] + off[1], zb),
             (b[0] + off[0], b[1] + off[1], zb + h), (a[0] + off[0], a[1] + off[1], za + h)]
        face(q, finish, on * s, list(uv) if s > 0 else [(2 * u0 + L - u, v) for u, v in uv])


base_z = 0.0


def flight_slab(r_ax, run0, z0, run1, z1, c0, c1, finish="Metal_RAL5015"):
    """Sloped slab: top surface from (run0, z0) to (run1, z1) over cross [c0, c1], SLAB_F thick."""
    c_ax = 1 - r_ax

    def P(r, c, z):
        p = [0.0, 0.0, z]; p[r_ax] = r; p[c_ax] = c
        return p
    t = SLAB_F
    # embed both ends EMBED into the landings (extend along the slope), never below the base
    d = np.sign(run1 - run0); slope = (z1 - z0) / abs(run1 - run0)
    r0e, r1e = run0 - d * EMBED, run1 + d * EMBED
    z0e, z1e = z0 - slope * EMBED, z1 + slope * EMBED
    if z0 <= base_z + 1e-9:  # starts on the ground/roof: no embed below the base
        r0e, z0e = run0, z0
    top = [P(r0e, c0, z0e), P(r1e, c0, z1e), P(r1e, c1, z1e), P(r0e, c1, z0e)]
    bot = [P(r, c, max(z - t, base_z)) for r, c, z in ((r0e, c0, z0e), (r1e, c0, z1e), (r1e, c1, z1e), (r0e, c1, z0e))]
    up = np.cross(np.subtract(top[1], top[0]), np.subtract(top[3], top[0]))
    up = up if up[2] > 0 else -up
    face(top, finish, up); face(bot, finish, -up)
    for i, j in ((0, 1), (3, 2)):
        n = np.zeros(3); n[c_ax] = -1 if i == 0 else 1
        face([bot[i], bot[j], top[j], top[i]], finish, n)
    for i, j, sgn in ((0, 3, -1), (1, 2, 1)):
        if abs(top[i][2] - bot[i][2]) < 1e-6:
            continue  # zero-height end on the base
        n = np.zeros(3); n[r_ax] = sgn * np.sign(run1 - run0)
        face([bot[i], bot[j], top[j], top[i]], finish, n)


CLEAR, WALL_SKIP, MERGE = 0.006, 0.3, 1.5
EMBED, SPLIT, LIFT, GUARD_OFF = 0.011, 0.012, 0.006, 0.010  # KPP1 v005 joints: embed 11 mm, 6 mm clearances


def merge_clusters(cls):
    """Merge non-ladder clusters whose plan boxes are closer than MERGE and overlap in z."""
    cls = [dict(c) for c in cls]
    changed = True
    while changed:
        changed = False
        for a in cls:
            for b in cls:
                if a is b or "ladder" in a["area_by_kind"] or "ladder" in b["area_by_kind"]:
                    continue
                gap = max(max(a["lo"][i], b["lo"][i]) - min(a["hi"][i], b["hi"][i]) for i in range(2))
                zov = min(a["hi"][2], b["hi"][2]) - max(a["lo"][2], b["lo"][2])
                if gap < MERGE and zov > -0.5:
                    a["lo"] = [min(a["lo"][i], b["lo"][i]) for i in range(3)]
                    a["hi"] = [max(a["hi"][i], b["hi"][i]) for i in range(3)]
                    for k, v in b["area_by_kind"].items():
                        a["area_by_kind"][k] = a["area_by_kind"].get(k, 0) + v
                    a["landings"] = a["landings"] + b["landings"]; a["flights"] = a["flights"] + b["flights"]
                    cls.remove(b); changed = True
                    break
            if changed:
                break
    return cls


def clip_plan(r_ax, r0, r1, c0, c1, z_bottom):
    """Shrink the plan box out of every mass taller than z_bottom, keeping CLEAR."""
    c_ax = 1 - r_ax
    for m in masses:
        if m["top"] <= z_bottom + 0.05:
            continue
        mr, mc = (m["x"], m["y"]) if r_ax == 0 else (m["y"], m["x"])
        if r1 <= mr[0] or r0 >= mr[1] or c1 <= mc[0] or c0 >= mc[1]:
            continue
        cuts = {"c_hi": c1 - (mc[0] - CLEAR), "c_lo": (mc[1] + CLEAR) - c0, "r_hi": r1 - (mr[0] - CLEAR), "r_lo": (mr[1] + CLEAR) - r0}
        side = min(cuts, key=cuts.get)
        if side == "c_hi": c1 = mc[0] - CLEAR
        elif side == "c_lo": c0 = mc[1] + CLEAR
        elif side == "r_hi": r1 = mr[0] - CLEAR
        else: r0 = mr[1] + CLEAR
    return r0, r1, c0, c1


def near_wall(a, b, z):
    """Guard line a-b lies within WALL_SKIP of a parallel mass face standing above z."""
    a, b = np.array(a, float), np.array(b, float)
    for m in masses:
        if m["top"] <= z + 0.05:
            continue
        for ax, v in ((0, m["x"][0]), (0, m["x"][1]), (1, m["y"][0]), (1, m["y"][1])):
            if abs(a[ax] - b[ax]) < 1e-6 and abs(a[ax] - v) < WALL_SKIP:
                o = 1 - ax
                span = (m["y"] if ax == 0 else m["x"])
                if min(a[o], b[o]) < span[1] and max(a[o], b[o]) > span[0]:
                    return True
    return False


report = []
for cl in merge_clusters(stairs):
    kinds = cl["area_by_kind"]
    total = sum(kinds.values())
    if total < 30 and set(kinds) != {"ladder"}:
        continue  # platform scraps are part of a neighbouring cluster
    lo, hi = np.array(cl["lo"]), np.array(cl["hi"])
    if set(kinds) == {"ladder"}:
        # ladder: plane parallel to the nearest mass face, through the cluster centre line
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        best = None
        for m in masses:
            for ax, v in ((0, m["x"][0]), (0, m["x"][1]), (1, m["y"][0]), (1, m["y"][1])):
                d = abs((cx if ax == 0 else cy) - v)
                if best is None or d < best[0]:
                    best = (d, ax, v)
        _, ax, v = best
        off = np.sign((cx if ax == 0 else cy) - v) or 1.0
        plane = v + off * 0.2
        if ax == 0:
            a, b = (plane, cy - 0.40), (plane, cy + 0.40); n = (off, 0)
        else:
            a, b = (cx - 0.40, plane), (cx + 0.40, plane); n = (0, off)
        # ladder pattern: stiles at u 0.04..0.09 / 0.79..0.84 -> plane u 0.04..0.84; split into <= 3.5 m pieces
        hgt = hi[2] - lo[2]; pieces = int(np.ceil(hgt / 3.5)); dh = hgt / pieces
        for k_ in range(pieces):
            zk = lo[2] + k_ * dh
            guard(a, b, zk, zk, n, "Ladder_Alpha_RAL1021", h=dh, u0=0.04)
        report.append({"cluster": cl["cluster"], "type": "ladder", "z": [lo[2], hi[2]], "plane_axis": "xy"[ax], "plane": plane})
        continue
    lands = [l for l in cl["landings"] if l[1] > 10]
    treads = [l for l in cl["landings"] if l[1] <= 10]
    if not lands:
        continue
    if len({round(l[0], 1) for l in lands}) == 1:
        # platform + straight flight: platform = union of its plates, flight = treads extent from the base
        z = lands[0][0]
        base_z = LIFT
        fl = [f for f in cl["flights"] if f["faces"] > 3] or cl["flights"]
        r_ax = 0 if sum(abs(f["down_dir_xy"][0]) * f["faces"] for f in fl) >= sum(abs(f["down_dir_xy"][1]) * f["faces"] for f in fl) else 1
        c_ax = 1 - r_ax
        pr0 = min(l[2][r_ax] for l in lands); pr1 = max(l[3][r_ax] for l in lands)
        pc0 = min(l[2][c_ax] for l in lands); pc1 = max(l[3][c_ax] for l in lands)
        pr0, pr1, pc0, pc1 = clip_plan(r_ax, pr0, pr1, pc0, pc1, 0.0)
        lo_b = [0.0, 0.0, z - SLAB_L]; hi_b = [0.0, 0.0, z]
        lo_b[r_ax], hi_b[r_ax], lo_b[c_ax], hi_b[c_ax] = pr0, pr1, pc0, pc1
        box(lo_b, hi_b, "Metal_RAL5015")
        tr0 = min(t[2][r_ax] for t in treads); tr1 = max(t[3][r_ax] for t in treads)
        tc0 = min(t[2][c_ax] for t in treads); tc1 = max(t[3][c_ax] for t in treads)
        tr0, tr1, tc0, tc1 = clip_plan(r_ax, tr0, tr1, tc0, tc1, 0.0)
        far_hi = abs(tr1 - (pr0 + pr1) / 2) > abs(tr0 - (pr0 + pr1) / 2)
        start, stop = (tr1, pr1) if far_hi else (tr0, pr0)
        flight_slab(r_ax, start, LIFT, stop, z, tc0 + CLEAR, tc1 - CLEAR)
        g_stop = stop + np.sign(start - stop) * 0.02  # end short of the platform edge (no vertex on its edge)
        g_z = LIFT + (z - LIFT) * abs(g_stop - start) / abs(stop - start)
        for side, sgn in ((tc0 + CLEAR, -1), (tc1 - CLEAR, 1)):
            n = [0, 0]; n[c_ax] = sgn
            pa = [0, 0]; pb = [0, 0]; pa[r_ax], pa[c_ax] = start, side; pb[r_ax], pb[c_ax] = g_stop, side
            guard(pa, pb, LIFT, g_z, n)
        for (a_, b_, n_) in (((pr0, pc0), (pr1, pc0), (0, -1)), ((pr0, pc1), (pr1, pc1), (0, 1)), ((pr0, pc0), (pr0, pc1), (-1, 0))):
            pa = [0, 0]; pb = [0, 0]; n = [0, 0]
            pa[r_ax], pa[c_ax] = a_; pb[r_ax], pb[c_ax] = b_; n[r_ax], n[c_ax] = n_
            guard(pa, pb, z, z, n)
        report.append({"cluster": cl["cluster"], "type": "platform+flight", "run_axis": "xy"[r_ax], "z": z,
                       "platform": [[round(pr0, 3), round(pr1, 3)], [round(pc0, 3), round(pc1, 3)]],
                       "flight": [[round(start, 3), round(stop, 3)], [round(tc0, 3), round(tc1, 3)]]})
        continue
    fl = [f for f in cl["flights"] if f["faces"] > 3]
    r_ax = 0 if sum(abs(f["down_dir_xy"][0]) * f["faces"] for f in fl) >= sum(abs(f["down_dir_xy"][1]) * f["faces"] for f in fl) else 1
    c_ax = 1 - r_ax
    pts = [(l[2], l[3]) for l in (treads or lands)] + [(l[2], l[3]) for l in lands if l[0] < 1.0 or not treads]
    r_lo = min(p[0][r_ax] for p in pts) - TREAD; r_hi = max(p[1][r_ax] for p in pts) + TREAD
    c_lo = min(p[0][c_ax] for p in pts) - TREAD; c_hi = max(p[1][c_ax] for p in pts) + TREAD
    base = (max(0.0, round(float(lo[2]), 2)) if lo[2] > 0.3 else 0.0) + LIFT  # roof towers start on their roof; 6 mm lift
    base_z = base
    r_lo, r_hi, c_lo, c_hi = clip_plan(r_ax, r_lo, r_hi, c_lo, c_hi, base)
    c_mid = (c_lo + c_hi) / 2
    landing_depth = max(min(l[3][r_ax] - l[2][r_ax] + 2 * TREAD, 2.0) for l in lands)
    seq = []
    for l in sorted(lands, key=lambda l: l[0]):
        z = l[0]
        centre = (l[2][r_ax] + l[3][r_ax]) / 2
        end = 1 if centre > (r_lo + r_hi) / 2 else 0
        a0, a1 = (r_hi - landing_depth, r_hi) if end else (r_lo, r_lo + landing_depth)
        # landing spans the full tower width unless it is a single-run platform
        lo_b = [0.0, 0.0, z - SLAB_L]; hi_b = [0.0, 0.0, z]
        lo_b[r_ax], hi_b[r_ax] = a0, a1
        lo_b[c_ax], hi_b[c_ax] = c_lo, c_hi
        box(lo_b, hi_b, "Metal_RAL5015")
        seq.append((z, end, a0, a1))
    switchback = len({s[1] for s in seq}) > 1
    prev = None
    for k, (z, end, a0, a1) in enumerate(seq):
        if prev is None:
            if z > base + 0.3:  # first flight from the free end, at the base (ground or the roof below)
                start = r_lo if end else r_hi
                stop = a0 if end else a1
                tz = [t for t in treads if t[0] < z]
                cc = np.mean([(t[2][c_ax] + t[3][c_ax]) / 2 for t in tz]) if tz else c_mid
                c0, c1 = ((c_lo + CLEAR, c_mid - SPLIT / 2) if cc < c_mid else (c_mid + SPLIT / 2, c_hi - CLEAR)) if switchback else (c_lo + CLEAR, c_hi - CLEAR)
                flight_slab(r_ax, start, base, stop, z, c0, c1)
                outer = c0 if cc < c_mid else c1
                n = [0, 0]; n[c_ax] = -1 if outer == c0 else 1
                pa = [0, 0]; pb = [0, 0]; pa[r_ax], pa[c_ax] = start, outer; pb[r_ax], pb[c_ax] = stop, outer
                guard(pa, pb, base, z, n)
        else:
            pz, pend, pa0, pa1 = prev
            start = pa0 if pend else pa1
            stop = a0 if end else a1  # inner edge of the landing this flight reaches
            if pend == end:  # same end (no switchback): straight flight over the full width
                stop = a0 if end else a1
            tz = [t for t in treads if pz < t[0] < z]
            cc = np.mean([(t[2][c_ax] + t[3][c_ax]) / 2 for t in tz]) if tz else c_mid
            c0, c1 = ((c_lo + CLEAR, c_mid - SPLIT / 2) if cc < c_mid else (c_mid + SPLIT / 2, c_hi - CLEAR)) if switchback else (c_lo + CLEAR, c_hi - CLEAR)
            flight_slab(r_ax, start, pz, stop, z, c0, c1)
            outer = c0 if cc < c_mid else c1
            n = [0, 0]; n[c_ax] = -1 if outer == c0 else 1
            pa = [0, 0]; pb = [0, 0]; pa[r_ax], pa[c_ax] = start, outer; pb[r_ax], pb[c_ax] = stop, outer
            guard(pa, pb, pz, z, n)
        # landing guards: run-end side and both cross sides
        r_end = a1 if end else a0
        n = [0, 0]; n[r_ax] = 1 if end else -1
        pa = [0, 0]; pb = [0, 0]; pa[r_ax] = pb[r_ax] = r_end; pa[c_ax], pb[c_ax] = c_lo, c_hi
        guard(pa, pb, z, z, n)
        prev = (z, end, a0, a1)
    report.append({"cluster": cl["cluster"], "type": "tower" if switchback else "straight", "run_axis": "xy"[r_ax],
                   "plan": [[round(r_lo, 2), round(r_hi, 2)], [round(c_lo, 2), round(c_hi, 2)]],
                   "landings": [round(s[0], 2) for s in seq]})
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"mesh": {"name": "STAIRS", "vertices": verts, "faces": faces}, "finishes": fins,
                           "uvm": uvms, "towers": report}, ensure_ascii=False), encoding="utf-8")
from collections import Counter
print(json.dumps({"faces": len(faces), "tris": 2 * len(faces), "finishes": Counter(fins)}, ensure_ascii=False))
for r in report:
    print(r)

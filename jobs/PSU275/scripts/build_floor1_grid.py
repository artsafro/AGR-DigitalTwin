"""Measured occupancy grid for `extract_exterior` from the clipped S3 first floor.

    blender --background <psu275_floor1_src.blend> --python jobs/PSU275/scripts/build_floor1_grid.py -- <out_dir>

Frame: Revit metres shifted to the building bbox centre (angle 0). Footprint: outer panel faces
measured by facade_planes.py and mapped S3 -> Revit (STATE.md).
Each facade run is ray-sampled from outside; a hit on an opaque wall layer within DEPTH
behind the outer face = wall, otherwise = opening. Opening edges snap to nearby vertex
coordinates of the opaque layer. Outputs: body-grid.npz, contour-source.json (openings as
explicit items `S3-op-<run>-<n>`), owner-registry.json, grid-report.json.
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT = Path(sys.argv[sys.argv.index("--") + 1])
H = 13.060
STEP = 0.05          # sampling step along u and z, m
DEPTH = 0.15         # wall layer depth behind the outer face, m
SNAP = 0.04          # max snap distance of an opening edge to a vertex coordinate, m
PANEL = 0.12         # boundary cell thickness (panel), m
MERGE_OVERLAP = 0.8  # stacked openings sharing this width fraction ...
MERGE_GAP = 0.3      # ... and separated by at most this band are one curtain strip, m
MIN_OPENING = 0.35   # narrower/shorter voids are sampling or detail noise -> wall, m
OPAQUE = ("Сэндвич", "Синий (RAL 5015)", "Плитка", "Кладка", "Бетон")
CLUSTER = 0.012      # opening edges closer than this share one cut (no sub-10 mm faces), m
# S3 -> Revit: X_rvt = 204.86 - y_s3, Y_rvt = x_s3 - 142.55 (STATE.md). Local = Revit - CENTRE.
S3_TO_RVT = (204.86, 142.55)
CENTRE_RVT = (37.17, 54.00)   # centre of the outer-face bbox X -19.28..93.62, Y -0.28..108.28
# Outer panel faces (facade_planes_v001.json) in the local frame: L-shaped footprint, CCW.
X0, XA, X1 = -19.28 - 37.17, -0.62 - 37.17, 93.62 - 37.17
Y0, YA, Y1 = -0.28 - 54.00, 56.28 - 54.00, 108.28 - 54.00
RING = [(X0, Y0), (X1, Y0), (X1, Y1), (XA, Y1), (XA, YA), (X0, YA)]

opaque = [o for o in bpy.data.objects if o.type == "MESH" and any(k in o.name for k in OPAQUE)]


def to_local(p):
    """S3 FBX -> Revit (fit residual <= 0.02 m) -> local frame centred on the building bbox."""
    xr, yr = S3_TO_RVT[0] - p[1], p[0] - S3_TO_RVT[1]
    return Vector((xr - CENTRE_RVT[0], yr - CENTRE_RVT[1], p[2]))


verts, polys = [], []
for o in opaque:
    base = len(verts)
    verts.extend(to_local(o.matrix_world @ v.co) for v in o.data.vertices)
    polys.extend([base + i for i in p.vertices] for p in o.data.polygons)
bvh = BVHTree.FromPolygons(verts, polys)
V = np.array([tuple(v) for v in verts])

runs, items, registry = [], [], {"opaque_objects": [o.name for o in opaque]}
for ri, (a, b) in enumerate(zip(RING, RING[1:] + RING[:1]), 1):
    a, b = np.array(a), np.array(b)
    d = b - a
    u_ax = int(np.argmax(abs(d)))
    n_ax = 1 - u_ax
    outward = np.array([d[1], -d[0]]) / np.linalg.norm(d)
    plane = a[n_ax]
    u0, u1 = sorted((a[u_ax], b[u_ax]))
    us = np.arange(u0 + STEP / 2, u1, STEP)
    zs = np.arange(STEP / 2, H, STEP)
    wall = np.zeros((len(us), len(zs)), bool)
    direction = Vector((-outward[0], -outward[1], 0))
    for i, u in enumerate(us):
        for j, z in enumerate(zs):
            p = [0.0, 0.0, z]
            p[u_ax] = u
            p[n_ax] = plane + outward[n_ax] * 0.3
            hit = bvh.ray_cast(Vector(p), direction, 0.3 + DEPTH)
            wall[i, j] = hit[0] is not None
    # vertex coordinates of the opaque layer near this plane, for edge snapping
    near = V[abs(V[:, n_ax] - plane) < DEPTH + 0.05]
    snap_u, snap_z = np.unique(np.round(near[:, u_ax], 4)), np.unique(np.round(near[:, 2], 4))

    def snap(value, pool):
        if len(pool):
            k = pool[np.argmin(abs(pool - value))]
            if abs(k - value) <= SNAP:
                return float(k), True
        return float(value), False

    # greedy maximal rectangles over the void mask
    void = ~wall
    seen = np.zeros_like(void)
    openings = []
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
            lo_u, ok1 = snap(us[i] - STEP / 2, snap_u)
            hi_u, ok2 = snap(us[i1] + STEP / 2, snap_u)
            lo_z, ok3 = (0.0, True) if j == 0 else snap(zs[j] - STEP / 2, snap_z)
            hi_z, ok4 = (H, True) if j1 == len(zs) - 1 else snap(zs[j1] + STEP / 2, snap_z)
            lo_u, hi_u = max(lo_u, u0), min(hi_u, u1)
            if hi_u - lo_u < 0.2 or hi_z - lo_z < 0.2:
                continue  # sampling noise, not an opening
            openings.append({"u": [lo_u, hi_u], "z": [lo_z, hi_z], "snapped": all((ok1, ok2, ok3, ok4))})
    # A continuous curtain strip is split by slab edges behind the glass: merge stacked
    # openings that share >= MERGE_OVERLAP of their width and are separated by <= MERGE_GAP.
    merged = True
    while merged:
        merged = False
        for p in openings:
            for q in openings:
                if p is q:
                    continue
                ov = min(p["u"][1], q["u"][1]) - max(p["u"][0], q["u"][0])
                width = min(p["u"][1] - p["u"][0], q["u"][1] - q["u"][0])
                gap = max(p["z"][0], q["z"][0]) - min(p["z"][1], q["z"][1])
                if width > 0 and ov / width >= MERGE_OVERLAP and gap <= MERGE_GAP:
                    p["u"] = [min(p["u"][0], q["u"][0]), max(p["u"][1], q["u"][1])]
                    p["z"] = [min(p["z"][0], q["z"][0]), max(p["z"][1], q["z"][1])]
                    p["snapped"] = p["snapped"] and q["snapped"]
                    p["merged"] = p.get("merged", 1) + q.get("merged", 1)
                    openings.remove(q)
                    merged = True
                    break
            if merged:
                break
    dropped_slivers = [op for op in openings if min(op["u"][1] - op["u"][0], op["z"][1] - op["z"][0]) < MIN_OPENING]
    openings = [op for op in openings if op not in dropped_slivers]
    runs.append({"run": ri, "plane_axis": "xy"[n_ax], "u_axis": u_ax, "n_axis": n_ax, "plane": plane, "u_range": [u0, u1],
                 "wall_fraction": float(wall.mean()), "openings": openings,
                 "dropped_slivers": dropped_slivers})


def consolidate(values, anchors):
    """Map values closer than CLUSTER to one representative; anchors (run ends, 0, H) win."""
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


zmap = consolidate([z for r in runs for op in r["openings"] for z in op["z"]], {0.0, H})
moved = 0.0
for r in runs:
    umap = consolidate([u for op in r["openings"] for u in op["u"]], set(r["u_range"]))
    for k, op in enumerate(r["openings"], 1):
        new_u, new_z = [umap[u] for u in op["u"]], [zmap[z] for z in op["z"]]
        moved = max(moved, *(abs(a - b) for a, b in zip(op["u"] + op["z"], new_u + new_z)))
        op["u"], op["z"] = new_u, new_z
        op["id"] = oid = f"S3-op-{r['run']}-{k}"
        corners = []
        for uu in op["u"]:
            for zz in op["z"]:
                q = [0.0, 0.0, zz]
                q[r["u_axis"]] = uu
                q[r["n_axis"]] = r["plane"]
                corners.append(q)
        items.append({"props": {"revit_element_id": oid, "source": "S3 opaque-layer void"}, "vertices": corners})

# Grid axes: footprint lines, panel insets on both sides, opening edges.
xs = {c + d for c in (X0, XA, X1) for d in (-PANEL, 0.0, PANEL)}
ys = {c + d for c in (Y0, YA, Y1) for d in (-PANEL, 0.0, PANEL)}
zs_ax = {0.0, H}
for r in runs:
    for op in r["openings"]:
        (xs if r["plane_axis"] == "y" else ys).update(op["u"])
        zs_ax.update(op["z"])
ax = [np.array(sorted(s)) for s in (xs, ys, zs_ax)]
cx, cy, cz = [(v[:-1] + v[1:]) / 2 for v in ax]
X, Y = np.meshgrid(cx, cy, indexing="ij")
inside = ((X > XA) & (X < X1) & (Y > Y0) & (Y < Y1)) | ((X > X0) & (X <= XA) & (Y > Y0) & (Y < YA))
owner = np.repeat(inside[:, :, None], len(cz), axis=2).astype(np.int32)
for r in runs:
    for op in r["openings"]:
        u_lo, u_hi = op["u"]; z_lo, z_hi = op["z"]
        zmask = (cz > z_lo) & (cz < z_hi)
        if r["plane_axis"] == "y":   # plane y = const, u along x
            umask = (cx > u_lo) & (cx < u_hi)
            vmask = abs(cy - r["plane"]) < PANEL
            owner[np.ix_(umask, vmask, zmask)] = 0
        else:
            umask = (cy > u_lo) & (cy < u_hi)
            vmask = abs(cx - r["plane"]) < PANEL
            owner[np.ix_(vmask, umask, zmask)] = 0

frame = {"frame": "local = Revit - CENTRE_RVT, metres, angle 0", "s3_to_revit": S3_TO_RVT, "centre_revit": CENTRE_RVT}
OUT.mkdir(parents=True, exist_ok=False)
np.savez_compressed(OUT / "body-grid.npz", x=ax[0], y=ax[1], z=ax[2], owner=owner, angle=np.float64(0.0))
(OUT / "contour-source.json").write_text(json.dumps({**frame, "items": items}, ensure_ascii=False), encoding="utf-8")
(OUT / "owner-registry.json").write_text(json.dumps({**registry, **frame, "owner_1": "opaque facade layer (S3)"}, ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "grid-report.json").write_text(json.dumps({
    **frame, "height_m": H, "step_m": STEP, "depth_m": DEPTH, "snap_m": SNAP, "cluster_m": CLUSTER,
    "max_cluster_move_m": moved, "ring": RING, "grid_shape": list(owner.shape), "openings": len(items),
    "unsnapped_openings": sum(1 for r in runs for op in r["openings"] if not op["snapped"]),
    "runs": runs}, ensure_ascii=False, indent=1), encoding="utf-8")
print("DONE openings", len(items), "grid", owner.shape, "max move", moved)

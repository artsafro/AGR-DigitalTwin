"""Ray-sample what fills every BODY opening in the S3 source (class + depth), local frame.

    blender --background <psu275_full_src.blend> --python jobs/PSU275/scripts/sample_openings.py -- \
        <exterior-surface.json> <out.npz>

Rays start 0.3 m outside the facade plane, go inward up to MAX_DEPTH. The first hit gives the
fill class (by source object name) and its depth behind the facade plane. Also stores, per
opening, vertex u/z coordinates of glass and frame objects near the plane for edge snapping.
"""
import json
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

surface_json, out_npz = sys.argv[sys.argv.index("--") + 1:]
STEP, MAX_DEPTH = 0.025, 1.5
SKIP = ("Желтый", "Box", "Plane", "Cylinder", "Line", "Text", "Generic", "Layer", "Настил", "Пол")
CLASSES = [("glass", ("Стекло",)), ("frame", ("Белый RAL 9016", "Белый RAL 9017", "Белый ма")),
           ("door", ("Темно-Сер", "Серый RAL 7004", "Серый темный", "ПВХ")),
           ("louvre", ("Алюкобонд", "оцинкованная")), ("wall", ("Сэндвич", "Синий", "Бетон", "Кладка", "Плитка"))]
S3_TO_RVT, CENTRE_RVT = (204.86, 142.55), (37.17, 54.00)


def cls_of(name):
    for k, (c, keys) in enumerate(CLASSES, 1):
        if any(s in name for s in keys):
            return k
    return len(CLASSES) + 1  # other


verts, polys, poly_cls, cls_verts = [], [], [], {}
for o in bpy.data.objects:
    if o.type != "MESH" or any(k in o.name for k in SKIP) or not o.data.polygons:
        continue
    me = o.data
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    M = np.array(o.matrix_world); co = co @ M[:3, :3].T + M[:3, 3]
    co = np.stack([S3_TO_RVT[0] - co[:, 1] - CENTRE_RVT[0], co[:, 0] - S3_TO_RVT[1] - CENTRE_RVT[1], co[:, 2]], 1)
    base = len(verts)
    verts.extend(map(tuple, co))
    k = cls_of(o.name)
    for p in me.polygons:
        polys.append([base + i for i in p.vertices]); poly_cls.append(k)
    cls_verts.setdefault(k, []).append(co)
bvh = BVHTree.FromPolygons(verts, polys)
poly_cls = np.array(poly_cls, dtype=np.int8)
snap_src = np.concatenate([np.concatenate(cls_verts[k]) for k in (1, 2) if k in cls_verts])

surface = json.load(open(surface_json, encoding="utf-8"))
arrays, index = {}, []
for pi, prof in enumerate(surface["profiles"]):
    a, u_ax, plane = prof["axis"], prof["along_axis"], prof["plane"]
    out = np.array(prof["outward"] + [0.0])
    direction = Vector(tuple(-out))
    for oi, op in enumerate(prof["openings"]):
        u0, z0, u1, z1 = op["bounds_uz"]
        us = np.arange(u0 + STEP / 2, u1, STEP); zs = np.arange(z0 + STEP / 2, z1, STEP)
        cls = np.zeros((len(us), len(zs)), np.int8); depth = np.full((len(us), len(zs)), np.nan, np.float32)
        for i, u in enumerate(us):
            for j, z in enumerate(zs):
                q = [0.0, 0.0, z]; q[u_ax] = u; q[a] = plane + out[a] * 0.3
                loc, nrm, fi, dist = bvh.ray_cast(Vector(q), direction, 0.3 + MAX_DEPTH)
                if fi is not None:
                    cls[i, j] = poly_cls[fi]; depth[i, j] = dist - 0.3
        key = f"{pi}_{oi}"
        near = snap_src[(abs(snap_src[:, a] - (plane - out[a] * 0.2)) < 0.6) &
                        (snap_src[:, u_ax] > u0 - 0.1) & (snap_src[:, u_ax] < u1 + 0.1) &
                        (snap_src[:, 2] > z0 - 0.1) & (snap_src[:, 2] < z1 + 0.1)]
        arrays[f"cls_{key}"] = cls; arrays[f"depth_{key}"] = depth
        arrays[f"us_{key}"] = us; arrays[f"zs_{key}"] = zs
        arrays[f"snapu_{key}"] = np.unique(np.round(near[:, u_ax], 4)); arrays[f"snapz_{key}"] = np.unique(np.round(near[:, 2], 4))
        index.append([pi, oi])
arrays["index"] = np.array(index); arrays["step"] = np.float64(STEP)
arrays["class_names"] = np.array(["none"] + [c for c, _ in CLASSES] + ["other"])
np.savez_compressed(out_npz, **arrays)
print("DONE openings", len(index))

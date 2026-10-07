"""Ray-sample the opaque wall layer on every massing profile plane (local frame).

    blender --background <psu275_full_src.blend> --python jobs/PSU275/scripts/sample_wall_masks.py -- <profiles.json> <out.npz>

For each profile: wall[i, j] = an opaque face lies within [-0.3, +DEPTH] of the outer plane
along the inward normal at (u_i, z_j). Also stores vertex u/z coordinates of the opaque layer
near the plane for edge snapping. No shapely here; masking by the profile is done downstream.
"""
import json
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

profiles_json, out_npz = sys.argv[sys.argv.index("--") + 1:]
STEP, DEPTH = 0.05, 0.2
OPAQUE = ("Сэндвич", "Синий (RAL 5015)", "Плитка", "Кладка", "Бетон", "Алюкобонд")
S3_TO_RVT, CENTRE_RVT = (204.86, 142.55), (37.17, 54.00)


def to_local(p):
    return Vector((S3_TO_RVT[0] - p[1] - CENTRE_RVT[0], p[0] - S3_TO_RVT[1] - CENTRE_RVT[1], p[2]))


objs = [o for o in bpy.data.objects if o.type == "MESH" and any(k in o.name for k in OPAQUE)]
verts, polys = [], []
for o in objs:
    base = len(verts)
    verts.extend(to_local(o.matrix_world @ v.co) for v in o.data.vertices)
    polys.extend([base + i for i in p.vertices] for p in o.data.polygons)
bvh = BVHTree.FromPolygons(verts, polys)
V = np.array([tuple(v) for v in verts])
profiles = json.load(open(profiles_json, encoding="utf-8"))["profiles"]
arrays = {"step": np.float64(STEP), "depth": np.float64(DEPTH)}
for k, p in enumerate(profiles):
    a, u_ax, plane = p["axis"], p["along_axis"], p["plane"]
    out = np.array(p["outward"] + [0.0])
    u0, z0, u1, z1 = p["bounds_uz"]
    us = np.arange(u0 + STEP / 2, u1, STEP)
    zs = np.arange(z0 + STEP / 2, z1, STEP)
    wall = np.zeros((len(us), len(zs)), bool)
    direction = Vector(tuple(-out))
    for i, u in enumerate(us):
        for j, z in enumerate(zs):
            q = [0.0, 0.0, z]
            q[u_ax] = u
            q[a] = plane + out[a] * 0.3
            wall[i, j] = bvh.ray_cast(Vector(q), direction, 0.3 + DEPTH)[0] is not None
    near = V[abs(V[:, a] - plane) < DEPTH + 0.05]
    arrays[f"wall_{k}"] = wall
    arrays[f"us_{k}"] = us
    arrays[f"zs_{k}"] = zs
    arrays[f"snapu_{k}"] = np.unique(np.round(near[:, u_ax], 4))
    arrays[f"snapz_{k}"] = np.unique(np.round(near[:, 2], 4))
    print("profile", k, "xy"[a], plane, wall.shape, round(float(wall.mean()), 3), flush=True)
np.savez_compressed(out_npz, **arrays)
print("DONE", len(profiles))

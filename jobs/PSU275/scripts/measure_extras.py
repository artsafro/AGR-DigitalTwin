"""Measure S3 extra structures (chimney, tanks, transformer, ducts) in the local frame.

    blender --background --factory-startup --python jobs/PSU275/scripts/measure_extras.py -- <S3.fbx> <out.json>

Per selected object: bbox, triangles, material slots with face counts and z ranges, and for
round objects the radius profile (mean distance of vertices from the plan centre per 1 m band).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import bpy
import numpy as np

src, out = sys.argv[sys.argv.index("--") + 1:]
S3_TO_RVT, CENTRE_RVT = (204.86, 142.55), (37.17, 54.00)
PICK = ("Труба", "Cylinder00", "Layer:0_металл", "трансформатор", "трубы", "здание с трубами", "StairHandrail")
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
res = {}
for o in bpy.context.scene.objects:
    if o.type != "MESH" or not any(k in o.name for k in PICK):
        continue
    me = o.data
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    M = np.array(o.matrix_world); co = co @ M[:3, :3].T + M[:3, 3]
    loc = np.stack([S3_TO_RVT[0] - co[:, 1] - CENTRE_RVT[0], co[:, 0] - S3_TO_RVT[1] - CENTRE_RVT[1], co[:, 2]], 1)
    lo, hi = loc.min(0), loc.max(0)
    mats = defaultdict(lambda: [0, 1e9, -1e9])
    for p in me.polygons:
        name = o.material_slots[p.material_index].material.name if o.material_slots and o.material_slots[p.material_index].material else "-"
        z = loc[list(p.vertices), 2]
        m = mats[name]; m[0] += 1; m[1] = min(m[1], z.min()); m[2] = max(m[2], z.max())
    row = {"tris": sum(len(p.vertices) - 2 for p in me.polygons), "lo": lo.round(3).tolist(), "hi": hi.round(3).tolist(),
           "materials": {k: [v[0], round(v[1], 2), round(v[2], 2)] for k, v in mats.items()}}
    c = (lo[:2] + hi[:2]) / 2
    r = np.linalg.norm(loc[:, :2] - c, axis=1)
    prof = []
    for z0 in np.arange(np.floor(lo[2]), hi[2], 1.0 if hi[2] - lo[2] < 40 else 5.0):
        m = (loc[:, 2] >= z0) & (loc[:, 2] < z0 + (1.0 if hi[2] - lo[2] < 40 else 5.0))
        if m.any():
            prof.append([round(float(z0), 1), round(float(r[m].max()), 3), round(float(r[m].min()), 3), int(m.sum())])
    row["centre"] = c.round(3).tolist(); row["radius_profile"] = prof
    res[o.name] = row
Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("DONE", len(res))

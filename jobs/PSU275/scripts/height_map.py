"""Top-down height map of the opaque building envelope (walls, roofs) in the local frame.

    blender --background <psu275_full_src.blend> --python jobs/PSU275/scripts/height_map.py -- <out.npz> <out.json>

Local frame as build_floor1_grid.py: Revit metres minus the building bbox centre.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

out_npz, out_json = sys.argv[sys.argv.index("--") + 1:]
STEP = 0.25
OPAQUE = ("Сэндвич", "Синий (RAL 5015)", "Кровля", "Бетон", "Кладка", "Плитка", "Алюкобонд")
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
lo, hi = V.min(0), V.max(0)
xs = np.arange(lo[0] + STEP / 2, hi[0], STEP)
ys = np.arange(lo[1] + STEP / 2, hi[1], STEP)
top = np.full((len(xs), len(ys)), np.nan)
down = Vector((0, 0, -1))
for i, x in enumerate(xs):
    for j, y in enumerate(ys):
        hit = bvh.ray_cast(Vector((x, y, 90.0)), down, 100.0)
        if hit[0] is not None:
            top[i, j] = hit[0].z
np.savez_compressed(out_npz, x=xs, y=ys, top=top)
levels = Counter(np.round(top[np.isfinite(top)], 2).tolist())
rows = []
for z, n in levels.most_common(40):
    mask = np.isclose(top, z, atol=0.005)
    ii, jj = np.nonzero(mask)
    rows.append({"z": z, "area_m2": round(n * STEP * STEP, 1),
                 "x": [round(float(xs[ii.min()]), 2), round(float(xs[ii.max()]), 2)],
                 "y": [round(float(ys[jj.min()]), 2), round(float(ys[jj.max()]), 2)]})
Path(out_json).write_text(json.dumps({"objects": [o.name for o in objs], "step_m": STEP,
                                      "bounds": [lo.tolist(), hi.tolist()], "levels": rows},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
print("DONE", len(objs), "objects; top levels", rows[:12])

"""Connected mesh islands of selected S3 objects with PCA shape descriptors (local frame).

    blender --background --factory-startup --python jobs/PSU275/scripts/measure_islands.py -- <S3.fbx> <out.json> <name-substring> [...]

Per island: vertex count, bbox, centre, principal axes and extents (PCA), roundness of the cross
section (ratio of the two minor extents) - input for primitive replacement (box / n-gon prism).
"""
import json
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

args = sys.argv[sys.argv.index("--") + 1:]
src, out, keys = args[0], args[1], args[2:]
S3_TO_RVT, CENTRE_RVT = (204.86, 142.55), (37.17, 54.00)
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
res = {}
for o in bpy.context.scene.objects:
    if o.type != "MESH" or not any(k in o.name for k in keys):
        continue
    bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
    bm.verts.ensure_lookup_table()
    seen, islands = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, isl = [v], []
        seen.add(v.index)
        while stack:
            w = stack.pop(); isl.append(w.index)
            for e in w.link_edges:
                u = e.other_vert(w)
                if u.index not in seen:
                    seen.add(u.index); stack.append(u)
        islands.append(isl)
    co = np.array([tuple(v.co) for v in bm.verts])
    loc = np.stack([S3_TO_RVT[0] - co[:, 1] - CENTRE_RVT[0], co[:, 0] - S3_TO_RVT[1] - CENTRE_RVT[1], co[:, 2]], 1)
    rows = []
    for isl in islands:
        P = loc[isl]
        c = P.mean(0)
        if len(P) >= 3:
            w, V = np.linalg.eigh(np.cov((P - c).T))
            V = V[:, ::-1]
            proj = (P - c) @ V
            ext = (proj.max(0) - proj.min(0)).tolist()
            mid = c + V @ ((proj.max(0) + proj.min(0)) / 2)
        else:
            V = np.eye(3); ext = [0, 0, 0]; mid = c
        rows.append({"n": len(P), "lo": P.min(0).round(3).tolist(), "hi": P.max(0).round(3).tolist(),
                     "centre": np.round(mid, 3).tolist(), "axes": np.round(V.T, 4).tolist(), "ext": np.round(ext, 3).tolist()})
    rows.sort(key=lambda r: -np.prod([max(e, 0.01) for e in r["ext"]]))
    res[o.name] = rows
    bm.free()
Path(out).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
print("DONE", {k: len(v) for k, v in res.items()})

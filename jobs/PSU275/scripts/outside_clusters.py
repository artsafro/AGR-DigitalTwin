"""Source faces outside the massing footprint (portals, vestibules, canopies), vectorised.

    blender --background <psu275_full_src.blend> --python jobs/PSU275/scripts/outside_clusters.py -- <masses.json> <out.npz>

Writes face centres, areas, normals and object ids (local frame) of every face whose centre is
more than OUT_TOL outside all mass footprints. Clustering is done downstream (numpy/scipy).
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

masses_json, out = sys.argv[sys.argv.index("--") + 1:]
OUT_TOL = 0.05
SKIP = ("Желтый", "Box", "Plane", "Cylinder", "Line", "Text", "Generic", "Layer")
S3_TO_RVT, CENTRE_RVT = (204.86, 142.55), (37.17, 54.00)
masses = json.loads(Path(masses_json).read_text(encoding="utf-8"))["masses"]
names, C, A, N, OID, LO, HI = [], [], [], [], [], [], []
for o in bpy.data.objects:
    if o.type != "MESH" or any(k in o.name for k in SKIP) or not o.data.polygons:
        continue
    me = o.data
    n = len(me.polygons)
    c = np.empty(n * 3); me.polygons.foreach_get("center", c); c = c.reshape(-1, 3)
    nr = np.empty(n * 3); me.polygons.foreach_get("normal", nr); nr = nr.reshape(-1, 3)
    a = np.empty(n); me.polygons.foreach_get("area", a)
    M = np.array(o.matrix_world)
    c = c @ M[:3, :3].T + M[:3, 3]
    nr = nr @ M[:3, :3].T
    local = np.stack([S3_TO_RVT[0] - c[:, 1] - CENTRE_RVT[0], c[:, 0] - S3_TO_RVT[1] - CENTRE_RVT[1], c[:, 2]], 1)
    nloc = np.stack([-nr[:, 1], nr[:, 0], nr[:, 2]], 1)
    inside = np.zeros(n, bool)
    for m in masses:
        inside |= ((local[:, 0] >= m["x"][0] - OUT_TOL) & (local[:, 0] <= m["x"][1] + OUT_TOL) &
                   (local[:, 1] >= m["y"][0] - OUT_TOL) & (local[:, 1] <= m["y"][1] + OUT_TOL))
    keep = ~inside & (local[:, 2] > 0.05)
    # per-face vertex bbox (local frame)
    nv = len(me.vertices)
    co = np.empty(nv * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    co = np.stack([S3_TO_RVT[0] - co[:, 1] - CENTRE_RVT[0], co[:, 0] - S3_TO_RVT[1] - CENTRE_RVT[1], co[:, 2]], 1)
    lv = np.empty(len(me.loops), int); me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(n, int); me.polygons.foreach_get("loop_start", ls)
    pts = co[lv]
    lo = np.minimum.reduceat(pts, ls, axis=0); hi = np.maximum.reduceat(pts, ls, axis=0)
    if keep.any():
        names.append(o.name)
        C.append(local[keep]); A.append(a[keep]); N.append(nloc[keep]); OID.append(np.full(keep.sum(), len(names) - 1))
        LO.append(lo[keep]); HI.append(hi[keep])
np.savez_compressed(out, centres=np.concatenate(C), areas=np.concatenate(A), normals=np.concatenate(N),
                    object_ids=np.concatenate(OID), object_names=np.array(names),
                    lo=np.concatenate(LO), hi=np.concatenate(HI))
print("DONE", len(names), "objects", int(sum(len(x) for x in C)), "faces")

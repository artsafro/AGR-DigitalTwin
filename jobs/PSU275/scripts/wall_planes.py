"""Vertical opaque wall planes (axis, coordinate, area, u/z extents) in the local frame.

    blender --background <psu275_full_src.blend> --python jobs/PSU275/scripts/wall_planes.py -- <out.json>
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Vector

out = sys.argv[sys.argv.index("--") + 1]
OPAQUE = ("Сэндвич", "Синий (RAL 5015)", "Алюкобонд")
S3_TO_RVT, CENTRE_RVT = (204.86, 142.55), (37.17, 54.00)


def to_local(p):
    return Vector((S3_TO_RVT[0] - p[1] - CENTRE_RVT[0], p[0] - S3_TO_RVT[1] - CENTRE_RVT[1], p[2]))


acc = defaultdict(lambda: {"area": 0.0, "u": [1e9, -1e9], "z": [1e9, -1e9], "objects": set()})
for o in bpy.data.objects:
    if o.type != "MESH" or not any(k in o.name for k in OPAQUE):
        continue
    for p in o.data.polygons:
        n = p.normal
        if abs(n.z) > 0.05:
            continue
        pts = [to_local(o.matrix_world @ o.data.vertices[i].co) for i in p.vertices]
        # S3 -> local swaps axes: S3 normal x -> local y, S3 normal y -> local -x
        if abs(n.y) > 0.99:
            axis, u = 0, 1
        elif abs(n.x) > 0.99:
            axis, u = 1, 0
        else:
            continue
        key = (axis, round(sum(q[axis] for q in pts) / len(pts), 2))
        a = acc[key]
        a["area"] += p.area
        a["u"] = [min(a["u"][0], *(q[u] for q in pts)), max(a["u"][1], *(q[u] for q in pts))]
        a["z"] = [min(a["z"][0], *(q.z for q in pts)), max(a["z"][1], *(q.z for q in pts))]
        a["objects"].add(o.name)
rows = [{"axis": "xy"[k[0]], "coord": k[1], "area": round(v["area"], 1),
         "u": [round(t, 2) for t in v["u"]], "z": [round(t, 2) for t in v["z"]], "objects": sorted(v["objects"])}
        for k, v in acc.items() if v["area"] > 15]
rows.sort(key=lambda r: -r["area"])
Path(out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print("DONE", len(rows))

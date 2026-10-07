"""Inventory of S3 objects that are not the main building envelope (stairs, chimney, transformer, racks...).

    blender --background --factory-startup --python jobs/PSU275/scripts/inventory_extras.py -- <S3.fbx> <masses.json> <out.json>

Local frame as the other PSU275 scripts. Every mesh object gets bbox, triangle count, materials and a
class guess: inside = bbox within the massing footprint (+0.3 m), outside, or overlapping.
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

src, masses_json, out = sys.argv[sys.argv.index("--") + 1:]
S3_TO_RVT, CENTRE_RVT = (204.86, 142.55), (37.17, 54.00)
masses = json.loads(Path(masses_json).read_text(encoding="utf-8"))["masses"]
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
rows = []
for o in bpy.context.scene.objects:
    if o.type != "MESH" or not o.data.vertices:
        continue
    co = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    M = np.array(o.matrix_world); co = co @ M[:3, :3].T + M[:3, 3]
    loc = np.stack([S3_TO_RVT[0] - co[:, 1] - CENTRE_RVT[0], co[:, 0] - S3_TO_RVT[1] - CENTRE_RVT[1], co[:, 2]], 1)
    lo, hi = loc.min(0), loc.max(0)
    tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
    within = lambda p: any(m["x"][0] - 0.3 <= p[0] <= m["x"][1] + 0.3 and m["y"][0] - 0.3 <= p[1] <= m["y"][1] + 0.3 for m in masses)
    inside_share = float(np.mean([within(p) for p in loc[:: max(1, len(loc) // 2000)]]))
    rows.append({"name": o.name, "tris": tris, "lo": lo.round(2).tolist(), "hi": hi.round(2).tolist(),
                 "inside_share": round(inside_share, 2),
                 "materials": [s.material.name for s in o.material_slots if s.material][:4]})
rows.sort(key=lambda r: -r["tris"])
Path(out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print("DONE", len(rows))

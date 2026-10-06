"""Dump per-object bounds/materials of KPP1 Revit FBX groups to JSON (one file per group)."""
import bpy, sys, json, os
from mathutils import Vector
src, out = sys.argv[sys.argv.index("--") + 1:][:2]
os.makedirs(out, exist_ok=True)
for f in sorted(os.listdir(src)):
    if not f.endswith(".fbx"): continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=os.path.join(src, f))
    rows = []
    for o in bpy.data.objects:
        if o.type != "MESH": continue
        ws = [o.matrix_world @ Vector(c) for c in o.bound_box]
        rows.append({"name": o.name, "data": o.data.name, "users": o.data.users,
                     "min": [round(min(w[i] for w in ws), 4) for i in range(3)],
                     "max": [round(max(w[i] for w in ws), 4) for i in range(3)],
                     "mats": [s.material.name for s in o.material_slots if s.material],
                     "tris": sum(len(p.vertices) - 2 for p in o.data.polygons),
                     "parent": o.parent.name if o.parent else None})
    json.dump(rows, open(os.path.join(out, f[:-4] + ".objects.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("DUMP", f, len(rows))

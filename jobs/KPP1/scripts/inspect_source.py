"""Import KPP1 Revit FBX groups into Blender and report names, units and bounds."""
import bpy, sys, json, os
from mathutils import Vector
src = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
report = {}
for f in sorted(os.listdir(src)):
    if not f.endswith(".fbx"): continue
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(src, f))
    objs = [o for o in bpy.data.objects if o not in before]
    lo, hi = Vector((1e9,)*3), Vector((-1e9,)*3); tris = 0
    for o in objs:
        if o.type != "MESH": continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c); lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
        tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
    report[f] = {"objects": len(objs), "types": sorted({o.type for o in objs}),
                 "sample": [(o.name, tuple(round(s, 4) for s in o.matrix_world.to_scale())) for o in objs[:4]],
                 "min": [round(v, 3) for v in lo], "max": [round(v, 3) for v in hi], "tris": tris}
print("REPORT", json.dumps(report, ensure_ascii=False, indent=1))

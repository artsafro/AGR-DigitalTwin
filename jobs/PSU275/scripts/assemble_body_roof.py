"""Assemble BODY shell + ROOF wells into one new .blend and read it back.

    blender --background --factory-startup --python jobs/PSU275/scripts/assemble_body_roof.py -- \
        <BODY_SHELL.blend> <roof-wells.json> <out.blend> <readback.json>
"""
import json
import sys
from pathlib import Path

import bpy

body_blend, out_blend, out_json, *mesh_jsons = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_homefile(use_empty=True)  # no default cube/camera/light
with bpy.data.libraries.load(body_blend) as (src, dst):
    dst.objects = list(src.objects)
for o in dst.objects:
    if o is not None:
        bpy.context.scene.collection.objects.link(o)
PREVIEW = {"glass": (0.25, 0.4, 0.55, 1), "frame_RAL9016": (0.95, 0.95, 0.93, 1), "door_RAL7004": (0.6, 0.6, 0.6, 1),
           "louvre_RAL9016": (0.85, 0.85, 0.85, 1), "void_dark": (0.05, 0.05, 0.05, 1)}
for path in mesh_jsons:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    mesh = doc["mesh"]
    me = bpy.data.meshes.new(mesh["name"])
    me.from_pydata(mesh["vertices"], [], mesh["faces"])
    me.validate()
    ob = bpy.data.objects.new(mesh["name"], me)
    bpy.context.scene.collection.objects.link(ob)
    if doc.get("material_names") and mesh.get("materials"):
        for name in doc["material_names"]:
            mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
            mat.diffuse_color = PREVIEW.get(name, (0.8, 0.8, 0.8, 1))
            me.materials.append(mat)
        me.polygons.foreach_set("material_index", mesh["materials"])
        me.update()
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
bpy.ops.wm.open_mainfile(filepath=out_blend)
rows = []
for o in bpy.context.scene.objects:
    if o.type == "MESH":
        rows.append({"name": o.name, "vertices": len(o.data.vertices), "faces": len(o.data.polygons),
                     "quads": sum(1 for p in o.data.polygons if len(p.vertices) == 4),
                     "z_range": [min(v.co.z for v in o.data.vertices), max(v.co.z for v in o.data.vertices)]})
Path(out_json).write_text(json.dumps({"blend": out_blend, "objects": rows}, indent=1), encoding="utf-8")
print("ASSEMBLED", rows)

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
for path in mesh_jsons:
    mesh = json.loads(Path(path).read_text(encoding="utf-8"))["mesh"]
    me = bpy.data.meshes.new(mesh["name"])
    me.from_pydata(mesh["vertices"], [], mesh["faces"])
    me.validate()
    bpy.context.scene.collection.objects.link(bpy.data.objects.new(mesh["name"], me))
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

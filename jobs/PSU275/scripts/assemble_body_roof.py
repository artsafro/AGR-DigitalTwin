"""Assemble BODY shell + ROOF wells into one new .blend and read it back.

    blender --background --factory-startup --python jobs/PSU275/scripts/assemble_body_roof.py -- \
        <BODY_SHELL.blend> <roof-wells.json> <out.blend> <readback.json>
"""
import json
import sys
from pathlib import Path

import bpy

body_blend, roof_json, out_blend, out_json = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_homefile(use_empty=True)  # no default cube/camera/light
with bpy.data.libraries.load(body_blend) as (src, dst):
    dst.objects = list(src.objects)
for o in dst.objects:
    if o is not None:
        bpy.context.scene.collection.objects.link(o)
roof = json.loads(Path(roof_json).read_text(encoding="utf-8"))["mesh"]
me = bpy.data.meshes.new(roof["name"])
me.from_pydata(roof["vertices"], [], roof["faces"])
me.validate()
ob = bpy.data.objects.new(roof["name"], me)
bpy.context.scene.collection.objects.link(ob)
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

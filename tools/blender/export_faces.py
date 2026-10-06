"""Export world-space faces of an FBX as JSON for tools/qa/check_clearance.py.

    blender --background --factory-startup --python-exit-code 1 \
        --python tools/blender/export_faces.py -- <model.fbx> <faces.json>

Output: [{"object": name, "index": polygon index, "points": [[x, y, z], ...]}]. Read-only.
"""
import json
import sys
from pathlib import Path

import bpy

src, out = (Path(a).resolve() for a in sys.argv[sys.argv.index("--") + 1:][:2])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(src))
faces = []
for obj in bpy.context.scene.objects:
    if obj.type != "MESH":
        continue
    world = [obj.matrix_world @ v.co for v in obj.data.vertices]
    for poly in obj.data.polygons:
        faces.append({"object": obj.name, "index": poly.index,
                      "points": [list(world[i]) for i in poly.vertices]})
out.write_text(json.dumps(faces), encoding="utf-8")
print("TWINQA_FACES", len(faces))

"""Close-up Workbench render (local frame) with back-face culling, for QA of slits and back faces.

    blender --background <file.blend> --python jobs/PSU275/scripts/render_closeup.py -- <out.png> cx cy cz size az_deg el_deg
"""
import math
import sys

import bpy
from mathutils import Vector

out, cx, cy, cz, size, az, el = sys.argv[sys.argv.index("--") + 1:]
cx, cy, cz, size, az, el = map(float, (cx, cy, cz, size, az, el))
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "MATERIAL"
sc.display.shading.show_backface_culling = True
sc.render.resolution_x, sc.render.resolution_y = 1400, 1000
for o in sc.objects:
    if o.name.startswith("UCX_"):
        o.hide_render = True
cam_data = bpy.data.cameras.new("cu"); cam_data.type = "ORTHO"; cam_data.ortho_scale = size; cam_data.clip_end = 1000
cam = bpy.data.objects.new("cu", cam_data); sc.collection.objects.link(cam); sc.camera = cam
a, e = math.radians(az), math.radians(el)
d = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
c = Vector((cx, cy, cz))
cam.location = c + d * 200
cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("DONE", out)

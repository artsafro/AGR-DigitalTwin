"""Workbench preview renders of an opened .blend (two isometric views).

    blender --background <file.blend> --python jobs/PSU275/scripts/render_preview.py -- <out_prefix>
"""
import math
import sys

import bpy
from mathutils import Vector

prefix = sys.argv[sys.argv.index("--") + 1]
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_cavity = True
scene.render.resolution_x, scene.render.resolution_y = 1800, 1100
scene.render.film_transparent = False
meshes = [o for o in scene.objects if o.type == "MESH"]
grey = bpy.data.materials.new("preview_grey"); grey.diffuse_color = (0.75, 0.78, 0.82, 1)
for o in meshes:
    if not o.data.materials:
        o.data.materials.append(grey)
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
centre, size = (lo + hi) / 2, (hi - lo).length
cam_data = bpy.data.cameras.new("preview")
cam_data.type = "ORTHO"
cam_data.ortho_scale = size * 1.1
cam = bpy.data.objects.new("preview", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
for name, azimuth in (("sw", 225), ("ne", 45)):
    a = math.radians(azimuth)
    cam.location = centre + Vector((math.cos(a), math.sin(a), 0.7)).normalized() * size
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{prefix}_{name}.png"
    bpy.ops.render.render(write_still=True)
print("DONE", prefix)

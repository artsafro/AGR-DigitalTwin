"""Workbench render of an S3 region given in the PSU275 local frame (material-coloured).

    blender --background <src.blend> --python jobs/PSU275/scripts/render_region.py -- <out.png> x0 x1 y0 y1 z1 azimuth_deg
"""
import math
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
out = args[0]
x0, x1, y0, y1, z1, az = map(float, args[1:])
S3_TO_RVT, CENTRE_RVT = (204.86, 142.55), (37.17, 54.00)


def to_s3(x, y):
    return (y + CENTRE_RVT[1]) + S3_TO_RVT[1], S3_TO_RVT[0] - (x + CENTRE_RVT[0])


scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_cavity = True
scene.render.resolution_x, scene.render.resolution_y = 1600, 1100
cx, cy = to_s3((x0 + x1) / 2, (y0 + y1) / 2)
centre = Vector((cx, cy, z1 / 2))
size = max(x1 - x0, y1 - y0, z1) * 1.6
cam_data = bpy.data.cameras.new("region"); cam_data.type = "ORTHO"; cam_data.ortho_scale = size
cam = bpy.data.objects.new("region", cam_data); scene.collection.objects.link(cam); scene.camera = cam
# azimuth given in the local frame; local +x = S3 -y, local +y = S3 +x
a = math.radians(az)
dl = Vector((math.cos(a), math.sin(a)))
d = Vector((dl.y, -dl.x, 0.6)).normalized()
cam.location = centre + d * size * 2
cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
cam_data.clip_end = size * 10
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("DONE", out)

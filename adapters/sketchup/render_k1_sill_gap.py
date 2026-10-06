"""Diagnostic close-up of the upper transition sill seam."""
import bpy
from pathlib import Path
from mathutils import Vector
root=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(root/'GLB_K1_assembled_v023.blend'))
scene=bpy.context.scene
scene.render.engine='BLENDER_WORKBENCH'
scene.display.shading.light='STUDIO'
scene.display.shading.color_type='OBJECT'
scene.display.shading.show_cavity=True
for o in bpy.data.objects:
 if o.type!='MESH':continue
 o.color=(.65,.65,.65,1)
 if o.name=='TOP_<auto>26':o.color=(.9,.55,.2,1)
 if o.name.startswith('TOP_Window'):o.color=(.15,.4,.7,1)
 if o.name=='K1_TOP_REVEALS_10MM':o.color=(.25,.7,.35,1)
target=Vector((8.27,20.65,66.5))
cam=scene.camera
cam.location=target+Vector((-5,7,5))
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=7
scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.filepath=str(root/'top-sill-gap-v023.png')
bpy.ops.render.render(write_still=True)
target=Vector((5.443,12.446,71.15))
cam.location=target+Vector((-5.5,.6,1.2))
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.ortho_scale=3.7
scene.render.filepath=str(root/'top-upper-window-v023.png')
bpy.ops.render.render(write_still=True)
cam.location=target+Vector((-4.5,-2.7,1.4))
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(root/'top-upper-window-oblique-v023.png')
bpy.ops.render.render(write_still=True)
print('RENDER',scene.render.filepath)

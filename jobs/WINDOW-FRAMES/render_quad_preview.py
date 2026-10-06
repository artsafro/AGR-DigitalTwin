"""Render a read-only overview of the saved simplified frames."""
import bpy
from mathutils import Vector
from pathlib import Path

out=Path(__file__).resolve().parent/'outputs'/'window_frames_quad_v002_preview.png'
o=bpy.data.objects['WindowFrames_Quad_v002']
o.color=(0.9,0.68,0.25,1.0)
corners=[o.matrix_world @ Vector(c) for c in o.bound_box]
center=sum(corners,Vector())/8
cam_data=bpy.data.cameras.new('PreviewCamera')
cam=bpy.data.objects.new('PreviewCamera',cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location=center+Vector((90,-115,65))
direction=center-cam.location
cam.rotation_euler=direction.to_track_quat('-Z','Y').to_euler()
cam_data.type='ORTHO'
cam_data.ortho_scale=105
scene=bpy.context.scene
scene.camera=cam
scene.render.engine='BLENDER_WORKBENCH'
scene.display.shading.color_type='OBJECT'
scene.display.shading.light='STUDIO'
scene.display.shading.show_cavity=True
scene.display.shading.background_type='VIEWPORT'
scene.display.shading.background_color=(0.94,0.95,0.96)
scene.render.resolution_x=1600
scene.render.resolution_y=1100
scene.render.resolution_percentage=100
scene.render.filepath=str(out)
bpy.ops.render.render(write_still=True)
print(str(out))

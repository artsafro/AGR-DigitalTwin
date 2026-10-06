"""Render body with inserted frames from exterior orthographic views."""
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/body-v005'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'SOSH1150_Body_Openings_Replaced_v005.blend'))
scene=bpy.context.scene
scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=2400
scene.render.resolution_y=1400
scene.render.resolution_percentage=100
scene.display.shading.color_type='MATERIAL'
scene.display.shading.light='STUDIO'
scene.display.shading.show_shadows=False
scene.display.shading.show_cavity=True
scene.display.shading.cavity_type='BOTH'
scene.display.shading.background_type='WORLD'
world=bpy.data.worlds.new('BODY_PREVIEW_WORLD')
world.color=(.75,.77,.79)
scene.world=world
data=bpy.data.cameras.new('BODY_PREVIEW_CAMERA')
cam=bpy.data.objects.new('BODY_PREVIEW_CAMERA',data)
scene.collection.objects.link(cam)
scene.camera=cam
data.type='ORTHO'
views=[
    ('body-facade-long.png',Vector((-150,0,11)),Vector((0,0,11)),135),
    ('body-facade-short.png',Vector((0,-150,11)),Vector((0,0,11)),85),
    ('body-frames-close.png',Vector((-100,-15,10)),Vector((-29,-15,10)),24),
]
for filename,location,target,scale in views:
    cam.location=location
    cam.rotation_euler=(target-location).to_track_quat('-Z','Y').to_euler()
    data.ortho_scale=scale
    scene.render.filepath=str(OUT/filename)
    bpy.ops.render.render(write_still=True)
    print('Rendered',filename)
scene.display.shading.color_type='OBJECT'
bpy.data.objects['skolka'].color=(.36,.38,.40,1)
cam.location=Vector((-150,0,11))
cam.rotation_euler=(Vector((0,0,11))-cam.location).to_track_quat('-Z','Y').to_euler()
data.ortho_scale=135
scene.render.filepath=str(OUT/'body-review-map.png')
bpy.ops.render.render(write_still=True)
print('Rendered body-review-map.png')

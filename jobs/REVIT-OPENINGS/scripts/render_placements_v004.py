"""Render two overall workbench elevations from the saved placement scene."""
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/placements-v004'
bpy.ops.wm.open_mainfile(filepath=str(OUT / 'SOSH1150_FBX_Openings_Placed_v004.blend'))
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = 2400
scene.render.resolution_y = 1400
scene.render.resolution_percentage = 100
scene.display.shading.color_type = 'OBJECT'
scene.display.shading.light = 'STUDIO'
scene.display.shading.show_shadows = False
scene.display.shading.show_cavity = True
scene.display.shading.background_type = 'WORLD'
world = bpy.data.worlds.new('PLACEMENT_PREVIEW_BACKGROUND')
world.color = (.72, .74, .76)
scene.world = world
camdata = bpy.data.cameras.new('PLACEMENT_PREVIEW_CAMERA')
camera = bpy.data.objects.new('PLACEMENT_PREVIEW_CAMERA', camdata)
scene.collection.objects.link(camera)
scene.camera = camera
camdata.type = 'ORTHO'
views = [
    ('elevation-long-side.png', Vector((30, -150, 11)), Vector((30, 54, 11)), 90),
    ('elevation-short-side.png', Vector((-150, 55, 11)), Vector((30, 55, 11)), 135),
]
for filename, location, target, scale in views:
    camera.location = location
    camera.rotation_euler = (target-location).to_track_quat('-Z','Y').to_euler()
    camdata.ortho_scale = scale
    scene.render.filepath = str(OUT / filename)
    bpy.ops.render.render(write_still=True)
    print('Rendered', filename)

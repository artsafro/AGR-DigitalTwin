import bpy, math
from pathlib import Path
from mathutils import Vector
root=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION/outputs/v001')
bpy.ops.wm.open_mainfile(filepath=str(root/'source_import.blend'))
s=bpy.context.scene
s.render.engine='BLENDER_WORKBENCH';s.render.resolution_x=1200;s.render.resolution_y=1200;s.render.resolution_percentage=100
s.display.shading.light='STUDIO';s.display.shading.color_type='MATERIAL';s.display.shading.show_shadows=True;s.display.shading.show_cavity=True
s.display.shading.background_type='VIEWPORT';s.display.shading.background_color=(0.12,0.12,0.12)
cam=bpy.data.objects.new('AuditCamera',bpy.data.cameras.new('AuditCamera'));s.collection.objects.link(cam);s.camera=cam
cam.data.type='ORTHO';cam.data.ortho_scale=18500;cam.data.clip_end=100000
cam.location=(2300,3800,30000);cam.rotation_euler=(0,0,0)
for name in ['Ground','Relef']:
    for o in s.objects:
        if o.type=='MESH':o.hide_render=o.name!=name
    s.render.filepath=str(root/f'{name}_top.png');bpy.ops.render.render(write_still=True)


import bpy
from pathlib import Path
from mathutils import Vector
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001')
s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH';s.render.resolution_x=1200;s.render.resolution_y=1100;s.render.resolution_percentage=100
sh=s.display.shading;sh.light='STUDIO';sh.color_type='MATERIAL';sh.show_shadows=True;sh.show_cavity=True;sh.cavity_type='BOTH';sh.background_type='WORLD';s.world.color=(.10,.10,.10)
cam=bpy.data.objects.new('MasterPreviewCamera',bpy.data.cameras.new('MasterPreviewCamera'));s.collection.objects.link(cam);s.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=77
for tag,delta in [('A',(90,-110,80)),('B',(-100,100,70))]:
 t=Vector((122,-43,17));cam.location=t+Vector(delta);cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler()
 s.render.filepath=str(out/('MASTER-'+tag+'.png'));bpy.ops.render.render(write_still=True)

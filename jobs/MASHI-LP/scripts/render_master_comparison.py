import bpy
from pathlib import Path
from mathutils import Vector
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001');s=bpy.context.scene
s.render.engine='BLENDER_WORKBENCH';s.render.resolution_x=1600;s.render.resolution_y=850;s.render.resolution_percentage=100
sh=s.display.shading;sh.light='STUDIO';sh.color_type='MATERIAL';sh.show_cavity=True;sh.cavity_type='BOTH';sh.show_shadows=True;sh.background_type='WORLD';s.world.color=(.12,.12,.12)
cam=bpy.data.objects.new('CompareCam',bpy.data.cameras.new('CompareCam'));s.collection.objects.link(cam);s.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=170
t=Vector((72,-43,17));cam.location=t+Vector((50,-140,85));cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler()
s.render.filepath=str(out/'LP-and-MASTER.png');bpy.ops.render.render(write_still=True)

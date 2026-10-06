import bpy
from pathlib import Path
from mathutils import Vector
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001')
s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH';s.render.resolution_x=700;s.render.resolution_y=650;s.render.resolution_percentage=100
s.display.shading.light='STUDIO';s.display.shading.color_type='SINGLE';s.display.shading.single_color=(.65,.65,.65);s.display.shading.show_cavity=True
cam=bpy.data.objects.new('InspectCam',bpy.data.cameras.new('InspectCam'));s.collection.objects.link(cam);s.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=72
t=Vector((22,-43,17));cam.location=t+Vector((90,-110,70));cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler()
for col in bpy.data.collections:col.hide_render=False
for name in ['MultiMat_5','MultiMat_6','MultiMat_20','Material #215','Material #206','Material #218']:
 for o in s.objects:
  if o.type=='MESH':o.hide_render=o.name!=name
 s.render.filepath=str(out/(name.replace('#','')+'.png'));bpy.ops.render.render(write_still=True)

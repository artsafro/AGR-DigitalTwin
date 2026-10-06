import bpy,json
from pathlib import Path
from mathutils import Vector
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001');rows=json.loads((out/'glass-panels.json').read_text())
candidates=[]
for row in rows:
 pts=[Vector(p) for f in row['faces'] for p in f['coords']];c=sum(pts,Vector())/len(pts)
 if 10<c.x<30 and c.y<-60 and 17<c.z<26 and .7<row['area']<5:candidates.append((abs(c.x-20)+abs(c.z-22),c))
target=min(candidates,key=lambda p:p[0])[1]+Vector((100,0,0))
s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH';s.render.resolution_x=1100;s.render.resolution_y=1000;s.render.resolution_percentage=100
sh=s.display.shading;sh.light='STUDIO';sh.color_type='MATERIAL';sh.show_shadows=True;sh.show_cavity=True;sh.cavity_type='BOTH';sh.background_type='WORLD';s.world.color=(.13,.13,.13)
cam=bpy.data.objects.new('FrameDetailCamera',bpy.data.cameras.new('FrameDetailCamera'));s.collection.objects.link(cam);s.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=5.5
cam.location=target+Vector((3,-8,2));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();s.render.filepath=str(out/'MASTER-frame-detail.png');bpy.ops.render.render(write_still=True)
print('target',list(target))

"""Map diagnostic close-up pixels to source objects and face heights."""
import bpy,json
from pathlib import Path
from mathutils import Vector
root=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(root/'GLB_K1_assembled_v023.blend'))
scene=bpy.context.scene;cam=scene.camera
target=Vector((8.27,20.65,66.5));cam.location=target+Vector((-5,7,5))
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=7
deps=bpy.context.evaluated_depsgraph_get();rot=cam.matrix_world.to_3x3()
right=rot@Vector((1,0,0));up=rot@Vector((0,1,0));forward=rot@Vector((0,0,-1))
rows=[]
for y in (900,920,940,960):
 for x in (250,330,400,450,500,550,600,700):
  origin=cam.location+right*((x-500)/1000*7)+up*((500-y)/1000*7)
  hit,point,normal,face,obj,mat=scene.ray_cast(deps,origin,forward,distance=100)
  rows.append([x,y,obj.name if hit else None,face if hit else None,[round(v,3) for v in point] if hit else None])
print('PICKS='+json.dumps(rows))

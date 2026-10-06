"""Ray section through the suspected gap below an upper window."""
import bpy,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(root/'GLB_K1_assembled_v023.blend'))
obj=bpy.data.objects['TOP_Window_0.002']
c=sum((obj.matrix_world@v.co for v in obj.data.vertices),Vector())/4
out=Vector((-.995227,.097586,0))
trees=[]
for o in bpy.data.objects:
 if o.type!='MESH' or not (o.name.startswith('TOP_') or o.name=='K1_TYPICAL_NPM' or o.name=='K1_TOP_REVEALS_10MM'):continue
 trees.append((o.name,BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(p.vertices) for p in o.data.polygons])))
rows=[]
for z in (69.89,69.905,69.93,69.96,69.99,70.02,70.04,70.07,70.12):
 p=Vector((c.x,c.y,z));hits=[]
 for name,tree in trees:
  h,n,f,d=tree.ray_cast(p+out*.8,-out,1.6)
  if h is not None:hits.append((round(.8-d,4),name,f,round(n.dot(out),3)))
 rows.append((z,sorted(hits,reverse=True)))
print('SECTION='+json.dumps(rows,ensure_ascii=False))

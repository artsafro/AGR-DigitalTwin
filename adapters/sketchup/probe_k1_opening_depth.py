"""Measure exterior wall plane beside a representative top opening."""
import bpy,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(root/'GLB_K1_assembled_v022.blend'))
rows=[]
for name in ('TOP_Window_0.002','TOP_Window_0.001'):
 o=bpy.data.objects[name]
 vs=[o.matrix_world@o.data.vertices[i].co for i in o.data.polygons[0].vertices]
 c=sum(vs,Vector())/4
 lo=[v for v in vs if v.z< c.z]
 t=(lo[1]-lo[0]).normalized()
 n=(o.matrix_world.to_3x3()@o.data.polygons[0].normal).normalized()
 rad=Vector((c.x-14.25,c.y-6,0));out=n if n.dot(rad)>=0 else -n
 width=max(v.dot(t) for v in vs)-min(v.dot(t) for v in vs)
 height=max(v.z for v in vs)-min(v.z for v in vs)
 bvh=[]
 for wall in bpy.data.objects:
  if not wall.name.startswith('TOP_') or wall.name.startswith(('TOP_Window','TOP_AC')) or wall.type!='MESH':continue
  bvh.append((wall.name,BVHTree.FromPolygons([wall.matrix_world@v.co for v in wall.data.vertices],[list(p.vertices) for p in wall.data.polygons])))
 probes=[]
 for label,p in [('middle',c),('left',c-t*(width/2+.03)),('right',c+t*(width/2+.03)),('top',c+Vector((0,0,height/2+.03))),('bottom',c-Vector((0,0,height/2+.03)))]:
  hits=[]
  for wall,tree in bvh:
   h,hn,face,d=tree.ray_cast(p+out*.8,-out,1.6)
   if h is not None:hits.append([round(.8-d,4),wall,face,round(hn.dot(out),3)])
  probes.append((label,sorted(hits,reverse=True)[:8]))
 rows.append({'name':name,'center':list(c),'outward':list(out),'width':width,'height':height,'probes':probes})
print('OPENING_DEPTH='+json.dumps(rows,ensure_ascii=False))

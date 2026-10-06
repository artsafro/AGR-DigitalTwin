import bpy,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out.parent/'clearance-ab-v007/GLB_AB_clearance_v007.blend'))
verts=[];faces=[]
for o in bpy.data.objects:
 if o.type!='MESH' or o.get('role') in ['ac','simple_sills']:continue
 start=len(verts);verts.extend(o.matrix_world@v.co for v in o.data.vertices)
 faces.extend([start+i for i in p.vertices] for p in o.data.polygons)
tree=BVHTree.FromPolygons(verts,faces,all_triangles=False)
result={}
for o in bpy.data.objects:
 if o.type!='MESH' or not (o.name.endswith('Материал3') or o.name.endswith('Материал') or '<auto>52' in o.name):continue
 rows=[]
 for p in o.data.polygons:
  n=(o.matrix_world.to_3x3()@p.normal).normalized()
  if abs(n.z)>.01:continue
  points=[o.matrix_world@o.data.vertices[i].co for i in p.vertices];center=sum(points,Vector())/len(points)
  samples=[center]+[center*.65+v*.35 for v in points]
  visible=0
  for sample in samples:
   escaped=False
   for i in range(128):
    a=(i+.31)*math.tau/128;d=Vector((math.cos(a),math.sin(a),0))
    if d.dot(n)<.02:continue
    hit=tree.ray_cast(sample+n*.0002,d,100)
    if hit[0] is None:escaped=True;break
   visible+=escaped
  rows.append({'index':p.index,'outside_visible_samples':visible,'sample_count':len(samples)})
 result[o.name]=rows
(out/'body-visibility.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:{'total':len(v),'interior_candidates':sum(r['outside_visible_samples']==0 for r in v)} for k,v in result.items()},ensure_ascii=True))

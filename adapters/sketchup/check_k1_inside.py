"""Probe the assembled typical facade from interior positions; back faces expected."""
import bpy,json,math,sys
from pathlib import Path
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
filename=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'K1_with_top_draft_v011.blend'
bpy.ops.wm.open_mainfile(filepath=str(out/filename))
objects=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('K1_')]
verts=[];faces=[];ids=[]
for o in objects:
 start=len(verts);verts.extend(o.matrix_world@v.co for v in o.data.vertices)
 for p in o.data.polygons:faces.append([start+i for i in p.vertices]);ids.append((o.name,p.index))
tree=BVHTree.FromPolygons(verts,faces,all_triangles=False);bad={};bad_z={};examples=[];missing=0;total=0
rows=json.loads((out/'floor-instances.json').read_text())
for row in rows:
 m=Matrix(row['matrix_inches']);m.translation*=.0254
 for xy in [(15.94,16.85),(13.94,16.85),(17.94,16.85),(15.94,14.85),(15.94,18.85)]:
  for z in [.5,.985,1.02,1.5,2.2,3.28]:
   origin=m@Vector((*xy,z+.02))
   for i in range(768):
    a=(i%256+.31)*math.tau/256;direction=Vector((math.cos(a),math.sin(a),[-.7,0,.7][i//256])).normalized()
    loc,n,index,d=tree.ray_cast(origin,direction,100);total+=1
    if loc is None:missing+=1;continue
    if n.dot(direction)<-.001:
     key=str(ids[index]);
     if len(examples)<20 and ids[index][0]=='K1_WINDOWS':examples.append({'face':ids[index],'origin':list(origin),'direction':list(direction),'hit':list(loc),'normal':list(n)})
     bad[key]=bad.get(key,0)+1;bad_z[str(z)]=bad_z.get(str(z),0)+1
report={'examples':examples,'front_hits_by_relative_z':bad_z,'rays':total,'front_faces_from_interior':bad,'front_hit_count':sum(bad.values()),'missing_facade_hits':missing,
 'scope':'Typical floors only; horizontal and inclined rays at 6 heights from 5 interior points per floor; top draft excluded; open top/bottom cause expected misses'}
(out/('interior-probe-'+Path(filename).stem+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
print('INSIDE',total,'front hits',sum(bad.values()),'faces',len(bad),'missing',missing)

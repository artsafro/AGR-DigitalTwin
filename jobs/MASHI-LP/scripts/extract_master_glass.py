import bpy,json,numpy as np
from pathlib import Path
from collections import defaultdict
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001')
vv=[];ff=[]
for o in bpy.data.collections['Revit'].objects:
 off=len(vv);vv.extend(o.matrix_world@v.co for v in o.data.vertices);ff.extend([tuple(off+i for i in f.vertices) for f in o.data.polygons])
bvh=BVHTree.FromPolygons(vv,ff);del vv,ff
o=bpy.data.objects['MultiMat_5'];v=[o.matrix_world@p.co for p in o.data.vertices]
comp=json.loads((out/'components.json').read_text())[0]['components'];rows=[]
for ci,c in enumerate(comp):
 groups=defaultdict(list)
 for fi in c['face_ids']:
  q=[v[i] for i in o.data.polygons[fi].vertices];n=(q[1]-q[0]).cross(q[2]-q[0]);area=n.length*.5
  if area<1e-6:continue
  n.normalize();d=n.dot(q[0]);key=tuple(round(x,4) for x in n)+(round(d,3),)
  groups[key].append(dict(coords=[list(p) for p in q],face=fi,area=area))
 options=[]
 for key,fs in groups.items():
  area=sum(f['area'] for f in fs)
  if area<.08:continue
  n=Vector(key[:3]);n.normalize()
  if n.z<-.15:continue
  points=[Vector(p) for f in fs for p in f['coords']];center=sum(points,Vector())/len(points)
  if center.z<-.1:continue
  exposed=bvh.ray_cast(center+n*.003,n,250)[0] is None
  if not exposed:
   tests=[sum([Vector(p) for p in f['coords']],Vector())/len(f['coords']) for f in fs]
   exposed=any(bvh.ray_cast(p+n*.003,n,250)[0] is None for p in tests[:8])
  if exposed:options.append((area,key,fs))
 if not options:continue
 # A glazing solid has two broad sides; retain the outward measured one only.
 for area,key,fs in sorted(options,reverse=True)[:1]:
  rows.append(dict(component=ci,normal=key[:3],d=key[3],area=area,faces=fs))
(out/'glass-panels.json').write_text(json.dumps(rows))
print('glass exterior panels',len(rows),'area',sum(r['area'] for r in rows))

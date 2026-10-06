"""Full contours of facade trim solids, not visibility-clipped triangles."""
import bpy,json,bmesh,math
from pathlib import Path
from collections import defaultdict
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001')
names=['MultiMat_22','MultiMat_26','Material #200','Material #230','Material #219','Object015','Object016','Object020','Object029']
groups=defaultdict(list)
for name in names:
 o=bpy.data.objects[name];bm=bmesh.new();bm.from_mesh(o.data)
 attr=bm.faces.layers.int.new('source_face')
 for i,f in enumerate(bm.faces):f[attr]=i
 for v in bm.verts:v.co=o.matrix_world@v.co
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00005)
 bmesh.ops.dissolve_limit(bm,angle_limit=.008,verts=list(bm.verts),edges=list(bm.edges),use_dissolve_boundaries=False)
 bm.normal_update()
 for f in bm.faces:
  q=[v.co.copy() for v in f.verts];n=f.normal.copy();area=f.calc_area()
  if area<.005:continue
  d=sum(n.dot(p) for p in q)/len(q);key=tuple(round(x,4) for x in n)+(round(d,3),)
  groups[key].append(dict(object=name,face=f[attr],coords=[list(p) for p in q],area=area))
 bm.free()
data=[dict(id=100000+i,normal=key[:3],d=key[3],area=sum(f['area'] for f in fs),faces=fs,full_profile=True) for i,(key,fs) in enumerate(groups.items())]
(out/'profile-planes.json').write_text(json.dumps(data))
print('profile planes',len(data))

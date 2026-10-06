"""Rebuild facade profiles as connected quad strips using measured Revit corners."""
import bpy,bmesh,json,numpy as np,math
from pathlib import Path
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001')
names=['MultiMat_22','MultiMat_26','Material #200','Material #230','Material #219']
result=[]
for name in names:
 o=bpy.data.objects[name];bm=bmesh.new();bm.from_mesh(o.data)
 for v in bm.verts:v.co=o.matrix_world@v.co
 layer=bm.faces.layers.int.new('ref_face')
 for i,f in enumerate(bm.faces):f[layer]=i
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0001)
 bmesh.ops.dissolve_degenerate(bm,dist=.00001,edges=list(bm.edges))
 # Reconstruct longitudinal strips across imported diagonals, including gently curved panels.
 bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4])
 bmesh.ops.join_triangles(bm,faces=list(bm.faces),angle_face_threshold=.1,angle_shape_threshold=math.pi,cmp_seam=False,cmp_sharp=False,cmp_uvs=False,cmp_vcols=False,cmp_materials=False)
 from collections import Counter
 print(name,'paired degrees',Counter(len(f.verts) for f in bm.faces),flush=True)
 bm.normal_update();bm.verts.index_update();vv=[list(v.co) for v in bm.verts];ff=[];source=[]
 for f in bm.faces:
  if f.calc_area()<1e-8:continue
  ids=[v.index for v in f.verts]
  if len(ids)==4:ff.append(ids);source.append(f[layer]);continue
  pts=np.array([vv[i] for i in ids]);center=len(vv);vv.append(pts.mean(axis=0).tolist());mids=[]
  for a,b in zip(pts,np.roll(pts,-1,axis=0)):mids.append(len(vv));vv.append(((a+b)/2).tolist())
  for i,vi in enumerate(ids):ff.append([vi,mids[i],center,mids[i-1]]);source.append(f[layer])
 # Collapse only exact duplicated output vertices, never feature widths.
 remap={};lookup={};verts=[]
 for i,p in enumerate(vv):
  key=tuple(round(x,6) for x in p)
  if key not in lookup:lookup[key]=len(verts);verts.append(p)
  remap[i]=lookup[key]
 faces=[[remap[i] for i in f] for f in ff]
 result.append(dict(vertices=verts,faces=faces,source_plane=-2,source_object=name,source_faces=source,normal=[0,0,0],area=sum(f.calc_area() for f in bm.faces),role='profiles',method='measured_profile_quad_strips'))
 print(name,'faces',len(faces),flush=True);bm.free()
(out/'profiles-quad.json').write_text(json.dumps(result))

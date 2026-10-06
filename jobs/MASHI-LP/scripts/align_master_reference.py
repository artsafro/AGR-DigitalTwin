import bpy,json,math,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001')
verts=[];faces=[]
for o in bpy.data.collections['Revit'].objects:
 if o.type!='MESH' or o.name!='MultiMat_5':continue
 off=len(verts);verts.extend([o.matrix_world@v.co for v in o.data.vertices]);faces.extend([tuple(off+i for i in p.vertices) for p in o.data.polygons])
bvh=BVHTree.FromPolygons(verts,faces)
old=bpy.data.objects['SM_MashiPoryvaevoj_34_004_MainGlass.002']
points=np.array([tuple(old.matrix_world@v.co) for v in old.data.vertices])
t=np.array([-14.005,-56.843,-17.686]);angle=-.004101659
for k in range(35):
 c,s=math.cos(angle),math.sin(angle);r=np.array([[c,-s,0],[s,c,0],[0,0,1.]])
 rp=points@r.T;q=rp+t;aa=[];bb=[];dist=[]
 for p,rot in zip(q,rp):
  loc,n,idx,d=bvh.find_nearest(Vector(p))
  if d>1.5:continue
  n=np.array(n);res=n@(p-np.array(loc));w=1/max(1,abs(res)/.1)
  aa.append(n*w);bb.append(-res*w);dist.append(d)
 delta=np.linalg.lstsq(aa,bb,rcond=None)[0];t+=delta[:3]
 if k%5==0:print(k,t,angle,np.percentile(dist,[25,50,90]),flush=True)
 if np.linalg.norm(delta)<1e-8:break
c,s=math.cos(angle),math.sin(angle);r=np.array([[c,-s,0],[s,c,0],[0,0,1.]])
result=dict(translation=t.tolist(),rotation_z_radians=angle,rotation=r.tolist(),residual_percentiles=np.percentile(dist,[25,50,90]).tolist())
(out/'old-alignment.json').write_text(json.dumps(result,indent=2))
print(result)


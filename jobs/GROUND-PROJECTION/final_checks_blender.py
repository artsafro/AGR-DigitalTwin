import bpy,json,hashlib
from pathlib import Path
import numpy as np
from mathutils.bvhtree import BVHTree
from mathutils import Vector
ROOT=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION/outputs/v003')
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'GROUND_projected_v003.blend'))
o=bpy.data.objects['GROUND_PROJECTED'];d=np.load(ROOT/'quad_mesh.npz')
out={'blend_readback':{'vertices':len(o.data.vertices),'quads':len(o.data.polygons),'all_quad':all(len(p.vertices)==4 for p in o.data.polygons),'material_slots':len(o.data.materials),'material_ids_equal':np.array_equal(np.array([p.material_index for p in o.data.polygons]),d['materials']),'visible_meshes':[x.name for x in bpy.context.scene.objects if x.type=='MESH' and not x.hide_get()]}}
rd=np.load(ROOT.parent/'v001/Relef_arrays.npz');rv=rd['v'];rf=rd['f'];tr=rv[rf]
n=np.cross(tr[:,1]-tr[:,0],tr[:,2]-tr[:,0]);valid=np.abs(n[:,2])/np.maximum(np.linalg.norm(n,axis=1),1e-30)>.001
n=n[valid];tr=tr[valid];rf=rf[valid]
planes=np.column_stack((-n[:,0]/n[:,2],-n[:,1]/n[:,2],np.einsum('ij,ij->i',n,tr[:,0])/n[:,2]))
bvh=BVHTree.FromPolygons(rv.tolist(),rf.tolist(),all_triangles=True)
v=d['vertices'];f=d['faces'];p=v[f];area=np.abs(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])[:,2]+np.cross(p[:,2]-p[:,0],p[:,3]-p[:,0])[:,2])*.5
rng=np.random.default_rng(27092026);ids=rng.choice(len(f),size=20000,replace=True,p=area/area.sum())
err=[];miss=0;worst=[]
for i in ids:
    pt=p[i,[0,1,2]].mean(axis=0)
    hit=bvh.ray_cast(Vector((pt[0],pt[1],1000)),Vector((0,0,-1)))
    if hit[2] is None:miss+=1;continue
    plane=planes[hit[2]];target=plane[0]*pt[0]+plane[1]*pt[1]+plane[2]
    delta=abs(pt[2]-target);err.append(delta)
    if delta>50:worst.append({'face':int(i),'xyz':pt.tolist(),'target_z':float(target),'error':float(delta)})
out['surface_fit_area_weighted_sample']={'samples':20000,'outside_relief':miss,'error_quantiles_source_world_units':np.quantile(err,[0,.5,.9,.95,.99,1]).tolist(),'fraction_error_over_1':float(np.mean(np.array(err)>1)),'fraction_error_over_10':float(np.mean(np.array(err)>10)),'note':'Approximation at sharp height steps; no exact riser conformity claimed.'}
(ROOT/'surface_worst_samples.json').write_text(json.dumps(worst,indent=2))
original=Path(r'C:/Users/artsafro/Downloads/Telegram Desktop/GROUND.fbx')
out['original_unchanged']=hashlib.sha256(original.read_bytes()).hexdigest()==json.loads((ROOT.parent/'v001/source_audit.json').read_text())['source_sha256']
(ROOT/'final_checks.json').write_text(json.dumps(out,indent=2,default=lambda x:bool(x)))
print(json.dumps(out,indent=2,default=lambda x:bool(x)))

import json,time,sys
from pathlib import Path
import numpy as np
import shapely as sh
from shapely import Polygon
ROOT=Path(__file__).parent/'outputs'/(sys.argv[2] if len(sys.argv)>2 else 'v001');t0=time.time()
filename=sys.argv[1] if len(sys.argv)>1 else 'quad_mesh.npz'
d=np.load(ROOT/filename);v=d['vertices'];f=d['faces'];m=d['materials'];pts=v[f]
n1=np.cross(pts[:,1]-pts[:,0],pts[:,2]-pts[:,0]);n2=np.cross(pts[:,2]-pts[:,0],pts[:,3]-pts[:,0]);area=(np.linalg.norm(n1,axis=1)+np.linalg.norm(n2,axis=1))*.5
keys=np.sort(f,axis=1);unique,counts=np.unique(keys,axis=0,return_counts=True)
edges=np.sort(np.concatenate([f[:,[i,(i+1)%4]] for i in range(4)]),axis=1)
eu,ec=np.unique(edges,axis=0,return_counts=True)
dupv=len(v)-len(np.unique(v,axis=0));loose=len(v)-len(np.unique(f))
bad=np.flatnonzero((area<1e-9)|~np.isfinite(area))
fold=np.flatnonzero((n1[:,2]*n2[:,2]<-1e-8))
out={'file':filename,'vertices':len(v),'quads':len(f),'exact_duplicate_vertices':dupv,'loose_vertices':loose,'duplicate_face_geometry':int(np.sum(counts-1)),'zero_area_faces':len(bad),'zero_area_face_examples':bad[:10].tolist(),'folded_xy_quads':len(fold),'folded_xy_examples':fold[:10].tolist(),'boundary_edges':int(np.sum(ec==1)),'nonmanifold_edges':int(np.sum(ec>2)),'shortest_edge':float(np.min(np.linalg.norm(v[eu[:,0]]-v[eu[:,1]],axis=1))),'smallest_face_area':float(np.min(area))}
print(json.dumps(out,indent=2),flush=True)
source=np.load(ROOT.parent/'v001/Ground_arrays.npz');sp=np.array([Polygon(t[:,:2]) for t in source['v'][source['f']]])
polys=np.array([Polygon(p[:,:2]) for p in pts]);valid=sh.is_valid(polys);out['invalid_xy_polygons_including_vertical']=int(np.sum(~valid))
polys=sh.make_valid(polys);positive=sh.area(polys)>1e-7
rows=[]
for mat in range(18):
    old=sh.union_all(sp[source['mat']==mat]);new=sh.union_all(polys[(m==mat)&positive])
    diff=old.symmetric_difference(new)
    rows.append({'material_id':mat+1,'source_union_area':old.area,'output_union_area':new.area,'symmetric_difference_area':diff.area,'relative_area_difference':diff.area/max(old.area,1e-30),'boundary_hausdorff':old.boundary.hausdorff_distance(new.boundary)})
    print('MAT',mat+1,'diff',round(diff.area,6),flush=True)
out['material_contours']=rows;out['seconds']=time.time()-t0
(ROOT/(Path(filename).stem+'_qa.json')).write_text(json.dumps(out,indent=2))

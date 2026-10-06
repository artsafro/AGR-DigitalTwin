import json,collections
from pathlib import Path
import numpy as np
import shapely as sh
ROOT=Path(__file__).parent/'outputs/v003'
src=np.load(ROOT.parent/'v001/Ground_arrays.npz');dst=np.load(ROOT/'fbx_geometry.npz')
def topology(v,f,mat):
    edges=np.sort(np.concatenate([f[:,[i,(i+1)%f.shape[1]]] for i in range(f.shape[1])]),axis=1)
    mm=np.tile(mat,f.shape[1]);eu,ec=np.unique(edges,axis=0,return_counts=True)
    labelled=np.column_stack((mm,edges));lu,lc=np.unique(labelled,axis=0,return_counts=True)
    return eu,ec,lu,lc
sv=src['v'];sf=src['f'];sm=src['mat'];dv=dst['vertices'];df=dst['faces'];dm=dst['materials']
se,sc,sl,slc=topology(sv,sf,sm);de,dc,dl,dlc=topology(dv,df,dm)
out={}
for name,mask,smask in [('boundary',dc==1,sc==1),('nonmanifold',dc>2,sc>2)]:
    source_lines=sh.union_all(sh.linestrings(sv[se[smask],:2]))
    samples=dv[de[mask],:2].reshape(-1,2)
    dist=sh.distance(sh.points(samples),source_lines)
    out[name]={'source_edges':int(smask.sum()),'output_edges':int(mask.sum()),'max_distance_to_source_edges':float(dist.max()),'samples_beyond_0_002':int((dist>.002).sum())}
rows=[]
for mat in range(18):
    old=sl[(sl[:,0]==mat)&(slc!=2),1:];new=dl[(dl[:,0]==mat)&(dlc!=2),1:]
    oldlines=sh.union_all(sh.linestrings(sv[old,:2]));newlines=sh.union_all(sh.linestrings(dv[new,:2]))
    a=sh.distance(sh.points(dv[new,:2].reshape(-1,2)),oldlines)
    b=sh.distance(sh.points(sv[old,:2].reshape(-1,2)),newlines)
    rows.append({'material_id':mat+1,'output_to_source_max':float(a.max()),'source_to_output_max':float(b.max())})
out['material_boundaries']=rows
(ROOT/'boundary_qa.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))

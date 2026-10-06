import json,numpy as np
from pathlib import Path
from collections import Counter
root=Path(__file__).resolve().parents[1]/'outputs';d=json.loads((root/'source.json').read_text());b=json.loads((root/'build.json').read_text())
v=np.array(b['vertices']);f=np.array(b['faces']);uv=np.clip(np.array(b['uv']),0,1);p=v[f]
area=np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1)/2+np.linalg.norm(np.cross(p[:,2]-p[:,0],p[:,3]-p[:,0]),axis=1)/2
ua=abs(np.sum(uv[:,:,0]*np.roll(uv[:,:,1],-1,axis=1)-uv[:,:,1]*np.roll(uv[:,:,0],-1,axis=1),axis=1))/2
td=4096*np.sqrt(ua/area)
parents=np.array(b['parents']);s=np.array(d['vertices']);sa=[]
sa=np.zeros(len(d['faces']))
for tri in d['triangles']:
    q=s[tri['vertices']];sa[tri['face']]+=np.linalg.norm(np.cross(q[1]-q[0],q[2]-q[0]))/2
tot=np.bincount(parents,weights=area,minlength=len(sa));delta=tot-np.array(sa)
edges=Counter(tuple(sorted((int(a),int(c)))) for face in f for a,c in zip(face,np.roll(face,-1)))
dup=len(f)-len({tuple(sorted(face)) for face in f})
report={'faces':len(f),'quads':len(f),'td_percentiles':np.percentile(td,[0,1,50,99,100]).tolist(),'degenerate':int((area<1e-12).sum()),'duplicate_faces':dup,'uv_bounds':[float(uv.min()),float(uv.max())],'out_of_tile':int(((uv<-1e-7)|(uv>1+1e-7)).sum()),'edge_multiplicity':dict(Counter(edges.values())),'source_area':float(sum(sa)),'result_area':float(sum(area)),'max_parent_area_error_m2':float(abs(delta).max()),'parent_area_mismatch':np.flatnonzero(abs(delta)>1e-5).tolist(),'unresolved_phase_edges':b['unresolved_phase_edges'],'delivery_passed':False,'margin_pixels':0,'scope':'UV trial; closure seams unresolved; not full AGR certification'}
(root/'qa-plan.json').write_text(json.dumps(report,indent=2));print(json.dumps({**report,'unresolved_phase_edges':len(b['unresolved_phase_edges'])}))

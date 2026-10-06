import json,numpy as np,shapely
from pathlib import Path
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011');desc=json.loads((out/'facade-sections.json').read_text());levels=desc['levels'];fs=json.loads((out/'v015-faces.json').read_text());changes={}
for f in fs:
 if f['object']!='K1_BODY' or f['material']!='<auto>58':continue
 p=np.array(f['points']);assert np.ptp(p[:,2])<.00001
 idx=min(range(len(levels)),key=lambda i:abs(p[:,2].mean()-levels[i]-1));typ='belt' if p[:,2].mean()<levels[idx]+1 else 'window'
 shape=shapely.Polygon(p[:,:2]).difference(shapely.from_wkt(desc['sections'][str(idx)+'_'+typ]));parts=[]
 fit=np.linalg.lstsq(np.c_[p[:,:2],np.ones(len(p))],np.array(f['uv']),rcond=None)[0];n=np.cross(p[1]-p[0],p[2]-p[0])
 for t in shapely.constrained_delaunay_triangles(shape).geoms:
  if t.area<1e-7:continue
  xy=np.array(t.exterior.coords)[:-1];xyz=np.c_[xy,np.full(3,p[0,2])]
  if np.cross(xyz[1]-xyz[0],xyz[2]-xyz[0])@n<0:xyz=xyz[::-1];xy=xy[::-1]
  parts.append({'points':xyz.tolist(),'uv':(np.c_[xy,np.ones(3)]@fit).tolist()})
 changes[str(f['index'])]=parts
(out/'misc-exterior-replacements.json').write_text(json.dumps(changes),encoding='utf-8');print('Misc hidden faces',sum(not v for v in changes.values()),'of',len(changes))

import json,numpy as np,shapely
from pathlib import Path
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011');rows=json.loads((out/'v020-poly-uv.json').read_text());pairs=json.loads((out/'final-v020-clearance.json').read_text())['pairs'];groups=[]
for r in pairs:
 group={r['a'][1],r['b'][1]};hits=[g for g in groups if g&group]
 for g in hits:group|=g;groups.remove(g)
 groups.append(group)
result=[]
for group in groups:
 first=rows[min(group)];p=np.array(first['points']);q=p-p.mean(0);n=np.cross(q,np.roll(q,-1,axis=0)).sum(0);n/=np.linalg.norm(n);d=n@p[0];drop=abs(n).argmax();axes=[i for i in range(3) if i!=drop]
 shape=shapely.union_all([shapely.Polygon(np.array(rows[i]['points'])[:,axes]) for i in group],grid_size=.00001).simplify(.00001,preserve_topology=True)
 parts=list(shape.geoms) if hasattr(shape,'geoms') else [shape];made=[]
 fit=np.linalg.lstsq(np.c_[p[:,axes],np.ones(len(p))],np.array(first['uv']),rcond=None)[0]
 for poly in parts:
  for piece in ([poly] if len(poly.exterior.coords)<=5 and not poly.interiors else shapely.constrained_delaunay_triangles(poly).geoms):
   xy=np.array(piece.exterior.coords)[:-1];xyz=np.zeros((len(xy),3));xyz[:,axes]=xy;xyz[:,drop]=(d-xyz@n)/n[drop]
   if np.cross(xyz[1]-xyz[0],xyz[2]-xyz[0])@n<0:xyz=xyz[::-1];xy=xy[::-1]
   made.append({'points':xyz.tolist(),'uv':(np.c_[xy,np.ones(len(xy))]@fit).tolist()})
 result.append({'old_indices':sorted(group),'replacement':made})
(out/'reveal-seam-unions.json').write_text(json.dumps(result),encoding='utf-8');print('Rejoined reveal seams',len(groups))

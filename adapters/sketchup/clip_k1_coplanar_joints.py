"""Partition coincident belt/pier faces in their shared plane, preserving UVs."""
import json,numpy as np
from pathlib import Path
from shapely.geometry import Polygon
from shapely.ops import unary_union,triangulate
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011')
fs=json.loads((out/'assembly-faces.json').read_text(encoding='utf-8'))
piers=[f for f in fs if f['object']=='K1_BODY' and f['material'] in ['Материал3','M_Reveal_Color']]
def plane(f):
 p=np.array(f['points']);n=np.cross(p[1]-p[0],p[2]-p[0]);n/=np.linalg.norm(n);return n,float(n@p[0])
planes=[plane(f) for f in piers];ns=np.array([p[0] for p in planes]);ds=np.array([p[1] for p in planes]);changes={}
for f in fs:
 if f['object']!='K1_BODY' or f['material']!='Материал':continue
 n,d=plane(f);p=np.array(f['points']);drop=int(abs(n).argmax());keep=[i for i in range(3) if i!=drop]
 poly=Polygon(p[:,keep]);cutters=[]
 for j in np.flatnonzero((ns@n>.999999)&(abs(np.array([np.mean(q['points'],axis=0) for q in piers])@n-d)<.00001)):
  q=Polygon(np.array(piers[j]['points'])[:,keep])
  if poly.intersection(q).area>1e-7:cutters.append(q)
 if not cutters:continue
 remainder=poly.difference(unary_union(cutters))
 uvmap=np.linalg.lstsq(np.c_[p[:,keep],np.ones(len(p))],np.array(f['uv']),rcond=None)[0]
 pieces=[]
 for tri in triangulate(remainder):
  if not remainder.covers(tri.representative_point()):continue
  xy=np.array(tri.exterior.coords)[:-1];xyz=np.zeros((3,3));xyz[:,keep]=xy;xyz[:,drop]=(d-xyz@n)/n[drop]
  uv=np.c_[xy,np.ones(3)]@uvmap
  if np.cross(xyz[1]-xyz[0],xyz[2]-xyz[0])@n<0:xyz=xyz[::-1];uv=uv[::-1]
  pieces.append({'points':xyz.tolist(),'uv':uv.tolist()})
 changes[str(f['index'])]=pieces
(out/'coplanar-body-replacements.json').write_text(json.dumps(changes),encoding='utf-8')
print('Partitioned belt faces',len(changes),'without bevel or XY offset')

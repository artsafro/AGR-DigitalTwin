import json
from pathlib import Path
from collections import Counter
import numpy as np
from shapely.geometry import Polygon,box,LineString
from shapely import make_valid,STRtree
out=Path(__file__).resolve().parents[1]/'outputs/master-v001'
objects=json.loads((out/'validated-geometry.json').read_text());faces=[]
for o in objects:
 vv=np.array(o['vertices'])
 for fi,ids in enumerate(o['faces']):
  p=vv[ids];n=np.cross(p[1]-p[0],p[2]-p[0]);length=np.linalg.norm(n)
  if length<1e-12:continue
  n/=length;axis=int(np.argmax(abs(n)));axes=[a for a in range(3) if a!=axis]
  poly=make_valid(Polygon(p[:,axes]))
  faces.append(dict(name=o['name'],face=fi,patch=o['patches'][fi],p=p,n=n,d=n@p[0],axis=axis,axes=axes,poly=poly,interior=poly.buffer(-.003)))
lo=np.array([f['p'].min(axis=0) for f in faces]);hi=np.array([f['p'].max(axis=0) for f in faces]);ns=np.array([f['n'] for f in faces])
trees=[]
for axis in range(3):
 axes=[a for a in range(3) if a!=axis]
 trees.append(STRtree([box(*(p[axes]-.002),*(q[axes]+.002)) for p,q in zip(lo,hi)]))
def intervals(g,start,direction):
 if g.is_empty:return []
 if g.geom_type=='LineString':
  t=(np.array(g.coords)-start)@direction/(direction@direction);return [(float(t.min()),float(t.max()))]
 return [v for c in getattr(g,'geoms',[]) for v in intervals(c,start,direction)]
overlaps=[];crossings=[]
for i,f in enumerate(faces):
 cand=trees[f['axis']].query(box(*(lo[i,f['axes']]-.002),*(hi[i,f['axes']]+.002)))
 cand=cand[(cand>i)&np.all(lo[cand]<=hi[i]+.002,axis=1)&np.all(hi[cand]>=lo[i]-.002,axis=1)]
 for j in cand:
  g=faces[j];dot=abs(f['n']@g['n']);record=dict(a=f['name'],af=f['face'],ap=f['patch'],b=g['name'],bf=g['face'],bp=g['patch'])
  if dot>.999999:
   sep=float(np.max(np.abs(g['p']@f['n']-f['d'])))
   if sep>.002:continue
   area=f['poly'].intersection(make_valid(Polygon(g['p'][:,f['axes']]))).area/abs(f['n'][f['axis']])
   if area>1e-5:overlaps.append(record|dict(area_m2=area,separation_m=sep))
   continue
  if f['interior'].is_empty or g['interior'].is_empty:continue
  direct=np.cross(f['n'],g['n']);direct/=np.linalg.norm(direct)
  p=np.linalg.lstsq(np.array([f['n'],g['n'],direct]),[f['d'],g['d'],0],rcond=None)[0]
  both=[]
  for item in [f,g]:
   axes=item['axes'];start=p[axes];d=direct[axes]
   both.append(intervals(item['interior'].intersection(LineString([start-d*300,start+d*300])),start,d))
  length=max([min(a1,b1)-max(a0,b0) for a0,a1 in both[0] for b0,b1 in both[1]],default=0)
  if length>.02:
   names={f['name'],g['name']}
   kind='designed_10mm_glass_capture' if names=={'MASTER_glass','MASTER_frames'} else 'review'
   crossings.append(record|dict(length_m=length,kind=kind))
 if i%5000==0:print('checked',i,'/',len(faces),flush=True)
report=dict(coplanar_count=len(overlaps),coplanar_area=sum(r['area_m2'] for r in overlaps),crossing_counts=dict(Counter(r['kind'] for r in crossings)),coplanar=overlaps,crossings=crossings)
(out/'intersections.json').write_text(json.dumps(report,indent=2))
print({k:v for k,v in report.items() if k not in ['coplanar','crossings']})

import json
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,LineString
from shapely import make_valid
from collections import Counter
out=Path(__file__).resolve().parents[1]/'outputs/model-v002'
objects=json.loads((out/'validated-geometry.json').read_text());faces=[]
for o in objects:
    vv=np.array(o['vertices'])
    for fi,ids in enumerate(o['faces']):
        p=vv[ids];n=np.cross(p[1]-p[0],p[2]-p[0]);length=np.linalg.norm(n)
        if length<1e-12:continue
        n/=length;axes=[a for a in range(3) if a!=int(np.argmax(np.abs(n)))]
        interior=make_valid(Polygon(p[:,axes])).buffer(-.003)
        faces.append({'name':o['name'],'new':o['new'],'face':fi,'p':p,'n':n,'d':n@p[0],'axes':axes,'poly':interior})
lo=np.array([f['p'].min(axis=0) for f in faces]);hi=np.array([f['p'].max(axis=0) for f in faces]);ns=np.array([f['n'] for f in faces])
def intervals(geom,start,direction):
    if geom.is_empty:return []
    if geom.geom_type=='LineString':
        arr=np.array(geom.coords);t=(arr-start)@direction/(direction@direction)
        return [(float(t.min()),float(t.max()))]
    return [v for g in getattr(geom,'geoms',[]) for v in intervals(g,start,direction)]
rows=[]
for i,f in enumerate(faces):
    if not f['new'] or f['poly'].is_empty:continue
    cand=np.flatnonzero(np.all(lo<hi[i]+.001,axis=1)&np.all(hi>lo[i]-.001,axis=1)&(np.abs(ns@f['n'])<.999999))
    for j in cand:
        g=faces[j]
        if (g['new'] and j<=i) or g['poly'].is_empty:continue
        direct=np.cross(f['n'],g['n']);length=np.linalg.norm(direct);direct/=length
        p=np.linalg.lstsq(np.array([f['n'],g['n'],direct]),np.array([f['d'],g['d'],0]),rcond=None)[0]
        intervals_both=[]
        for item in (f,g):
            axes=item['axes'];start=p[axes];d=direct[axes]
            intervals_both.append(intervals(item['poly'].intersection(LineString([start-d*300,start+d*300])),start,d))
        lengths=[min(a1,b1)-max(a0,b0) for a0,a1 in intervals_both[0] for b0,b1 in intervals_both[1]]
        overlap=max(lengths,default=0)
        if overlap>.02:rows.append({'a':f['name'],'af':f['face'],'b':g['name'],'bf':g['face'],'length_m':float(overlap),'kind':'new-new' if g['new'] else 'new-old'})
report={'method':'interior-interior plane intersection, 3mm face-edge exclusion, length >20mm','counts':dict(Counter(r['kind'] for r in rows)),'findings':rows}
(out/'crossing-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('CROSSINGS',report['counts'])
for r in sorted(rows,key=lambda r:-r['length_m'])[:5]:print(r)

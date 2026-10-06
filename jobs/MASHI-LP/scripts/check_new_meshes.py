"""Check candidate quads against each other and preserved LP in world metres."""
import json
from pathlib import Path
import numpy as np
from collections import Counter
from shapely.geometry import Polygon
from shapely import make_valid
out=Path(__file__).resolve().parents[1]/'outputs/model-v002'
new=json.loads((out/'new-meshes.json').read_text());old=json.loads((out/'lp-geometry.json').read_text())
if (out/'validated-geometry.json').exists():
    saved=json.loads((out/'validated-geometry.json').read_text());new=[o for o in saved if o['new']];old=[o for o in saved if not o['new']]
faces=[]
for group,objects in [('old',old),('new',new)]:
    for obj in objects:
        vv=np.array(obj['vertices'])
        for i,ids in enumerate(obj['faces']):
            pp=vv[ids];n=np.cross(pp[1]-pp[0],pp[2]-pp[0]);ln=np.linalg.norm(n)
            if ln<1e-12:continue
            n/=ln
            faces.append({'group':group,'name':obj['name'],'face':i,'p':pp,'n':n,'lo':pp.min(axis=0),'hi':pp.max(axis=0)})
los=np.array([f['lo'] for f in faces]);his=np.array([f['hi'] for f in faces]);normals=np.array([f['n'] for f in faces])
overlaps=[];seen=set()
for i,f in enumerate(faces):
    if f['group']!='new':continue
    candidates=np.flatnonzero(np.all(los<=f['hi']+.002,axis=1)&np.all(his>=f['lo']-.002,axis=1)&(np.abs(normals@f['n'])>.999999))
    axis=int(np.argmax(np.abs(f['n'])));proj=[j for j in range(3) if j!=axis]
    a=make_valid(Polygon(f['p'][:,proj]))
    for j in candidates:
        if i==j or (min(i,j),max(i,j)) in seen:continue
        g=faces[j];seen.add((min(i,j),max(i,j)))
        separation=np.max(np.abs((g['p']-f['p'][0])@f['n']))
        if separation>.002:continue
        b=make_valid(Polygon(g['p'][:,proj]));area=a.intersection(b).area/abs(f['n'][axis])
        if area>1e-5:
            overlaps.append({'a':f['name'],'af':f['face'],'b':g['name'],'bf':g['face'],'area_m2':area,'separation_m':float(separation),'kind':'new-new' if g['group']=='new' else 'new-old'})
counts=Counter(r['kind'] for r in overlaps)
(out/'overlap-check.json').write_text(json.dumps({'counts':counts,'findings':overlaps},indent=2),encoding='utf-8')
print('COPLANAR',dict(counts),'area',sum(r['area_m2'] for r in overlaps))
for row in sorted(overlaps,key=lambda r:-r['area_m2'])[:8]:print(row)

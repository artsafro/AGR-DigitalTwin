import json
from pathlib import Path
from collections import Counter
import os
ROOT=Path(os.environ['AGR_BOX_LIGHT_OUTPUT']).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
root=ROOT
d=json.loads((root/'box_light_source_audit.json').read_text())
objects={o['name']:o for o in d['objects']}
light=objects['box_light']; frame=objects['frames']
print('LIGHT',json.dumps(light))
v=frame['verts']; fs=frame['faces']
adj=[set() for _ in v]
for f in fs:
    for a in f['v']: adj[a].update(f['v'])
seen=set(); comps=[]
for i in range(len(v)):
    if i in seen: continue
    todo=[i]; seen.add(i); ids=[]
    while todo:
        a=todo.pop(); ids.append(a)
        for b in adj[a]-seen: seen.add(b); todo.append(b)
    comps.append(ids)
print('COMPONENTS',len(comps),Counter(map(len,comps)))
down=[]
for f in fs:
    if f['normal'][2]<-.1:
        pts=[v[i] for i in f['v']]
        lo=[min(p[k] for p in pts) for k in range(3)]
        hi=[max(p[k] for p in pts) for k in range(3)]
        down.append({**f,'lo':lo,'hi':hi})
(root/'down_faces.json').write_text(json.dumps(down))
print('DOWN',len(down))
owners={a:i for i,c in enumerate(comps) for a in c}
selected=[]; stats=[]
for ci,ids in enumerate(comps):
    lo=[min(v[i][k] for i in ids) for k in range(3)]; hi=[max(v[i][k] for i in ids) for k in range(3)]
    candidates=[f for f in down if owners[f['v'][0]]==ci and (f['lo'][2]+f['hi'][2])/2>(lo[2]+hi[2])/2 and max(f['hi'][k]-f['lo'][k] for k in (0,1))>.4]
    selected.extend(candidates)
    stats.append({'component':ci,'lo':lo,'hi':hi,'faces':[f['id'] for f in candidates]})
(root/'box_light_candidates.json').write_text(json.dumps({'selected':selected,'components':stats}))
print('CANDIDATES',len(selected),'FRAMES',sum(bool(s['faces']) for s in stats),'counts',Counter(len(s['faces']) for s in stats))
print('NO CANDIDATES', [s for s in stats if not s['faces']])
print('EXAMPLE MATCH', [f for f in selected if abs(f['lo'][0]+29.9283)<.001 and f['lo'][1]<-4.5 and f['hi'][1]>-12.5 and f['lo'][2]>21])

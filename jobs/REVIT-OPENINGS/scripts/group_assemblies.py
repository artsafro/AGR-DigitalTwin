import json, itertools, math
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np

root=Path(__file__).resolve().parents[1]; out=root/'outputs/source-v001'
rows=json.loads((out/'inventory.json').read_text(encoding='utf-8'))['objects']
entries=[]
for r in rows:
    n=r['name'].lower()
    if r['type']!='MESH' or not any(k in n for k in ['импост','системная панель','окновитраж','дверьвитраж']):continue
    p=np.array(r['bounds']);m=np.array(r['matrix']);p=p@m[:3,:3].T+m[:3,3]
    entries.append({'name':r['name'],'lo':p.min(axis=0),'hi':p.max(axis=0)})
parent=list(range(len(entries)))
def find(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
grid=defaultdict(list);pairs=0;gap=0.002
for i,e in enumerate(entries):
    lo=e['lo']-gap;hi=e['hi']+gap
    keys=list(itertools.product(*(range(math.floor(a/2),math.floor(b/2)+1) for a,b in zip(lo,hi))))
    candidates=set(j for key in keys for j in grid[key])
    for j in candidates:
        p=entries[j]
        if np.all(p['lo']<=hi) and np.all(p['hi']>=lo):
            parent[find(j)]=find(i);pairs+=1
    for k in keys:grid[k].append(i)
groups=defaultdict(list)
for i in range(len(entries)):groups[find(i)].append(i)
assemblies=[]
for ids in groups.values():
    lo=np.min([entries[i]['lo'] for i in ids],axis=0);hi=np.max([entries[i]['hi'] for i in ids],axis=0)
    names=[entries[i]['name'] for i in ids]
    assemblies.append({'members':names,'min':lo.tolist(),'max':hi.tolist(),'dimensions':(hi-lo).tolist(),
                       'panels':sum('Системная панель' in n for n in names),'mullions':sum('импост' in n.lower() for n in names),
                       'windows':sum('Окно' in n for n in names),'doors':sum('Дверь' in n for n in names)})
assemblies.sort(key=lambda a:(-len(a['members']),a['min']))
for i,a in enumerate(assemblies,1):a['id']=f'ASSEMBLY_{i:04d}'
(out/'assemblies-proximity.json').write_text(json.dumps({'method':'AABB contact 2mm; candidate assemblies, semantic boundaries not certified','assemblies':assemblies},ensure_ascii=False),encoding='utf-8')
print('entries',len(entries),'groups',len(assemblies),'contacts',pairs,'size_distribution',Counter(min(len(a['members']),100) for a in assemblies).most_common(15))
print(json.dumps([{k:v for k,v in a.items() if k!='members'}|{'count':len(a['members'])} for a in assemblies[:15]],ensure_ascii=False))

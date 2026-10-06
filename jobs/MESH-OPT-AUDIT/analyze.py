import json,collections, numpy as np
from pathlib import Path
p=Path('jobs/MESH-OPT-AUDIT/outputs');d=json.loads((p/'source-mesh.json').read_text());v=np.array(d['vertices']);parent=list(range(len(v)))
def root(a):
 while a!=parent[a]:parent[a]=parent[parent[a]];a=parent[a]
 return a
for a,b in d['edges']:parent[root(a)]=root(b)
groups=collections.defaultdict(list)
for i in range(len(v)):groups[root(i)].append(i)
fg=collections.defaultdict(list)
for i,f in enumerate(d['faces']):fg[root(f[0])].append(i)
rows=[]
for k,ids in groups.items():
 a=v[ids];fs=fg[k];rows.append({'id':min(ids),'vertices':len(ids),'faces':len(fs),'tris':sum(len(d['faces'][i])-2 for i in fs),'degrees':dict(collections.Counter(len(d['faces'][i]) for i in fs)),'bbox':np.ptp(a,axis=0).round(5).tolist(),'center':a.mean(axis=0).round(5).tolist(),'vertex_ids':ids,'face_ids':fs})
rows.sort(key=lambda x:-x['faces']);(p/'components.json').write_text(json.dumps(rows))
print('Components',len(rows),'face degrees',collections.Counter(map(len,d['faces'])),'tris',sum(len(f)-2 for f in d['faces']))
for r in rows[:35]:print({k:v for k,v in r.items() if k not in ['vertex_ids','face_ids']})

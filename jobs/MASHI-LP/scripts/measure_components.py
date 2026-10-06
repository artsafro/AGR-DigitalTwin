import json,numpy as np
from pathlib import Path
from collections import defaultdict,Counter
out=Path('jobs/MASHI-LP/outputs/master-v001');data=json.loads((out/'reference.json').read_text())
result=[]
for name in ['MultiMat_5','SM_MashiPoryvaevoj_34_004_Main.002']:
 o=next(o for o in data if o['name']==name);v=np.array(o['vertices']);parent=list(range(len(v)))
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def union(a,b):parent[root(a)]=root(b)
 lookup={};fs=[]
 for i,p in enumerate(v):
  key=tuple(np.round(p,4))
  if key in lookup:union(i,lookup[key])
  else:lookup[key]=i
 for i,f in enumerate(o['faces']):
  if name!='MultiMat_5' and o['materials'][i]!=0:continue
  for a in f:union(f[0],a)
  fs.append(i)
 groups=defaultdict(list)
 for i in fs:groups[root(o['faces'][i][0])].append(i)
 rows=[]
 for inds in groups.values():
  pts=v[list(set(i for fi in inds for i in o['faces'][fi]))]
  rows.append(dict(face_ids=inds,bounds=[pts.min(axis=0).tolist(),pts.max(axis=0).tolist()],size=(pts.max(axis=0)-pts.min(axis=0)).tolist()))
 result.append(dict(name=name,components=rows))
 print(name,len(rows),'sizes',Counter(tuple(round(x,2) for x in r['size']) for r in rows).most_common(15))
(out/'components.json').write_text(json.dumps(result))

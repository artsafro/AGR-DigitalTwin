import json,numpy as np
from pathlib import Path
from collections import defaultdict
d=json.loads(Path('jobs/MASHI-LP/outputs/master-v001/reference.json').read_text())
for name in ['MultiMat_5','SM_MashiPoryvaevoj_34_004_MainGlass.002']:
 o=next(o for o in d if o['name']==name);v=np.array(o['vertices']);groups=defaultdict(list)
 for i,f in enumerate(o['faces']):
  q=v[f];n=np.cross(q[1]-q[0],q[2]-q[0]);a=np.linalg.norm(n)/2
  if a<.001:continue
  n/=2*a
  if abs(n[2])>.99:groups[round(q[:,2].mean(),2)].append((a,q.mean(axis=0)))
 print(name)
 for z,vals in sorted(groups.items(),key=lambda kv:-sum(t[0] for t in kv[1]))[:15]:
  a=sum(t[0] for t in vals);print(z,round(a,3),np.average([t[1] for t in vals],axis=0,weights=[t[0] for t in vals]))

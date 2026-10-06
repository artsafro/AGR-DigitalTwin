import json
from pathlib import Path
from collections import Counter
import numpy as np
P=Path('jobs/GLB-NPM/outputs/source-live-v001/definitions')
D={int(f.stem):json.loads(f.read_text(encoding='utf-8'))['entities'] for f in P.glob('*.json')}
def flatten(d,m=None,mat=None):
    m=np.eye(4) if m is None else m
    for e in D[d]:
        if e['hidden'] or not e['layer_visible']:continue
        material=e.get('material') or mat
        if 'definition_id' in e:
            yield from flatten(e['definition_id'],m@np.array(e['transform_inches']).reshape(4,4,order='F'),material)
        elif e['type']=='Face':
            p=np.array(e['points_inches'])
            p=(np.c_[p,np.ones(len(p))]@m.T)[:,:3]*.0254
            yield e,p,material
if __name__=='__main__':
    for d in [77179,146223,146648,146365,143392]:
        fs=list(flatten(d));pts=np.concatenate([p for e,p,m in fs])
        print('DEF',d,'bounds',np.round([pts.min(0),pts.max(0)],6).tolist(),'materials',dict(Counter(m for e,p,m in fs)))
        largest=[]
        for e,p,m in fs:
            area=0
            for poly in e['polygons']:
                q=p[[abs(i)-1 for i in poly]]
                area+=sum(np.linalg.norm(np.cross(q[i]-q[0],q[i+1]-q[0]))/2 for i in range(1,len(q)-1))
            largest.append((area,e['entity_id'],m,np.round(p.min(0),5).tolist(),np.round(p.max(0),5).tolist(),len(e['loops_inches'])))
        print('largest',json.dumps(sorted(largest,reverse=True)[:14]))

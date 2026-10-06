import json,sys
from pathlib import Path
from collections import Counter
import numpy as np
from rebuild_core import volume,axes_for
root=Path(__file__).resolve().parents[1];out=root/'outputs/library-v001'
raw={t['id']:t for t in json.loads((root/'outputs/source-v001/types.json').read_text(encoding='utf-8'))}
rebuilt=json.loads((out/'rebuilt-core.json').read_text(encoding='utf-8'))
report=[]
for t in rebuilt:
    src=raw[t['id']];sv=np.array(src['vertices'])
    for p in t['parts']:
        fs=[src['faces'][fi] for fi in p['source_faces']]; ids=sorted(set(i for f in fs for i in f));cv=sv[ids];ax=axes_for(cv)
        y=volume(sv,fs,ax)
        x=volume(sv[:,[1,0,2]],fs,[ax[1],ax[0],ax[2]]).transpose(1,0,2)
        z=volume(sv[:,[0,2,1]],fs,[ax[0],ax[2],ax[1]]).transpose(0,2,1)
        edges=Counter(tuple(sorted((a,b))) for f in p['faces'] for a,b in zip(f,f[1:]+f[:1]))
        bv=np.array(p['vertices']);error=float(max(np.max(abs(bv.min(axis=0)-cv.min(axis=0))),np.max(abs(bv.max(axis=0)-cv.max(axis=0)))))
        bad={'id':t['id'],'component':p['component'],'ray_disagreement_cells':int(np.sum((x!=y)|(z!=y))),
             'boundary_edges':sum(c==1 for c in edges.values()),'nonmanifold_edges':sum(c>2 for c in edges.values()),
             'bbox_error_m':error,'faces':len(p['faces'])}
        report.append(bad)
(out/'reconstruction-check.json').write_text(json.dumps(report),encoding='utf-8')
bad=[r for r in report if r['ray_disagreement_cells'] or r['boundary_edges'] or r['nonmanifold_edges'] or r['bbox_error_m']>.00002]
print('parts',len(report),'issues',len(bad),'categories',Counter(r['id'].split('_')[0] for r in bad));print(json.dumps(bad[:10]))

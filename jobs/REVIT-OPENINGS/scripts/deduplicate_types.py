import json,hashlib,re
from pathlib import Path
from collections import Counter
import numpy as np
root=Path(__file__).resolve().parents[1];out=root/'outputs/source-v001'
raw=json.loads((out/'types-raw.json').read_text(encoding='utf-8'))
groups={}; mapping={}
for t in raw:
    v=np.round(np.array(t['vertices'])/1e-5).astype(np.int64)
    faces=sorted(tuple(sorted(tuple(v[i]) for i in f)) for f in t['faces'])
    # Keep semantic panel/mullion families separate even for identical geometry.
    base=re.sub(r'\s*\[\d+\](?:\.\d+)?$|[_ ]?[0-9a-f]{7}(?:\.\d+)?$','',t['source'])
    key=(t['category'],base,hashlib.sha256(repr(faces).encode()).hexdigest())
    if key not in groups:
        groups[key]=dict(t,raw_ids=[],instances=[],source_names=[],geometry_hash=key[2],family_hint=base)
    g=groups[key];g['raw_ids'].append(t['id']);g['instances'].extend(t['instances']);g['source_names'].append(t['source'])
types=sorted(groups.values(),key=lambda t:(t['category'],t['family_hint'],t['dimensions'],t['geometry_hash']))
counts=Counter()
for t in types:
    counts[t['category']]+=1;t['id']=f"{t['category']}_{counts[t['category']]:03d}"
    for n in t['instances']:mapping[n]=t['id']
(out/'types.json').write_text(json.dumps(types,ensure_ascii=False),encoding='utf-8')
(out/'instance-types.json').write_text(json.dumps(mapping,ensure_ascii=False),encoding='utf-8')
print(dict(counts))

import bpy, json, re, hashlib
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict

root = Path('C:/Users/artsafro/.AGR_Project/jobs/REVIT-OPENINGS')
out = root / 'outputs/source-v001'
bpy.ops.wm.open_mainfile(filepath=str(out/'source-snapshot.blend'))

def category(n):
    n=n.lower()
    if 'двер' in n or 'drs_дпу' in n: return 'DOOR'
    if 'окно' in n: return 'WINDOW'
    if 'импост' in n: return 'MULLION'
    if 'системная панель' in n: return 'PANEL'
    return None

groups={}
mapping=[]
for o in bpy.context.scene.objects:
    cat=category(o.name)
    if o.type!='MESH' or cat is None: continue
    key=(cat,o.data.name,tuple(round(s,7) for s in o.matrix_world.to_scale()))
    if key not in groups:
        coords=np.empty(len(o.data.vertices)*3,dtype=np.float64)
        o.data.vertices.foreach_get('co',coords)
        coords=coords.reshape(-1,3)*np.array(list(o.matrix_world.to_scale()))
        mn=coords.min(axis=0); mx=coords.max(axis=0)
        verts=coords-mn
        groups[key]={'category':cat,'source':o.name,'mesh':o.data.name,
                     'dimensions':(mx-mn).tolist(),'local_min':mn.tolist(),
                     'vertices':verts.tolist(),'faces':[list(p.vertices) for p in o.data.polygons],
                     'instances':[]}
    groups[key]['instances'].append(o.name)
    mapping.append({'name':o.name,'category':cat,'mesh':o.data.name,
                    'matrix':[list(r) for r in o.matrix_world]})
types=list(groups.values())
for cat in ['WINDOW','DOOR','PANEL','MULLION']:
    subset=sorted([t for t in types if t['category']==cat],key=lambda t:(t['source'],t['dimensions']))
    for i,t in enumerate(subset,1): t['id']=f'{cat}_{i:03d}'
(out/'types-raw.json').write_text(json.dumps(types,ensure_ascii=False),encoding='utf-8')
(out/'placements-raw.json').write_text(json.dumps(mapping,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'type_counts':dict(Counter(t['category'] for t in types)),
 'window_door_types':[{'id':t['id'],'name':t['source'],'dims':[round(v,4) for v in t['dimensions']],
                      'instances':len(t['instances']),'v':len(t['vertices']),'f':len(t['faces'])}
                     for t in types if t['category'] in ['WINDOW','DOOR']]},ensure_ascii=False))

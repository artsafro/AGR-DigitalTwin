"""Offline evidence from captured SketchUp definitions; no scene modifications."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'jobs/GLB-NPM/outputs/source-live-v001'

def main():
    defs = {int(p.stem): json.loads(p.read_text(encoding='utf-8'))['entities']
            for p in (SRC/'definitions').glob('*.json')}
    missing = sorted({e['definition_id'] for es in defs.values() for e in es
                      if 'definition_id' in e} - defs.keys())
    assert not missing, missing
    targets = {206978:'K1_A',206981:'K1_B',179766:'K2_A',179769:'K2_B'}
    entities = {e['entity_id']:e for es in defs.values() for e in es}
    reports = {}
    for eid,label in targets.items():
        root = entities[eid]
        faces = []
        def walk(did, matrix, inherited, visible, stack):
            assert did not in stack, 'Cyclic definition'
            for e in defs[did]:
                mat = e.get('material') or inherited
                vis = visible and not e['hidden'] and e['layer_visible']
                if 'definition_id' in e:
                    transform = np.array(e['transform_inches']).reshape(4,4,order='F')
                    walk(e['definition_id'],matrix@transform,mat,vis,stack+[did])
                elif e['type']=='Face' and vis:
                    pts = np.array(e['points_inches'])
                    pts = (np.c_[pts,np.ones(len(pts))]@matrix.T)[:,:3]*.0254
                    faces.append((e,pts,mat))
        # Compare in shared definition space, independent of tower placement.
        walk(root['definition_id'],np.eye(4),None,True,[])
        points = np.concatenate([f[1] for f in faces])
        lo,hi = points.min(axis=0),points.max(axis=0)
        signatures=[]
        for e,pts,mat in faces:
            for poly in e['polygons']:
                corners=sorted(tuple(v) for v in np.round((pts[[abs(i)-1 for i in poly]]-lo)*1e5).astype(int).tolist())
                signatures.append(corners)
        digest=hashlib.sha256(json.dumps(sorted(signatures)).encode()).hexdigest()
        reports[label]={'entity_id':eid,'definition_id':root['definition_id'],
            'visible_face_instances':len(faces),'mesh_polygons':len(signatures),
            'bounds_definition_m':[lo.tolist(),hi.tolist()], 'size_m':(hi-lo).tolist(),
            'materials':dict(Counter(mat or '<inherited from tower/default>' for _,_,mat in faces)),
            'normalized_geometry_sha256_at_0_01mm':digest}
    report={'definition_closure_complete':True,'definitions':len(defs),
            'unique_definition_faces':sum(e['type']=='Face' for es in defs.values() for e in es),
            'floors':reports,
            'shared_geometry_and_direct_uv':{'A':reports['K1_A']['definition_id']==reports['K2_A']['definition_id'],
                                            'B':reports['K1_B']['definition_id']==reports['K2_B']['definition_id']},
            'A_equals_B_geometry':reports['K1_A']['normalized_geometry_sha256_at_0_01mm']==reports['K1_B']['normalized_geometry_sha256_at_0_01mm'],
            'limits':['Inherited tower material may differ.','Definition equality is not topology QA.',
                      'Texture extraction status is recorded separately in capture-report.json.','Live snapshot is not atomic.']}
    (SRC/'floor-comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))

if __name__=='__main__':main()

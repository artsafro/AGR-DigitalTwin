import json,itertools,os
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
root=Path(__file__).resolve().parents[1]
out=root/('outputs/openings-v003' if os.environ.get('AGR_OPENINGS_V003')=='1' else 'outputs/simple-v002')
geometry=json.loads((out/'readback-geometry.json').read_text(encoding='utf-8'))
report=[]
for o in geometry:
    v=np.array(o['vertices']);faces=[]
    for f in o['faces']:
        p=v[f];lo=p.min(axis=0);hi=p.max(axis=0);axis=int(np.argmin(hi-lo));uv=[a for a in range(3) if a!=axis]
        faces.append((lo,hi,axis,Polygon(p[:,uv])))
    coplanar=[];crossings=[]
    for i,j in itertools.combinations(range(len(faces)),2):
        lo,hi,a,poly=faces[i];ll,hh,b,p=faces[j]
        if np.any(np.maximum(lo,ll)>np.minimum(hi,hh)+1e-8):continue
        if a==b:
            if abs(lo[a]-ll[a])<1e-8 and poly.intersection(p).area>1e-10:coplanar.append([i,j])
        else:
            c=3-a-b
            if min(hi[c],hh[c])-max(lo[c],ll[c])>1e-8 and lo[b]+1e-8<ll[b]<hi[b]-1e-8 and ll[a]+1e-8<lo[a]<hh[a]-1e-8:crossings.append([i,j])
    report.append({'name':o['name'],'coplanar_overlaps':len(coplanar),'interior_face_crossings':len(crossings),'issues':(coplanar+crossings)[:5]})
top=json.loads((out/'readback.json').read_text(encoding='utf-8'))
ok=all(r['degrees']=={'4':r['polygons']} and r['material_ids']==[1,2] and r['euler_characteristic']==1 and r['boundary_is_only_outer_perimeter'] and not any(r[k] for k in ['duplicate_vertices','duplicate_faces','zero_area_faces','nonmanifold_edges','loose_edges','zero_uv_faces']) for r in top)
ok=ok and all(not r['coplanar_overlaps'] and not r['interior_face_crossings'] for r in report)
result={'geometry_checks_passed':ok,'visual_acceptance':'pending','full_library_complete':False,'delivery_passed':False,'surface_checks':report}
(out/'QA.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));assert ok

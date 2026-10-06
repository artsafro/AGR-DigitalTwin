"""Inspect material IDs and actual face geometry on the copied live body."""
import json
from collections import Counter,defaultdict
from pathlib import Path
import bpy
from mathutils import Vector

root=Path(__file__).resolve().parents[1]
out=root/'outputs/body-v005'
bpy.ops.wm.open_mainfile(filepath=str(out/'live-autosave-snapshot.blend'))
body=bpy.data.objects['skolka']
mesh=body.data
rows=defaultdict(list)
for face in mesh.polygons:
    center=body.matrix_world@face.center
    normal=body.matrix_world.to_3x3()@face.normal
    rows[face.material_index].append({'index':face.index,'area':face.area,
        'center':[round(v,3) for v in center],
        'normal':[round(v,3) for v in normal],
        'vertices':[list(body.matrix_world@mesh.vertices[i].co) for i in face.vertices]})
report={}
for idx,faces in rows.items():
    areas=sorted(x['area'] for x in faces)
    q=lambda f:round(areas[int(f*(len(areas)-1))],4)
    normals=Counter(tuple(round(v,1) for v in x['normal']) for x in faces)
    big=sorted(faces,key=lambda x:x['area'],reverse=True)[:12]
    report[idx]={'name':mesh.materials[idx].name if idx<len(mesh.materials) and mesh.materials[idx] else None,
                 'count':len(faces),'area_quantiles_m2':[q(v) for v in [0,.1,.25,.5,.75,.9,1]],
                 'normals':normals.most_common(12),'largest':big}
(out/'body-face-statistics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:{a:v[a] for a in ('name','count','area_quantiles_m2','normals')}
                  for k,v in report.items()},ensure_ascii=False))

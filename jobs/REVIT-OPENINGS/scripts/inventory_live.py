import bpy
import json
import re
from pathlib import Path
from collections import Counter

root = Path('C:/Users/artsafro/.AGR_Project/jobs/REVIT-OPENINGS')
out = root / 'outputs/source-v001'
out.mkdir(parents=True, exist_ok=True)
rows = []
for o in bpy.context.scene.objects:
    row = {'name': o.name, 'type': o.type, 'parent': o.parent.name if o.parent else None,
           'data': o.data.name if o.data else None, 'dimensions': list(o.dimensions),
           'matrix': [list(r) for r in o.matrix_world],
           'properties': {k: str(o[k])[:2000] for k in o.keys()},
           'collections': [c.name for c in o.users_collection]}
    if o.type == 'MESH':
        row.update(vertices=len(o.data.vertices), polygons=len(o.data.polygons),
                   materials=[m.name if m else None for m in o.data.materials],
                   bounds=[list(p) for p in o.bound_box])
    rows.append(row)
report = {'file': bpy.data.filepath, 'version': bpy.app.version_string,
          'units': bpy.context.scene.unit_settings.system,
          'scale': bpy.context.scene.unit_settings.scale_length, 'objects': rows}
(out / 'inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
snapshot = out / 'source-snapshot.blend'
if not snapshot.exists():
    bpy.ops.wm.save_as_mainfile(filepath=str(snapshot), copy=True)
prefix = Counter(re.sub(r'[_ ]?[0-9a-f]{7}(?:\.\d+)?$', '', r['name']) for r in rows)
candidates = [r for r in rows if re.search(r'окн|двер|витраж|window|door|curtain|стекл|импост', r['name'], re.I)]
print(json.dumps({'objects': len(rows), 'candidate_names': len(candidates),
                  'meshes': len({r['data'] for r in rows if r['type']=='MESH'}),
                  'prefixes': prefix.most_common(65),
                  'candidate_sample': [{k:r.get(k) for k in ['name','parent','vertices','polygons','properties']} for r in candidates[:12]],
                  'inventory': str(out/'inventory.json'), 'snapshot': str(snapshot)}, ensure_ascii=False))

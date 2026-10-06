import bpy, json
from pathlib import Path
from mathutils import Vector
from collections import Counter
out = Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/audit-v001')
out.mkdir(parents=True, exist_ok=True)
rows = []
for o in bpy.context.scene.objects:
    box = [o.matrix_world @ Vector(c) for c in o.bound_box]
    row = dict(name=o.name, type=o.type, collections=[c.name for c in o.users_collection],
        parent=o.parent.name if o.parent else None,
        bounds=[[min(v[i] for v in box) for i in range(3)], [max(v[i] for v in box) for i in range(3)]],
        matrix=[list(r) for r in o.matrix_world], hidden=o.hide_get(), modifiers=[m.type for m in o.modifiers])
    if o.type == 'MESH':
        row.update(vertices=len(o.data.vertices), faces=len(o.data.polygons),
            face_sizes=dict(Counter(len(p.vertices) for p in o.data.polygons)),
            materials=[m.name if m else None for m in o.data.materials],uv=[u.name for u in o.data.uv_layers])
    rows.append(row)
report=dict(file=bpy.data.filepath, dirty=bpy.data.is_dirty, version=bpy.app.version_string,
    units=bpy.context.scene.unit_settings.system,scale_length=bpy.context.scene.unit_settings.scale_length,objects=rows)
(out/'inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='objects'}))
for r in rows:
    print(r['name'],r['type'],r.get('faces'),r['collections'], 'bounds', [[round(x,2) for x in b] for b in r['bounds']])

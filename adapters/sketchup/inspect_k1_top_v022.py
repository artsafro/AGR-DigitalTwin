"""Read-only inventory of the unfinished K1 top in saved v022."""
import bpy, json
from pathlib import Path

root = Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(root / 'GLB_K1_assembled_v022.blend'))
rows = []
for obj in bpy.data.objects:
    if obj.type != 'MESH' or not (obj.name.startswith('TOP_') or obj.name.startswith('K1_TOP')):
        continue
    mesh = obj.data
    points = [obj.matrix_world @ v.co for v in mesh.vertices]
    rows.append({
        'name': obj.name, 'faces': len(mesh.polygons), 'vertices': len(mesh.vertices),
        'bounds': [[min(p[i] for p in points), max(p[i] for p in points)] for i in range(3)] if points else [],
        'material': [m.name for m in mesh.materials],
        'source_definition': obj.get('source_definition'),
    })
(root / 'top-v022-inventory.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
from collections import Counter
print('TOP_INVENTORY=' + json.dumps({'objects': len(rows), 'window_objects': sum(r['name'].startswith('TOP_Window') for r in rows), 'ac_objects': sum(r['name'].startswith('TOP_AC') for r in rows), 'faces_by_prefix': dict(Counter(r['name'].split('_')[1] for r in rows for _ in range(r['faces']))), 'window_samples': [r for r in rows if r['name'].startswith('TOP_Window')][:4]}, ensure_ascii=False))

"""Blender: export measured floor reference only; never edit the source blend."""
import json
import sys
from pathlib import Path

import bpy

p = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
bpy.ops.wm.open_mainfile(filepath=str(p / 'OBR22_K02_typical_floor_v001.blend'))
items = []
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH' or not obj.visible_get():
        continue
    obj.data.calc_loop_triangles()
    items.append({
        'name': obj.name, 'group': obj.users_collection[0].name,
        'props': {k: obj[k] for k in obj.keys()},
        'vertices': [list(obj.matrix_world @ v.co) for v in obj.data.vertices],
        'faces': [list(f.vertices) for f in obj.data.polygons],
        'triangles': [list(t.vertices) for t in obj.data.loop_triangles],
    })
(p / 'contour-source.json').write_text(json.dumps({
    'source': 'OBR22_K02_typical_floor_v001.blend',
    'local_to_revit_internal_m': bpy.context.scene['local_to_revit_internal_m'],
    'items': items,
}, ensure_ascii=False), encoding='utf-8')
print('Extracted reference objects:', len(items))

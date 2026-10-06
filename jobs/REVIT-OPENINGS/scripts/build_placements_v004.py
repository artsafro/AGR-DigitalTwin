"""Overlay the simplified assets on a copy of the Revit FBX Blender scene."""
import json
from collections import Counter
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/placements-v004'
data = json.loads((OUT / 'placement-map.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=data['source_snapshot'])
scene = bpy.context.scene
originals = {obj.name: obj for obj in scene.objects}

type_ids = sorted({row['type_id'] for row in data['placements']})
def asset_id(name):
    return next((type_id for type_id in sorted(type_ids, key=len, reverse=True)
                 if name.startswith(type_id + '_')), None)

with bpy.data.libraries.load(data['asset_library'], link=False) as (source, target):
    target.objects = [name for name in source.objects
                      if asset_id(name) and not name.endswith('_LABEL')]
assets = {asset_id(obj.name): obj for obj in target.objects if obj and obj.type == 'MESH'}
assert set(assets) == set(type_ids), (sorted(assets), type_ids)

placed_collection = bpy.data.collections.new('SOSH1150_SIMPLE_OPENINGS_PLACED_v004')
scene.collection.children.link(placed_collection)
review_collection = bpy.data.collections.new('D04_OPAQUE_LEAVES_FACADE_STATUS_UNKNOWN')
placed_collection.children.link(review_collection)
source_hide = set()
placed = []
for row in data['placements']:
    asset = assets[row['type_id']]
    obj = asset.copy()
    obj.name = row['id']
    (review_collection if row['type_id'] == 'D04' else placed_collection).objects.link(obj)
    obj.matrix_world = Matrix(row['matrix_world'])
    obj['type_id'] = row['type_id']
    obj['source_type'] = row['source_type']
    obj['source_members_json'] = json.dumps(row['source_members'], ensure_ascii=False)
    obj['placement_status'] = row['scope']
    obj['geometry_source'] = data['asset_library']
    obj.color = (.18, .72, .88, 1) if row['type_id'] != 'D04' else (.95, .55, .18, 1)
    source_hide.update(row['source_members'])
    placed.append(obj)

missing = source_hide - originals.keys()
assert not missing, f'Missing source members: {list(missing)[:5]}'
for name in source_hide:
    obj = originals[name]
    obj.hide_set(True)
    obj.hide_render = True
    obj['simplified_replacement'] = 'v004'

scene['placed_openings_version'] = 'v004'
scene['placed_openings_count'] = len(placed)
scene['source_objects_hidden_as_replaced'] = len(source_hide)
scene['placement_map'] = str(OUT / 'placement-map.json')
scene['placement_status'] = 'APPROXIMATE; original FBX retained, visual acceptance pending'
note = bpy.data.texts.new('SOSH1150_PLACEMENTS_README_RU')
note.write('Отдельная копия FBX-сцены. 370 упрощённых экземпляров установлены по координатам исходных элементов.\n')
note.write('Замещённые исходные элементы скрыты, но остались в файле. Остальная исходная геометрия сохранена.\n')
note.write('30 вложенных в витражи дверей не дублируются отдельными объектами.\n')
note.write('D04: 97 глухих полотен по FBX, отдельная коллекция; принадлежность фасадам не подтверждена.\n')
note.write('Точки посадки приблизительные: середина глубины исходных деталей, без проверки откосов/зазоров.\n')
note.write('Карта экземпляров и исходных членов: placement-map.json.\n')

if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
for obj in placed:
    obj.select_set(False)
bpy.context.view_layer.objects.active = placed[0]

# A neutral overall view makes the replacement collection easy to inspect.
points = [obj.matrix_world @ Vector((x, 0, z))
          for obj in placed for x in (0, obj.dimensions.x) for z in (0, obj.dimensions.z)]
low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
center = (low + high) / 2
extent = high - low
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            space.shading.color_type = 'OBJECT'
            space.region_3d.view_location = center
            space.region_3d.view_distance = max(extent) * 1.5
            space.region_3d.view_rotation = Vector((.8, -.8, .55)).to_track_quat('Z', 'Y')

path = OUT / 'SOSH1150_FBX_Openings_Placed_v004.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
print(json.dumps({'blend': str(path), 'placed': len(placed),
                  'hidden_source_objects': len(source_hide),
                  'bounds_min': list(low), 'bounds_max': list(high),
                  'counts': dict(Counter(obj['type_id'] for obj in placed))}, ensure_ascii=False))

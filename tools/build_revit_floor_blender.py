"""Blender-only preparation of an already exported Revit floor (not reconstruction).

Usage: blender --background --factory-startup --python tools/build_revit_floor_blender.py -- OUTPUT_FOLDER
Reads source_import.blend and floor-selection.json. Source geometry remains in
source_import.blend; the derivative retains the inverse placement transform.
Classification is based on FBX names, not verified Revit category IDs.
"""
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

p = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
selection = json.loads((p / 'floor-selection.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(p / 'source_import.blend'))
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
meshes = [o for o in scene.objects if o.type == 'MESH']

def mcp_data(name):
    envelope = json.loads((p / name).read_text(encoding='utf-8'))
    result = json.loads(next(c['text'] for c in envelope['content'] if c['type']=='text'))
    if not result.get('ok'): raise ValueError(name)
    return result['data']

name_rows = json.loads((p/'fbx-name-map.json').read_text(encoding='utf-8'))
name_map = {}
for row in name_rows:
    key = row['blender_name']
    if key in name_map and name_map[key]['revit_id_candidates'] != row['revit_id_candidates']:
        raise ValueError('Ambiguous FBX identity: '+key)
    name_map[key] = row
wall_data = {str(x['id']):x for x in mcp_data('wall-semantics.json')['elements']}
wall_types = {x['id']:x for x in mcp_data('walltypes.json')['wallTypes']}
type_details = {x['data']['id']:x['data'] for x in mcp_data('type-details.json')['results'] if x['ok']}
material_data = {x['id']:x for x in mcp_data('materials.json')['materials']}
extras = {str(x['data']['id']):x['data'] for x in mcp_data('extras.json')['results'] if x['ok']}

def identity(o):
    row = name_map.get(o.name) or name_map.get(re.sub(r'\.\d{3}$','',o.name))
    return row

def wall(o):
    row = identity(o)
    ids = row['revit_id_candidates'] if row else []
    return wall_data.get(ids[-1]) if len(ids)==1 else None

def bounds(o):
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    return [[min(v[i] for v in pts) for i in range(3)],
            [max(v[i] for v in pts) for i in range(3)]]

def category(o):
    n = o.name.lower()
    r = identity(o)
    ids = r['revit_id_candidates'] if r else []
    extra = extras.get(ids[-1]) if len(ids)==1 else None
    if extra and extra['categoryEnum']=='OST_Ceilings': return '71_Потолки'
    w = wall(o)
    if w and w['fields'].get('Зависимость снизу') == selection['nextLevelId']:
        return '91_Срез_стен_соседнего_этажа'
    if n.startswith(('обозначение', 'mr_зона')):
        return '90_Обозначения_и_зоны'
    if n.startswith(('mr_', 'a_fur', 'стир.')):
        return '80_Мебель_из_источника'
    if n.startswith('перекрытие'):
        return '70_Верхние_плиты' if bounds(o)[0][2] > selection['levelElevationMeters'] + 2 else '01_Перекрытия'
    if 'лестниц' in n:
        return '05_Лестницы'
    if 'огражден' in n:
        return '06_Ограждения'
    if n.startswith(('102_окно','ac_подоконник','dc_')):
        return '03_Окна_и_детали'
    if n.startswith(('дверь','одиночные')):
        return '04_Двери'
    if n.startswith(('базовая','многослойный')):
        return '02_Стены'
    return '07_Прочие_элементы'

groups = {o.name: category(o) for o in meshes}
structural = [o for o in meshes if groups[o.name] == '02_Стены']
centers = np.array([[(b[0][i] + b[1][i]) / 2 for i in range(2)]
                    for b in map(bounds, structural)])
_, axes = np.linalg.eigh(np.cov(centers.T))
axis = axes[:, -1]
if axis[0] < 0: axis *= -1
angle = math.atan2(axis[1], axis[0])
origin = Vector((float(centers[:,0].mean()), float(centers[:,1].mean()), selection['levelElevationMeters']))
world_to_local = Matrix.Rotation(-angle, 4, 'Z') @ Matrix.Translation(-origin)

collections = {}
for name in sorted(set(groups.values())):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    collections[name] = c
    c.hide_render = name.startswith(('70_', '71_', '80_', '90_', '91_'))
    c.hide_viewport = c.hide_render

clay = bpy.data.materials.new('Нейтральный макет — не проектная отделка')
clay.diffuse_color = (0.76, 0.78, 0.80, 1)
before_faces = after_faces = 0
records = []
for o in meshes:
    source_name = o.name
    old_world = o.matrix_world.copy()
    old_bounds = bounds(o)
    o.data = o.data.copy()
    o.data.transform(world_to_local @ old_world)
    o.parent = None
    o.matrix_world = Matrix.Identity(4)
    for c in list(o.users_collection): c.objects.unlink(o)
    collections[groups[source_name]].objects.link(o)
    o['source_fbx_name'] = source_name
    row = identity(o)
    if row:
        o['source_fbx_full_name'] = row['name']
        o['revit_id_candidates'] = json.dumps(row['revit_id_candidates'])
        if len(row['revit_id_candidates']) == 1:
            o['revit_element_id'] = row['revit_id_candidates'][0]
    w = wall(o)
    if w:
        o['revit_element_id'] = str(w['id'])
        o['revit_type_id'] = str(w['typeId'])
        o['revit_type_name'] = w['name']
        o['revit_category'] = w['categoryEnum']
        o['revit_parameters_json'] = json.dumps(w['fields'],ensure_ascii=False)
        wt = wall_types.get(w['typeId'])
        if wt: o['wall_width_m'] = wt['widthFeet']*0.3048
        params = type_details.get(w['typeId'],{}).get('parameters',[])
        function = next((x for x in params if x['name']=='Функция'),None)
        if function: o['revit_wall_function'] = function.get('valueString') or str(function.get('value'))
        mid = w['fields'].get('Материал несущих конструкций')
        if mid in material_data:
            mat = material_data[mid]
            o['revit_structural_material_id'] = str(mid)
            o['revit_structural_material_name'] = mat['name']
            o['material_binding_status'] = 'Structural material parameter only; face/layer bindings pending'
    o['source_rvt_job'] = 'OBR22-K02'
    o['category_method'] = 'FBX name heuristic; review required'
    before_faces += len(o.data.polygons)
    # Conservative coplanar dissolve. No remeshing, hole filling, or shape inference.
    old_area = sum(poly.area for poly in o.data.polygons)
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.000001)
    bmesh.ops.dissolve_limit(bm, angle_limit=0.00001, use_dissolve_boundaries=False,
                           verts=list(bm.verts), edges=list(bm.edges), delimit={'NORMAL'})
    new_area = sum(f.calc_area() for f in bm.faces)
    cleanup_accepted = abs(new_area-old_area) <= max(0.000001, old_area*0.00001)
    if cleanup_accepted: bm.to_mesh(o.data)
    bm.free(); o.data.update()
    # Preserve exact pre-existing material slots if present; this FBX has none.
    if not o.data.materials: o.data.materials.append(clay)
    repaired = o.data.validate(verbose=False)
    o.data.update()
    after_faces += len(o.data.polygons)
    o.color = ((0.39, 0.47, 0.53, 1) if groups[source_name].startswith('03_') else
               (0.60, 0.63, 0.65, 1) if groups[source_name].startswith('01_') else
               (0.76, 0.78, 0.80, 1))
    records.append({'name':o.name, 'collection':groups[source_name], 'source_bounds_m':old_bounds,
                    'local_bounds_m':bounds(o), 'polygons':len(o.data.polygons),
                    'cleanup_accepted':cleanup_accepted, 'area_delta_m2':new_area-old_area,
                    'mesh_validation_repaired':repaired})

visible = [o for o in meshes if not collections[groups[o.name]].hide_render]
vb = [bounds(o) for o in visible]
lo = Vector([min(b[0][i] for b in vb) for i in range(3)])
hi = Vector([max(b[1][i] for b in vb) for i in range(3)])
center = (lo + hi)*0.5
span = hi-lo
scene['source_rvt_sha256'] = '4e6dff5ed6ba9b81c471ebd01e2e7f202d740d807d52c4b8aeb7c8c1ba7973d6'
scene['floor_level_id'] = selection['levelId']
scene['source_level_elevation_m'] = selection['levelElevationMeters']
scene['local_to_revit_internal_m'] = json.dumps([list(row) for row in world_to_local.inverted()])
scene['status'] = 'Source-derived editable floor; not a clean parametric master or NPM/VPM delivery'
scene['display'] = 'Neutral diagnostic colors; source finishes not recovered'
scene['hidden_collections'] = '70 overhead slabs; 71 ceilings; 80 furniture; 90 symbols/zones; 91 adjacent floor wall slices. All retained.'
registry = bpy.data.texts.new('Revit_material_registry.json')
registry.write(json.dumps(list(material_data.values()),ensure_ascii=False,indent=2))

setup = bpy.data.collections.new('00_Камеры'); scene.collection.children.link(setup)
def camera(name, target, direction, scale):
    data = bpy.data.cameras.new(name); data.type = 'ORTHO'; data.ortho_scale = scale
    data.clip_end = 2000
    obj = bpy.data.objects.new(name,data); setup.objects.link(obj)
    obj.location = target + Vector(direction).normalized()*150
    obj.rotation_euler = (target-obj.location).to_track_quat('-Z','Y').to_euler()
    return obj
overview = camera('Общий_вид',center,(0,-0.75,1.25),span.x*1.08)
top = camera('План_этажа',center,(0,0,1),span.x*1.08)
detail = camera('Фрагмент_средней_секции',center,(0,-0.65,1.4),max(span.y*1.7,span.x/2.65))
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = 2000; scene.render.resolution_y = 850
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
sh = scene.display.shading
sh.light = 'STUDIO'; sh.studiolight_rotate_z = 0.35; sh.color_type = 'OBJECT'
sh.show_shadows = True; sh.show_cavity = True; sh.cavity_type = 'BOTH'
sh.curvature_ridge_factor = 1.3; sh.curvature_valley_factor = 1.15
sh.show_object_outline = True; sh.background_type = 'WORLD'
if scene.world is None: scene.world = bpy.data.worlds.new('Studio')
scene.world.color = (0.16,0.16,0.16)
scene.camera = overview
for o in bpy.context.selected_objects: o.select_set(False)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_distance = float(span.x*0.75)
            area.spaces.active.region_3d.view_location = center
            area.spaces.active.region_3d.view_rotation = overview.rotation_euler.to_quaternion()
            area.spaces.active.clip_end = 2000
            area.spaces.active.shading.color_type = 'OBJECT'
            area.spaces.active.overlay.show_extras = False
notes = bpy.data.texts.new('READ_ME_Этаж.txt')
notes.write('Корпус 2, секции 7–9. Типовой этаж: уровень Этаж 2 (+4.500 м).\n'
            'Геометрия получена из копии RVT через Revit MCP и FBX.\n'
            'Единицы — метры. Исходное размещение восстанавливается матрицей в Scene.\n'
            'Коллекции 70/71/80/90/91 скрыты только для обзора; данные сохранены.\n'
            'Стены содержат исходный Revit ID, тип, ширину и доступный материал несущей части.\n'
            'Состав слоёв и назначения по граням ещё не перенесены.\n'
            'Цвета служебные. Материалы FBX не передались. Проверка художником необходима.\n')
out = p/'OBR22_K02_typical_floor_v001.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(out))
for cam, name, width, height in [(overview,'overview.png',2000,850),(top,'plan.png',2000,720),(detail,'detail.png',1600,1100)]:
    scene.camera=cam; scene.render.resolution_x=width; scene.render.resolution_y=height
    scene.render.filepath=str(p/name); bpy.ops.render.render(write_still=True)
report={'blender':bpy.app.version_string,'mesh_objects':len(meshes),'visible_objects':len(visible),
        'collections':dict(Counter(groups.values())),'polygons_before':before_faces,'polygons_after':after_faces,
        'visible_dimensions_m':list(span),'rotation_radians':angle,'revit_origin_m':list(origin),
        'local_to_revit_internal_m':[list(row) for row in world_to_local.inverted()],
        'records':records,'blend':str(out)}
(p/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('DONE',json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=True))

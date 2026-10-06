"""Blender builder/readback for the measured contour reconstruction prototype."""
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

p = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
grid = np.load(p / 'body-grid.npz')
owner = grid['owner']
occupied = owner > 0
axes = [grid[k] for k in 'xyz']
angle = float(grid['angle'])
build = json.loads((p / 'body-build.json').read_text(encoding='utf-8'))
packed_faces, source_indices = [], []
dimensions = np.array([len(a) for a in axes])
for axis in range(3):
    pad = [(0, 0)] * 3
    pad[axis] = (1, 1)
    padded = np.pad(owner, pad)
    left = [slice(None)] * 3
    right = [slice(None)] * 3
    left[axis] = slice(None, -1)
    right[axis] = slice(1, None)
    a, b = padded[tuple(left)], padded[tuple(right)]
    for sign in (-1, 1):
        select = ((a > 0) & (b == 0)) if sign == 1 else ((a == 0) & (b > 0))
        origins = np.stack(np.where(select), axis=1)
        offsets = np.zeros((4, 3), dtype=np.int64)
        u, v = (axis + 1) % 3, (axis + 2) % 3
        offsets[1, u] = 1
        offsets[2, u] = offsets[2, v] = 1
        offsets[3, v] = 1
        if sign == -1:
            offsets = offsets[::-1]
        corners = origins[:, None, :] + offsets[None, :, :]
        packed_faces.append((corners[:, :, 0]*dimensions[1]+corners[:, :, 1])*dimensions[2]+corners[:, :, 2])
        source_indices.append((a if sign == 1 else b)[select])
keys = np.concatenate(packed_faces)
unique, inverse = np.unique(keys.ravel(), return_inverse=True)
faces = inverse.reshape(-1, 4).astype(np.int32)
indices = np.stack([unique // (dimensions[1]*dimensions[2]),
                    unique // dimensions[2] % dimensions[1], unique % dimensions[2]], axis=1)
vertices = np.stack([axes[a][indices[:, a]] for a in range(3)], axis=1)
rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
vertices[:, :2] = vertices[:, :2] @ rotation.T
provenance = np.concatenate(source_indices).astype(np.int32)
np.savez_compressed(p / 'body-mesh.npz', vertices=vertices, faces=faces, source_indices=provenance)
compact = '--compact' in sys.argv
structured = '--structured' in sys.argv
optimized = '--optimized' in sys.argv
if compact or structured:
    packed = np.load(p / ('body-structured-mesh.npz' if structured else 'body-compact-mesh.npz'))
    vertices, faces, provenance = packed['vertices'], packed['faces'], packed['source_indices']
if optimized:
    packed = np.load(p / 'body-optimized-mesh.npz')
    vertices, faces, provenance = packed['vertices'], packed['faces'], packed['source_indices']
    optimization = json.loads((p / 'body-optimization.json').read_text(encoding='utf-8'))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'METERS'
collection = bpy.data.collections.new('01_BODY_по_контурам')
scene.collection.children.link(collection)
mesh = bpy.data.meshes.new('BODY_quad_contour_union')
mesh.from_pydata(vertices.tolist(), [], faces.tolist())
mesh.update()
obj = bpy.data.objects.new('BODY_Этаж_02', mesh)
collection.objects.link(obj)
obj.color = (0.72, 0.74, 0.76, 1)
attr = mesh.attributes.new('source_wall_index', 'INT', 'FACE')
wall_provenance = provenance
if optimized:
    mesh.attributes.new('source_group_index', 'INT', 'FACE').data.foreach_set('value', provenance)
    representatives = np.array([0]+[g[0] if len(g)==1 else 0 for g in optimization['source_groups']], dtype=np.int32)
    wall_provenance = representatives[provenance]
    bpy.data.texts.new('BODY_source_groups.json').write(json.dumps(optimization['source_groups']))
attr.data.foreach_set('value', wall_provenance)
ids = np.array([0]+[int(w['props']['revit_element_id']) for w in build['wall_records']], dtype=np.int32)
mesh.attributes.new('revit_element_id', 'INT', 'FACE').data.foreach_set('value', ids[wall_provenance])
obj['provenance'] = 'Face source_wall_index -> BODY_source_mapping.json; internal union faces removed'
if optimized:
    obj['provenance'] = 'source_group_index (1-based) -> BODY_source_groups.json -> wall records. source_wall_index/revit_element_id=0 for multi-source faces.'
obj['stage'] = 'BODY first. Windows must be modelled separately from source contours and seated in openings.'
scene['local_to_revit_internal_m'] = build['local_to_revit_internal_m']
scene['source_rvt_sha256'] = '4e6dff5ed6ba9b81c471ebd01e2e7f202d740d807d52c4b8aeb7c8c1ba7973d6'
scene['status'] = 'BODY contour prototype; see body-qa.json. Not a completed floor or NPM/VPM delivery.'
scene['source_reference_blend'] = str(p / 'OBR22_K02_typical_floor_v001.blend')
scene['material_status'] = 'Neutral diagnostic color. Source finishes not assigned.'
bpy.data.texts.new('BODY_source_mapping.json').write(json.dumps(build, ensure_ascii=False, indent=2))
bpy.data.texts.new('READ_ME.txt').write(
    'Бадик построен заново по измеренным контурам 556 стен и их проёмов.\n'
    'Исходная треугольная сетка не скопирована. Внутренние поверхности стыков удалены объединением объёмов.\n'
    'Окна, двери, плиты и оборудование остаются в отдельном исходном v001; это этап BODY.\n'
    'Рабочий прототип; заключение о соответствии только по body-qa.json.\n'
    'BODY начинается на отметке пола +4.500. Заглублённые части стен остаются в исходнике.\n')
lo, hi = vertices.min(axis=0), vertices.max(axis=0)
center = Vector((lo+hi)/2)
span = hi-lo
cams = bpy.data.collections.new('00_Камеры')
scene.collection.children.link(cams)
def camera(name, target, direction, scale):
    data = bpy.data.cameras.new(name)
    data.type = 'ORTHO'
    data.ortho_scale = scale
    data.clip_end = 1000
    cam = bpy.data.objects.new(name, data)
    cams.objects.link(cam)
    cam.location = target + Vector(direction).normalized()*150
    cam.rotation_euler = (target-cam.location).to_track_quat('-Z', 'Y').to_euler()
    return cam
overview = camera('BODY_Общий_вид', center, (0, -1.3, 1.8), float(span[0]*1.07))
detail = camera('BODY_Средняя_секция', center, (0, -1.1, 1.4), 30)
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
sh = scene.display.shading
sh.light = 'STUDIO'
sh.color_type = 'OBJECT'
sh.show_shadows = True
sh.show_cavity = True
sh.cavity_type = 'BOTH'
sh.show_object_outline = True
sh.background_type = 'WORLD'
scene.world = bpy.data.worlds.new('Studio')
scene.world.color = (0.14, 0.14, 0.14)
scene.camera = overview
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_distance = float(span[0]*.7)
            area.spaces.active.region_3d.view_location = center
            area.spaces.active.region_3d.view_rotation = overview.rotation_euler.to_quaternion()
            area.spaces.active.shading.color_type = 'OBJECT'
            area.spaces.active.overlay.show_extras = False
out = p / ('OBR22_K02_typical_floor_v003_BODY.blend' if compact else 'OBR22_K02_typical_floor_v002_BODY.blend')
if structured:
    out = p / 'OBR22_K02_typical_floor_v004_BODY.blend'
if optimized:
    out = p / 'OBR22_K02_typical_floor_v005_BODY.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(out))
for cam, name, w, h in [(overview, 'body-overview.png', 2000, 850), (detail, 'body-detail.png', 1600, 1100)]:
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.filepath = str(p / (('optimized-'+name) if optimized else name))
    bpy.ops.render.render(write_still=True)
print('BODY saved', len(vertices), len(faces), str(out))

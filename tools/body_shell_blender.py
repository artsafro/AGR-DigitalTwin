"""Save/reopen isolated shell output; run with Blender --background --factory-startup."""
import json
import sys
from pathlib import Path
import bpy

p = Path(sys.argv[sys.argv.index('--')+1]).resolve()
data = json.loads((p/'body-shell.json').read_text(encoding='utf-8'))
target = p/'BODY_SHELL.blend'
if target.exists():
    raise FileExistsError(target)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1.0
item = data['meshes'][0]
mesh = bpy.data.meshes.new(item['name'])
mesh.from_pydata(item['vertices'], [], item['faces'])
mesh.update()
repairs_before_save = mesh.validate(verbose=False, clean_customdata=False)
assert repairs_before_save is False
for polygon, material_index in zip(mesh.polygons, item['materials']):
    polygon.material_index = material_index
obj = bpy.data.objects.new(item['name'], mesh)
bpy.context.collection.objects.link(obj)
obj['shell_m'] = data['thickness_m']
obj['inner_faces'] = False
bpy.data.texts.new('PROVENANCE.json').write(json.dumps(data['face_sources'], ensure_ascii=False))
bpy.ops.wm.save_as_mainfile(filepath=str(target))
bpy.ops.wm.open_mainfile(filepath=str(target))
objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert len(objects) == 1
obj = objects[0]
repairs_after_reopen = obj.data.validate(verbose=False, clean_customdata=False)
assert repairs_after_reopen is False
actual = {'name': obj.name, 'vertices': [list(v.co) for v in obj.data.vertices],
          'faces': [list(f.vertices) for f in obj.data.polygons],
          'materials': [f.material_index for f in obj.data.polygons]}
assert actual['faces'] == item['faces']
assert actual['materials'] == item['materials']
error = max(abs(a-b) for v, w in zip(actual['vertices'], item['vertices']) for a, b in zip(v, w))
assert len(actual['vertices']) == len(item['vertices']) and error < 5e-6
assert all(len(f) == 4 for f in actual['faces'])
assert json.loads(bpy.data.texts['PROVENANCE.json'].as_string()) == data['face_sources']
assert abs(float(obj['shell_m']) - float(data['thickness_m'])) < 1e-12
assert bool(obj['inner_faces']) is False
(p/'blender-readback.json').write_text(json.dumps({**data, 'meshes': [actual]}, ensure_ascii=False), encoding='utf-8')
(p/'blender-evidence.json').write_text(json.dumps({'blender': bpy.app.version_string,
    'vertices': len(actual['vertices']), 'quads': len(actual['faces']), 'coordinate_error_m': error,
    'provenance_preserved': True, 'materials_preserved': True,
    'properties_preserved': True, 'mesh_validate_repairs': 0}), encoding='utf-8')
print('SHELL_READBACK_OK', len(actual['faces']), error)

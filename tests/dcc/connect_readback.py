"""Synthetic Connect save/reopen check; run in an isolated background Blender."""
import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from dt_ai.geometry.connect import connect_quads

out = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
out.mkdir(parents=True, exist_ok=False)
v, f, parents = connect_quads(
    [[0, 0, 0], [8, 0, 0], [6, 1, 0], [0, 1, 0], [8, 2, 0], [0, 2, 0]],
    [[0, 1, 2, 3], [3, 2, 4, 5]], max_side_m=3)
ids = [4 if p == 0 else 0 for p in parents]
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new('SYNTHETIC_CONNECT')
mesh.from_pydata(v.tolist(), [], f.tolist())
mesh.update()
assert not mesh.validate(), 'Blender repaired generated mesh'
for name, values in [('parent_face', parents), ('finish_id', ids)]:
    attr = mesh.attributes.new(name=name, type='INT', domain='FACE')
    for cell, value in zip(attr.data, values):
        cell.value = value
obj = bpy.data.objects.new('SYNTHETIC_CONNECT', mesh)
bpy.context.collection.objects.link(obj)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1
path = out / 'synthetic-connect.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path))
mesh = bpy.data.objects['SYNTHETIC_CONNECT'].data
np.testing.assert_allclose([list(p.co) for p in mesh.vertices], v, atol=1e-6)
np.testing.assert_array_equal([list(p.vertices) for p in mesh.polygons], f)
for name, values in [('parent_face', parents), ('finish_id', ids)]:
    assert [cell.value for cell in mesh.attributes[name].data] == values
assert all(len(p.vertices) == 4 and p.area > 0 and p.normal.z > 0 for p in mesh.polygons)
assert not mesh.validate(), 'Saved mesh required repair'
report = dict(synthetic=True, scope='Connect fixture save/reopen only',
              blender=bpy.app.version_string, vertices=len(v), faces=len(f),
              coordinates_quads_parents_finish_ids_preserved=True,
              synthetic_readback_passed=True, delivery_passed=False)
(out / 'readback.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))

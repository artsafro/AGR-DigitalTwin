"""Replace disconnected imported frame profiles with simple quad boxes."""
import bpy
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'outputs'
SOURCE = OUT / 'frame_source_snapshot_v001.blend'
RESULT = OUT / 'window_frames_quad_v002.blend'
REPORT = OUT / 'window_frames_quad_v002_qa.json'

assert Path(bpy.data.filepath).resolve() == SOURCE.resolve(), bpy.data.filepath
assert not RESULT.exists(), RESULT
source = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
mesh = source.data
parent = list(range(len(mesh.vertices)))

def root(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i

for edge in mesh.edges:
    a, b = edge.vertices
    parent[root(a)] = root(b)

groups = defaultdict(list)
for poly in mesh.polygons:
    groups[root(poly.vertices[0])].append(poly)

records = []
for polys in groups.values():
    ids = {v for p in polys for v in p.vertices}
    coords = [source.matrix_world @ mesh.vertices[v].co for v in ids]
    lo = [min(v[i] for v in coords) for i in range(3)]
    hi = [max(v[i] for v in coords) for i in range(3)]
    records.append((lo, hi, len(polys)))
records.sort(key=lambda r: tuple(round(v, 6) for v in r[0] + r[1]))

# Merge co-linear bars that have the same cross-section and touch or overlap.
# This removes source duplicates and internal end caps without changing the
# occupied volume or the visible outside proportions.
def merge_collinear(items, axis):
    other = [i for i in range(3) if i != axis]
    groups = defaultdict(list)
    for lo, hi, source_faces in items:
        key = tuple(round(v, 4) for i in other for v in (lo[i], hi[i]))
        groups[key].append((lo, hi, source_faces))
    merged = []
    for group in groups.values():
        group.sort(key=lambda row: row[0][axis])
        for lo, hi, source_faces in group:
            if merged and merged[-1][3] == id(group) and lo[axis] <= merged[-1][1][axis] + 1e-5:
                prev_lo, prev_hi, prev_faces, marker = merged[-1]
                prev_hi[axis] = max(prev_hi[axis], hi[axis])
                merged[-1] = (prev_lo, prev_hi, prev_faces + source_faces, marker)
            else:
                merged.append((lo[:], hi[:], source_faces, id(group)))
    return [(lo, hi, count) for lo, hi, count, _ in merged]

valid = []
skipped = []
for component_id, (lo, hi, source_faces) in enumerate(records, 1):
    if min(hi[i]-lo[i] for i in range(3)) < 0.0001:
        skipped.append({'component': component_id, 'source_faces': source_faces,
                        'min': lo, 'max': hi, 'reason': 'zero-volume source'})
    else:
        valid.append((lo, hi, source_faces))
for axis in (0, 1, 2, 0, 1, 2):
    valid = merge_collinear(valid, axis)
valid.sort(key=lambda r: tuple(round(v, 6) for v in r[0] + r[1]))

verts, faces = [], []
for component_id, (lo, hi, source_faces) in enumerate(valid, 1):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    base = len(verts)
    verts.extend(((x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
                  (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)))
    faces.extend(tuple(base+i for i in f) for f in (
        (3,2,1,0),(4,5,6,7),(0,1,5,4),
        (1,2,6,5),(2,3,7,6),(3,0,4,7)))

output_mesh = bpy.data.meshes.new('WindowFrames_Quad_Mesh_v002')
output_mesh.from_pydata(verts, [], faces)
output_mesh.update()
if mesh.materials:
    output_mesh.materials.append(mesh.materials[5] if len(mesh.materials) > 5 else mesh.materials[0])
output = bpy.data.objects.new('WindowFrames_Quad_v002', output_mesh)
collection = bpy.data.collections.new('WINDOW_FRAMES_QUAD_v002')
bpy.context.scene.collection.children.link(collection)
collection.objects.link(output)
output['source_object'] = source.name
output['source_snapshot'] = SOURCE.name
output['modeled_components'] = len(verts)//8
output['skipped_zero_volume'] = len(skipped)

source_collection = bpy.data.collections.new('SOURCE_IMPORTED_HIDDEN')
bpy.context.scene.collection.children.link(source_collection)
source_collection.objects.link(source)
for old in list(source.users_collection):
    if old != source_collection:
        old.objects.unlink(source)
source.hide_set(True)
source.hide_render = True

for o in bpy.context.selected_objects:
    o.select_set(False)
output.select_set(True)
bpy.context.view_layer.objects.active = output

report = {
    'source': str(SOURCE), 'result': str(RESULT),
    'source_object': source.name,
    'source_components': len(records),
    'modeled_components': len(verts)//8,
    'merged_volume_components': len(records)-len(skipped)-len(valid),
    'skipped': skipped,
    'source_vertices': len(mesh.vertices),
    'source_faces': len(mesh.polygons),
    'result_vertices': len(verts),
    'result_faces': len(faces),
    'result_face_degrees': dict(Counter(len(f) for f in faces)),
    'global_bounds': [[min(v[i] for v in verts) for i in range(3)],
                      [max(v[i] for v in verts) for i in range(3)]],
    'delivery_passed': False,
    'limits': ['Full AGR Checker and visual acceptance have not been performed.',
               'Three zero-volume source fragments were excluded.'],
}
OUT.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(RESULT))
print(json.dumps({k:report[k] for k in ('source_components','modeled_components','result_faces','result_face_degrees','skipped')}, ensure_ascii=False))

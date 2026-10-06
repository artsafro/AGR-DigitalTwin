"""Read-only ray probe for window-plane contacts on K1 top."""
import bpy, json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

root = Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(root / 'GLB_K1_assembled_v022.blend'))
surfaces = []
for obj in bpy.data.objects:
    if obj.type != 'MESH' or not obj.name.startswith('TOP_') or obj.name.startswith(('TOP_Window', 'TOP_AC')):
        continue
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    faces = [list(p.vertices) for p in obj.data.polygons]
    if faces:
        surfaces.append((obj.name, BVHTree.FromPolygons(verts, faces, all_triangles=False)))
rows = []
for obj in bpy.data.objects:
    if not obj.name.startswith('TOP_Window'):
        continue
    p = obj.data.polygons[0]
    normal = (obj.matrix_world.to_3x3() @ p.normal).normalized()
    center = obj.matrix_world @ p.center
    row = {'name': obj.name, 'source_definition': obj.get('source_definition'), 'center': list(center), 'normal': list(normal), 'hits': []}
    if obj.get('source_definition') != 14155:
        center.z = 67.5
    for sign in (-1, 1):
        direction = normal * sign
        hits = []
        for name, bvh in surfaces:
            hit, n, face, d = bvh.ray_cast(center - direction * .5, direction, 1.0)
            if hit is not None:
                hits.append((round(float(d - .5), 5), name, face, round(float(n.dot(normal)), 4)))
        row['hits'].append(sorted(hits, key=lambda x: abs(x[0]))[:8])
    rows.append(row)
(root / 'top-window-rays-v022.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
print('RAY_SUMMARY=' + json.dumps(rows[:4]))

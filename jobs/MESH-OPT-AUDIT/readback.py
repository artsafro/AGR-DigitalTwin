"""Read a saved Blender scene in a separate Blender process."""
import bpy
import collections
import json
import math
import sys

obj = bpy.data.objects.get('Object013')
assert obj and obj.type == 'MESH'
mesh = obj.data
parent = list(range(len(mesh.vertices)))

def root(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x

for e in mesh.edges:
    a, b = e.vertices
    parent[root(a)] = root(b)
components = collections.Counter(root(v.index) for v in mesh.vertices)
edge_use = collections.Counter(tuple(sorted((p.vertices[i], p.vertices[(i+1) % len(p.vertices)])))
                               for p in mesh.polygons for i in range(len(p.vertices)))
uv = mesh.uv_layers.get('Atlas_UV')
result = {
    'file': bpy.data.filepath,
    'vertices': len(mesh.vertices),
    'faces': len(mesh.polygons),
    'components': len(components),
    'face_degrees': dict(collections.Counter(str(len(p.vertices)) for p in mesh.polygons)),
    'nonmanifold_edges_over_2': sum(n > 2 for n in edge_use.values()),
    'duplicate_index_faces': len(mesh.polygons)-len({tuple(sorted(p.vertices)) for p in mesh.polygons}),
    'uv_layer': uv.name if uv else None,
    'uv_finite': bool(uv and all(math.isfinite(c) for loop in uv.data for c in loop.uv)),
    'material_slots': len(obj.material_slots),
    'material_index_counts': dict(collections.Counter(str(p.material_index) for p in mesh.polygons)),
}
assert result['vertices'] == 4482 and result['faces'] == 3677 and result['components'] == 138
assert result['nonmanifold_edges_over_2'] == 0 and result['duplicate_index_faces'] == 0
assert result['uv_finite']
print('READBACK_JSON=' + json.dumps(result))

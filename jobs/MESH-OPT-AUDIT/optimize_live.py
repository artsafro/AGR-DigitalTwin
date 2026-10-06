"""Optimize the exact audited live Object013; run through live_call.py."""
import bpy
import bmesh
import collections
import json
import math
from pathlib import Path
from mathutils import Vector

base = Path('C:/Users/artsafro/.AGR_Project/jobs/MESH-OPT-AUDIT/outputs')
source = json.loads((base / 'source-mesh.json').read_text(encoding='utf8'))
components = json.loads((base / 'components.json').read_text(encoding='utf8'))
obj = bpy.context.object
assert obj and obj.name == 'Object013' and obj.type == 'MESH'
assert [list(obj.matrix_world @ v.co) for v in obj.data.vertices] == source['vertices']
assert [list(p.vertices) for p in obj.data.polygons] == source['faces']
assert (base / 'Object013_source.blend').exists()

mesh = obj.data.copy()
bm = bmesh.new()
bm.from_mesh(mesh)
bm.verts.ensure_lookup_table()
old_verts = list(bm.verts)
posts = [c for c in components if (c['vertices'], c['faces']) == (24, 13)]
rotors = [c for c in components if (c['vertices'], c['faces']) in ((72, 61), (48, 37))]
assert len(posts) == 53 and len(rotors) == 45

odd = set()
edge_groups = []
for comp in rotors:
    verts = [old_verts[i] for i in comp['vertex_ids']]
    center = sum((v.co for v in verts), Vector()) / len(verts)
    parent = {v: v for v in verts}

    def root(v):
        while parent[v] != v:
            v = parent[v]
        return v

    comp_verts = set(verts)
    for v in verts:
        for edge in v.link_edges:
            a, b = edge.verts
            if a not in comp_verts or b not in comp_verts:
                continue
            ra = (a.co.xy - center.xy).length
            rb = (b.co.xy - center.xy).length
            if abs(a.co.z - b.co.z) < 0.001 and abs(ra - rb) < 0.005:
                parent[root(a)] = root(b)
    rings = collections.defaultdict(list)
    for v in verts:
        rings[root(v)].append(v)
    assert len(rings) == comp['vertices'] // 12
    assert all(len(ring) == 12 for ring in rings.values())
    selected = set()
    for ring in rings.values():
        order = sorted(ring, key=lambda v: math.atan2(v.co.y - center.y, v.co.x - center.x))
        selected.update(order[1::2])
    candidate = {e for v in verts for e in v.link_edges if all(w in selected for w in e.verts)}
    assert len(candidate) == (len(rings) - 1) * 6, (comp['id'], len(candidate))
    odd.update(selected)
    edge_groups.extend(candidate)

assert len(edge_groups) == 1110 and len(odd) == 1380
bmesh.ops.dissolve_edges(bm, edges=edge_groups, use_verts=False, use_face_split=False)
remaining = [v for v in odd if v.is_valid and len(v.link_edges) == 2]
assert len(remaining) == 1380
bmesh.ops.dissolve_verts(bm, verts=remaining, use_face_split=False, use_boundary_tear=False)
post_verts = [old_verts[i] for comp in posts for i in comp['vertex_ids']]
assert len(post_verts) == 1272 and all(v.is_valid for v in post_verts)
bmesh.ops.delete(bm, geom=post_verts, context='VERTS')
assert len(bm.verts) == 4482 and len(bm.faces) == 3677
assert all(len(face.verts) >= 3 for face in bm.faces)
assert all(len(edge.link_faces) <= 2 for edge in bm.edges)
bm.to_mesh(mesh)
bm.free()
mesh.update()
assert not mesh.validate(clean_customdata=False)
assert len(mesh.vertices) == 4482 and len(mesh.polygons) == 3677
assert [layer.name for layer in mesh.uv_layers] == source['uv_layers']

obj.data = mesh
out = base / 'Object013_optimized_v001.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(out))
report = {
    'source': str(base / 'Object013_source.blend'),
    'optimized': str(out),
    'deleted_posts': len(posts),
    'rotors_12_to_6': len(rotors),
    'vertices_before': len(source['vertices']),
    'vertices_after': len(mesh.vertices),
    'faces_before': len(source['faces']),
    'faces_after': len(mesh.polygons),
    'face_degrees_after': dict(collections.Counter(str(len(p.vertices)) for p in mesh.polygons)),
    'uv_layers': [layer.name for layer in mesh.uv_layers],
    'file_bytes': out.stat().st_size,
}
(base / 'optimization_v001.json').write_text(json.dumps(report, indent=2), encoding='utf8')
print(json.dumps(report))

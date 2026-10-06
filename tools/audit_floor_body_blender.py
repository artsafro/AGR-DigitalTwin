"""Read the saved BODY file independently; reject contacts and missing surfaces."""
import hashlib
import json
import sys
from pathlib import Path

import bpy
import bmesh
import numpy as np

p = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
compact = '--compact' in sys.argv
structured = '--structured' in sys.argv
optimized = '--optimized' in sys.argv
blend = p / ('OBR22_K02_typical_floor_v003_BODY.blend' if compact else 'OBR22_K02_typical_floor_v002_BODY.blend')
if structured:
    blend = p / 'OBR22_K02_typical_floor_v004_BODY.blend'
if optimized:
    blend = p / 'OBR22_K02_typical_floor_v005_BODY.blend'
digest = hashlib.sha256(blend.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(blend))
objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert len(objects) == 1
mesh = objects[0].data
bm = bmesh.new()
bm.from_mesh(mesh)
nonmanifold_vertices = sum(not v.is_manifold for v in bm.verts)
wire_edges = sum(e.is_wire for e in bm.edges)
loose_vertices = sum(not v.link_edges for v in bm.verts)
bm.free()
v = np.empty(len(mesh.vertices)*3, dtype=np.float64)
mesh.vertices.foreach_get('co', v)
v = v.reshape(-1, 3)
degrees = np.empty(len(mesh.polygons), dtype=np.int32)
mesh.polygons.foreach_get('loop_total', degrees)
assert (degrees == 4).all()
f = np.empty(len(mesh.loops), dtype=np.int32)
mesh.loops.foreach_get('vertex_index', f)
f = f.reshape(-1, 4)
source = np.load(p / ('body-compact-mesh.npz' if compact else 'body-mesh.npz'))
if structured:
    source = np.load(p / 'body-structured-mesh.npz')
if optimized:
    source = np.load(p / 'body-optimized-mesh.npz')
readback_error = float(np.linalg.norm(v-source['vertices'], axis=1).max())
face_readback = bool(np.array_equal(f, source['faces']))
provenance = np.empty(len(f), dtype=np.int32)
mesh.attributes['source_group_index' if optimized else 'source_wall_index'].data.foreach_get('value', provenance)
source_readback = bool(np.array_equal(provenance, source['source_indices']))
if optimized:
    groups = json.loads(bpy.data.texts['BODY_source_groups.json'].as_string())
    expected_groups = json.loads((p/'body-optimization.json').read_text(encoding='utf-8'))['source_groups']
    source_readback = source_readback and groups == expected_groups
    ids = np.empty(len(f), dtype=np.int32)
    mesh.attributes['revit_element_id'].data.foreach_get('value', ids)
    records = json.loads(bpy.data.texts['BODY_source_mapping.json'].as_string())['wall_records']
    expected_ids = [int(records[g[0]-1]['props']['revit_element_id']) if len(g)==1 else 0 for g in groups]
    source_readback = source_readback and np.array_equal(ids, np.array([0]+expected_ids)[provenance])
np.savez_compressed(p/'body-readback.npz', vertices=v, faces=f, source_indices=provenance)
edges = np.stack([f, np.roll(f, -1, axis=1)], axis=2).reshape(-1, 2)
sorted_edges = np.sort(edges, axis=1)
unique_edges, counts = np.unique(sorted_edges, axis=0, return_counts=True)
edge_length = np.linalg.norm(v[unique_edges[:, 1]] - v[unique_edges[:, 0]], axis=1)
duplicates_v = len(v)-len(np.unique(v, axis=0))
duplicates_f = len(f)-len(np.unique(np.sort(f, axis=1), axis=0))
q = v[f]
e1, e2 = q[:, 1]-q[:, 0], q[:, 3]-q[:, 0]
cross = np.cross(e1, e2)
area = np.linalg.norm(cross, axis=1)
orthogonality = np.abs(np.einsum('ij,ij->i', e1, e2)) / np.maximum(np.linalg.norm(e1, axis=1)*np.linalg.norm(e2, axis=1), 1e-30)
aspect = np.maximum(np.linalg.norm(e1, axis=1), np.linalg.norm(e2, axis=1))/np.maximum(np.minimum(np.linalg.norm(e1, axis=1), np.linalg.norm(e2, axis=1)), 1e-30)
bad = unique_edges[counts != 2]
build = json.loads((p/'body-build.json').read_text(encoding='utf-8'))
result = {
    'blend': str(blend), 'blend_sha256': digest, 'scope': 'BODY only; no windows/slabs/doors',
    'vertices': len(v), 'faces': len(f), 'quads': int((degrees == 4).sum()),
    'exact_duplicate_vertices': duplicates_v, 'exact_duplicate_faces': duplicates_f,
    'boundary_edges': int((counts == 1).sum()), 'nonmanifold_edges': int((counts > 2).sum()),
    'nonmanifold_vertices': nonmanifold_vertices, 'wire_edges': wire_edges, 'loose_vertices': loose_vertices,
    'zero_area_faces': int((area < 1e-12).sum()), 'minimum_edge_m': float(edge_length.min()),
    'maximum_aspect_ratio': float(aspect.max()), 'faces_aspect_over_100': int((aspect > 100).sum()),
    'maximum_rectangular_cosine_error': float(orthogonality.max()),
    'readback_max_error_m': readback_error, 'face_connectivity_readback': face_readback,
    'face_source_mapping_readback': source_readback,
    'nonmanifold_edge_examples_m': v[bad[:50]].tolist(),
    'source_vertex_alignment_max_m': build['source_snap_max_m'],
    'overlap_check': 'Pending independent grid-boundary verification; exact duplicate checks alone are insufficient',
    'status': 'prototype', 'passed': False,
    'remaining': ['Independent source contour/opening and union-boundary verification',
                  'Inspect high aspect ratio grid strips and reduce unnecessary subdivision',
                  'Model windows separately and measure their recess from the source'],
}
assert digest == hashlib.sha256(blend.read_bytes()).hexdigest()
(p/'body-qa.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: value for k, value in result.items() if k != 'nonmanifold_edge_examples_m'}))

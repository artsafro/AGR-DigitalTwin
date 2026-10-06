"""Read-only topology inventory shared by DCC jobs; never certifies delivery."""
from collections import Counter
import math


def inspect_mesh(vertices, faces, edges=None, material_ids=None, decimals=8):
    count = len(vertices)
    if any(len(v) != 3 or not all(math.isfinite(c) for c in v) for v in vertices):
        raise ValueError('Vertices must be finite XYZ triples')
    if any(len(f) < 3 or any(i < 0 or i >= count for i in f) for f in faces):
        raise ValueError('Invalid face indices')
    incidence = Counter(); used = set(); canonical = Counter(); material_edges = {}
    parent = list(range(count))

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def connect(a, b):
        parent[root(a)] = root(b)

    material_ids = [0]*len(faces) if material_ids is None else material_ids
    if len(material_ids) != len(faces):
        raise ValueError('Material IDs must match face count')
    zero_area = 0
    for face, material in zip(faces, material_ids):
        face = list(face); used.update(face); canonical[tuple(sorted(face))] += 1
        area = 0.0; origin = vertices[face[0]]
        for i in range(1, len(face)-1):
            a = [vertices[face[i]][k]-origin[k] for k in range(3)]
            b = [vertices[face[i+1]][k]-origin[k] for k in range(3)]
            cross = [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
            area += math.sqrt(sum(c*c for c in cross))/2
        zero_area += area < 1e-12
        for a,b in zip(face, face[1:]+face[:1]):
            edge = tuple(sorted((a,b))); incidence[edge] += 1
            material_edges.setdefault(edge,set()).add(material); connect(a,b)
    all_edges = set(incidence)
    for a,b in edges or []:
        if a<0 or b<0 or a>=count or b>=count:
            raise ValueError('Invalid edge indices')
        all_edges.add(tuple(sorted((a,b)))); connect(a,b)
    rounded = [tuple(round(c,decimals) for c in v) for v in vertices]
    extent = [max(v[k] for v in vertices)-min(v[k] for v in vertices) for k in range(3)] if vertices else [0]*3
    return {'vertices':count,'faces':len(faces),'polygon_sizes':dict(Counter(map(len,faces))),
      'triangles':sum(len(f)-2 for f in faces),'connected_components':len({root(i) for i in range(count)}),
      'duplicate_vertices_rounded':count-len(set(rounded)),'duplicate_vertex_decimals':decimals,
      'duplicate_faces_by_vertex_set':sum(n-1 for n in canonical.values()),'zero_area_faces_fan':zero_area,
      'boundary_edges':sum(n==1 for n in incidence.values()),'multi_face_edges':sum(n>2 for n in incidence.values()),
      'loose_edges':len(all_edges-set(incidence)),'vertices_unused_by_faces':count-len(used),
      'material_face_counts':dict(Counter(material_ids)),
      'material_interface_edges':sum(len(ids)>1 for ids in material_edges.values()),'extent_m':extent,
      'intersection_test_performed':False,'delivery_passed':False}

"""Contour-patch quadrangulation, preserving boundary nodes and source labels.

Reduce the Cartesian construction grid to maximal labelled rectangular patches.
Insert neighbour boundary nodes before quadrangulating, so patches share edges.
Regular four-corner patches become four rectangles. Junction patches use CDT
and a midpoint/centroid quad subdivision with no source FBX edges copied.
"""
import argparse
import bisect
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon


def rectangles(mask):
    remaining = mask.copy()
    for i in range(mask.shape[0]):
        j = 0
        while j < mask.shape[1]:
            value = remaining[i, j]
            if not value:
                j += 1
                continue
            j1 = j+1
            while j1 < mask.shape[1] and remaining[i, j1] == value:
                j1 += 1
            i1 = i+1
            while i1 < mask.shape[0] and (remaining[i1, j:j1] == value).all():
                i1 += 1
            remaining[i:i1, j:j1] = 0
            yield i, i1, j, j1, int(value)
            j = j1


def structured_mesh(patches, lines, axes):
    """Propagate measured edge nodes across rectangular patches to avoid fans.

    Each propagation inserts the matching node on the opposite edge. Repeat to
    closure, including neighbouring perpendicular faces, before emitting quads.
    This keeps a rectilinear surface with shared edges instead of CDT junctions.
    """
    lines = {key: set(value) for key, value in lines.items()}
    def edge_nodes(q, r):
        a = next(k for k in range(3) if q[k] != r[k])
        low, high = sorted([q[a], r[a]])
        key = (a, q[(a+1) % 3], q[(a+2) % 3])
        return key, {n for n in lines[key] if low <= n <= high}
    for iteration in range(1000):
        changed = 0
        for axis, sign, source, c in patches:
            for i, j in [(0, 2), (1, 3)]:
                k1, n1 = edge_nodes(c[i], c[(i+1) % 4])
                k2, n2 = edge_nodes(c[j], c[(j+1) % 4])
                union = n1 | n2
                changed += len(union-n1) + len(union-n2)
                lines[k1].update(union)
                lines[k2].update(union)
        if not changed:
            break
    else:
        raise ValueError('Structured edge propagation failed to converge')
    vertices, faces, labels, lookup = [], [], [], {}
    def vertex(q):
        if q not in lookup:
            lookup[q] = len(vertices)
            vertices.append([axes[a][q[a]] for a in range(3)])
        return lookup[q]
    for axis, sign, source, c in patches:
        u, v = (axis+1) % 3, (axis+2) % 3
        cuts_u = sorted(edge_nodes(c[0], c[1])[1])
        cuts_v = sorted(edge_nodes(c[1], c[2])[1])
        for i0, i1 in zip(cuts_u, cuts_u[1:]):
            for j0, j1 in zip(cuts_v, cuts_v[1:]):
                corners = []
                for i, j in [(i0, j0), (i1, j0), (i1, j1), (i0, j1)]:
                    q = list(c[0]); q[u], q[v] = i, j
                    corners.append(vertex(tuple(q)))
                faces.append(corners if sign > 0 else corners[::-1])
                labels.append(source)
    return np.array(vertices), np.array(faces, dtype=np.int32), np.array(labels, dtype=np.int32), iteration+1


def compact(p, structured=False):
    data = np.load(p/'body-grid.npz')
    owner = data['owner'].copy()
    axes = [data[k] for k in 'xyz']
    # The working wall body starts at the measured floor level, not the embedded
    # wall foot below it. Preserve that source geometry in the reference file.
    floor_plane = np.flatnonzero(np.abs(axes[2]) < 1e-8)
    if len(floor_plane) != 1:
        raise ValueError('Measured floor-level plane absent')
    cut = int(floor_plane[0])
    clipped_cells = int(np.count_nonzero(owner[:, :, :cut]))
    owner[:, :, :cut] = 0
    patches = []
    for axis in range(3):
        u, v = (axis+1) % 3, (axis+2) % 3
        rotated = np.transpose(owner, (axis, u, v))
        for plane in range(rotated.shape[0]+1):
            a = rotated[plane-1] if plane else np.zeros(rotated.shape[1:], dtype=np.int32)
            b = rotated[plane] if plane < rotated.shape[0] else np.zeros(rotated.shape[1:], dtype=np.int32)
            for sign in (-1, 1):
                mask = np.where((a > 0) & (b == 0), a, 0) if sign == 1 else np.where((b > 0) & (a == 0), b, 0)
                if not mask.any():
                    continue
                for i0, i1, j0, j1, source in rectangles(mask):
                    corners = []
                    for i, j in [(i0, j0), (i1, j0), (i1, j1), (i0, j1)]:
                        q = [0, 0, 0]
                        q[axis], q[u], q[v] = plane, i, j
                        corners.append(tuple(q))
                    patches.append((axis, sign, source, corners))
    # All corners on a grid line are candidates. Extra subdivision is harmless;
    # missed boundary nodes would create a T-junction.
    lines = defaultdict(set)
    for axis, sign, source, corners in patches:
        for q in corners:
            for a in range(3):
                key = (a, q[(a+1) % 3], q[(a+2) % 3])
                lines[key].add(q[a])
    lines = {key: sorted(value) for key, value in lines.items()}
    if structured:
        vertices, faces, labels, iterations = structured_mesh(patches, lines, axes)
        angle = float(data['angle'])
        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        vertices[:, :2] = vertices[:, :2] @ rotation.T
        np.savez_compressed(p/'body-structured-mesh.npz', vertices=vertices, faces=faces, source_indices=labels)
        report = {'patches': len(patches), 'propagation_iterations': iterations,
                  'vertices': len(vertices), 'quads': len(faces), 'body_z_min_local_m': 0.,
                  'embedded_wall_foot_cells_excluded': clipped_cells,
                  'method': 'measured rectangular patches + opposite-edge propagation to closure; no triangle fans',
                  'scope': 'Wall BODY above measured floor level; source wall feet and slabs excluded'}
        (p/'body-structured.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))
        return
    vertices, quads, labels, vertex_map = [], [], [], {}
    def vertex(co):
        key = tuple(np.round(co, 10))
        if key not in vertex_map:
            vertex_map[key] = len(vertices)
            vertices.append(list(co))
        return vertex_map[key]
    regular = junction = 0
    for axis, sign, source, corners in patches:
        boundary = []
        for q, r in zip(corners, corners[1:]+corners[:1]):
            a = next(k for k in range(3) if q[k] != r[k])
            values = lines[(a, q[(a+1) % 3], q[(a+2) % 3])]
            low, high = sorted([q[a], r[a]])
            cuts = values[bisect.bisect_left(values, low):bisect.bisect_right(values, high)]
            if q[a] > r[a]:
                cuts.reverse()
            for t in cuts[:-1]:
                xyz = list(q)
                xyz[a] = t
                boundary.append([axes[k][xyz[k]] for k in range(3)])
        u, v = (axis+1) % 3, (axis+2) % 3
        boundary = np.array(boundary)
        if len(boundary) == 4:
            pieces = [boundary]
            regular += 1
        else:
            polygon = Polygon(boundary[:, [u, v]])
            triangles = shapely.constrained_delaunay_triangles(polygon)
            if abs(sum(t.area for t in triangles.geoms)-polygon.area) > 1e-9:
                raise ValueError('Incomplete patch triangulation')
            expected = set(map(tuple, boundary[:, [u, v]]))
            actual = set()
            pieces = []
            for t in triangles.geoms:
                xy = np.array(t.exterior.coords[:-1])
                actual.update(map(tuple, xy))
                if not shapely.is_ccw(t.exterior):
                    xy = xy[::-1]
                pts = np.empty((3, 3))
                pts[:, axis], pts[:, u], pts[:, v] = boundary[0, axis], xy[:, 0], xy[:, 1]
                pieces.append(pts)
            if expected != actual:
                raise ValueError('CDT did not preserve patch boundary nodes')
            junction += 1
        for piece in pieces:
            center = np.mean(piece, axis=0)
            for k in range(len(piece)):
                quad = [piece[k], (piece[k]+piece[(k+1) % len(piece)])/2,
                        center, (piece[k]+piece[k-1])/2]
                if sign < 0:
                    quad.reverse()
                quads.append([vertex(q) for q in quad])
                labels.append(source)
    vertices = np.array(vertices)
    angle = float(data['angle'])
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    vertices[:, :2] = vertices[:, :2] @ rotation.T
    np.savez_compressed(p/'body-compact-mesh.npz', vertices=vertices, faces=np.array(quads, dtype=np.int32),
                        source_indices=np.array(labels, dtype=np.int32))
    report = {'patches': len(patches), 'regular_patches': regular, 'junction_patches': junction,
              'vertices': len(vertices), 'quads': len(quads),
              'body_z_min_local_m': float(axes[2][cut]), 'body_z_min_revit_m': 4.5,
              'embedded_wall_foot_cells_excluded': clipped_cells,
              'scope': 'Wall BODY from measured floor level upwards. Slabs and embedded wall feet remain source reference.',
              'method': 'labelled rectangles + shared boundary constraints + quad patches; no smoothing'}
    (p/'body-compact.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output_directory', type=Path)
    parser.add_argument('--structured', action='store_true')
    args = parser.parse_args()
    compact(args.output_directory, args.structured)

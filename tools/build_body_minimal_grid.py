"""Build quad flow from geometric boundaries, without Revit-ID seam cuts."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from compact_floor_body import rectangles, structured_mesh
from optimize_body_loops import optimize


def build(p):
    data = np.load(p/'body-grid.npz')
    owner = data['owner'].copy()
    axes = [data[k] for k in 'xyz']
    owner[:, :, axes[2][:-1] < -1e-8] = 0
    patches, lines = [], defaultdict(set)
    for axis in range(3):
        u, v = (axis+1) % 3, (axis+2) % 3
        occupied = np.transpose(owner > 0, (axis, u, v))
        for plane in range(occupied.shape[0]+1):
            a = occupied[plane-1] if plane else np.zeros(occupied.shape[1:], dtype=bool)
            b = occupied[plane] if plane < occupied.shape[0] else np.zeros(occupied.shape[1:], dtype=bool)
            for sign in (-1, 1):
                mask = (a & ~b) if sign == 1 else (b & ~a)
                if not mask.any():
                    continue
                for i0, i1, j0, j1, _ in rectangles(mask):
                    corners = []
                    for i, j in [(i0,j0), (i1,j0), (i1,j1), (i0,j1)]:
                        q = [0,0,0]
                        q[axis], q[u], q[v] = plane, i, j
                        corners.append(tuple(q))
                    patches.append((axis, sign, 1, corners))
    for axis, sign, _, corners in patches:
        for q in corners:
            for a in range(3):
                lines[(a, q[(a+1)%3], q[(a+2)%3])].add(q[a])
    vertices, faces, _, iterations = structured_mesh(patches, lines, axes)
    print('Geometric grid', len(patches), 'patches', len(faces), 'quads', flush=True)
    # Assign exact source-owner sets covered by each rectangle, using the same
    # explicit representative-owner convention as the source BODY union.
    sources = []
    for f in faces:
        q = vertices[f]
        axis = int(np.argmin(np.ptp(q, axis=0)))
        normal = np.cross(q[1]-q[0], q[2]-q[0])[axis]
        plane = int(np.argmin(abs(axes[axis]-q[0,axis])))
        slices = []
        for a in range(3):
            if a == axis:
                slices.append(plane-1 if normal > 0 else plane)
            else:
                low = int(np.argmin(abs(axes[a]-q[:,a].min())))
                high = int(np.argmin(abs(axes[a]-q[:,a].max())))
                slices.append(slice(low,high))
        source = set(map(int, np.unique(owner[tuple(slices)])))
        if not source or 0 in source:
            raise ValueError('Face extends outside the source boundary')
        sources.append(source)
    before = len(faces)
    vertices, faces, sources, history = optimize(vertices, faces, sources)
    angle = float(data['angle'])
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    vertices[:,:2] = vertices[:,:2] @ rotation.T
    groups, lookup, indices = [], {}, []
    for source in sources:
        key = tuple(sorted(source))
        if key not in lookup:
            lookup[key] = len(groups)+1
            groups.append(list(key))
        indices.append(lookup[key])
    np.savez_compressed(p/'body-optimized-mesh.npz', vertices=vertices, faces=faces,
                        source_indices=np.array(indices,dtype=np.int32))
    report = {'input_faces': 46503, 'output_faces': len(faces), 'output_vertices': len(vertices),
              'reduction_percent': 100*(1-len(faces)/46503), 'source_groups': groups,
              'geometry_patches': len(patches), 'propagation_iterations': iterations,
              'before_loop_cleanup_faces': before, 'history': history, 'vertices_moved': 0,
              'method': 'Geometric contour patches without ID seams; shared quad grid; closed coplanar loop removal',
              'status': 'Saved Blender and surface QA pending'}
    (p/'body-optimization.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_groups','history')}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('output_directory',type=Path)
    build(parser.parse_args().output_directory)

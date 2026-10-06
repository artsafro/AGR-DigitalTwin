"""Independent saved-surface/contour check against occupied source-contour cells.

Uses the re-opened blend coordinates, not the mesh passed to the Blender builder.
Each face must lie on the expected oriented boundary. Same-plane area overlap is
measured, and full surface coverage is compared with the source-cell boundary.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon


def verify(p):
    qa = json.loads((p/'body-qa.json').read_text(encoding='utf-8'))
    g = np.load(p/'body-grid.npz')
    crosscheck = np.load(p/'body-crosscheck-y/body-grid.npz')
    independent_solid_matches = bool(np.array_equal(g['owner'] > 0, np.transpose(crosscheck['owner'], (1, 0, 2)) > 0))
    mesh = np.load(p/'body-readback.npz')
    vertices, faces = mesh['vertices'].copy(), mesh['faces']
    angle = float(g['angle'])
    rotation = np.array([[np.cos(angle), np.sin(angle)], [-np.sin(angle), np.cos(angle)]])
    vertices[:, :2] = vertices[:, :2] @ rotation.T
    axes = [g[k] for k in 'xyz']
    owner = g['owner'].copy()
    owner[:, :, axes[2][:-1] < -1e-8] = 0
    groups = defaultdict(list)
    errors = []
    max_plane_error = 0.
    invalid = nonconvex = 0
    for face in faces:
        q = vertices[face]
        n = np.cross(q[1]-q[0], q[2]-q[0])
        axis = int(np.argmax(abs(n)))
        sign = 1 if n[axis] > 0 else -1
        coord = q[:, axis].mean()
        plane = int(np.argmin(abs(axes[axis]-coord)))
        err = float(abs(q[:, axis]-axes[axis][plane]).max())
        max_plane_error = max(max_plane_error, err)
        if err > 0.000005:
            errors.append({'reason': 'face_off_boundary_plane', 'error_m': err})
        u, v = (axis+1) % 3, (axis+2) % 3
        polygon = Polygon(q[:, [u, v]])
        if not polygon.is_valid or polygon.area <= 1e-12:
            invalid += 1
        if polygon.convex_hull.area - polygon.area > 1e-12:
            nonconvex += 1
        groups[(axis, plane, sign)].append(polygon)
    area_overlap = difference_area = max_hausdorff = 0.
    checked = 0
    for axis in range(3):
        u, v = (axis+1) % 3, (axis+2) % 3
        occ = np.transpose(owner > 0, (axis, u, v))
        for plane in range(occ.shape[0]+1):
            a = occ[plane-1] if plane else np.zeros(occ.shape[1:], dtype=bool)
            b = occ[plane] if plane < occ.shape[0] else np.zeros(occ.shape[1:], dtype=bool)
            for sign in (-1, 1):
                mask = (a & ~b) if sign == 1 else (b & ~a)
                got = groups.pop((axis, plane, sign), [])
                if not mask.any() and not got:
                    continue
                i, j = np.where(mask)
                expected = shapely.union_all(shapely.box(axes[u][i], axes[v][j], axes[u][i+1], axes[v][j+1]))
                actual = shapely.union_all(got)
                overlap = max(0., sum(poly.area for poly in got)-actual.area)
                area_overlap += overlap
                diff = actual.symmetric_difference(expected).area
                difference_area += diff
                distance = float(shapely.hausdorff_distance(actual, expected)) if not actual.is_empty and not expected.is_empty else float('inf')
                max_hausdorff = max(distance, max_hausdorff)
                if overlap > 1e-8 or distance > 0.000005:
                    errors.append({'axis': axis, 'plane': plane, 'sign': sign,
                                   'overlap_area_m2': overlap, 'hausdorff_m': distance})
                checked += 1
    if groups:
        errors.append({'reason': 'faces_on_nonexistent_planes'})
    # Coherently oriented manifold edges are checked directly on the saved mesh.
    edge = np.stack([faces, np.roll(faces, -1, axis=1)], axis=2).reshape(-1, 2)
    key = np.sort(edge, axis=1)
    _, inverse = np.unique(key, axis=0, return_inverse=True)
    sums = np.bincount(inverse, weights=np.where(edge[:, 0] < edge[:, 1], 1, -1))
    inconsistent = int(np.count_nonzero(sums))
    result = {'independent_x_y_source_solids_match': independent_solid_matches,
              'oriented_boundary_plane_groups_checked': checked,
              'source_boundary_hausdorff_max_m': max_hausdorff,
              'readback_plane_error_max_m': max_plane_error,
              'coplanar_overlap_area_m2': area_overlap,
              'boundary_symmetric_difference_area_m2': difference_area,
              'invalid_or_zero_area_quads': invalid, 'nonconvex_quads': nonconvex,
              'inconsistent_winding_edges': inconsistent, 'errors': errors,
              'numeric_plane_distance_tolerance_m': 0.000005,
              'overlap_area_tolerance_per_plane_m2': 1e-8,
              'intersection_method': 'Exhaustive oriented boundary coverage of a disjoint Cartesian solid; '
                                     'all faces contained in its boundary and coplanar overlaps measured. '
                                     'Only applies to this BODY construction, not arbitrary DCC geometry.'}
    topology = all(qa[k] == 0 for k in ['exact_duplicate_vertices', 'exact_duplicate_faces', 'boundary_edges', 'nonmanifold_edges', 'nonmanifold_vertices', 'wire_edges', 'loose_vertices', 'zero_area_faces'])
    topology = topology and qa['face_connectivity_readback'] and qa['face_source_mapping_readback'] and qa['readback_max_error_m'] <= 0.000005
    result['geometry_checks_passed'] = bool(topology and independent_solid_matches and not errors and invalid == 0 and nonconvex == 0 and inconsistent == 0)
    qa['surface_verification'] = result
    qa['overlap_check'] = result['intersection_method']
    qa['remaining'] = [f'Artist review of {qa["faces_aspect_over_100"]} high-aspect-ratio faces; quads do not imply square cells',
                       'Separate window modelling and measured recess into openings',
                       'Slabs, doors, accessories, source materials and full-floor final Attach validation']
    qa['status'] = 'BODY geometry verified; full-floor delivery and grid-quality review pending' if result['geometry_checks_passed'] else 'BODY verification failed'
    (p/'body-qa.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    (p/'body-surface-check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result))
    if not result['geometry_checks_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output_directory', type=Path)
    verify(parser.parse_args().output_directory)

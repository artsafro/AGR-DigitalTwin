"""Prototype for OBR22: reconstruct an orthogonal wall body from measured contours.

No source triangle connectivity is copied. Planar side contours define occupancy;
the boundary of their union is a conforming quadrilateral Cartesian surface.
Only orthogonal source walls are accepted, with a measured precision budget.
Run with the project's Python (numpy + shapely), then build_floor_body_blender.py.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon


def cluster_axis(values, span=0.00025):
    order = np.argsort(values)
    groups = []
    for i in order:
        if not groups or values[i] - values[groups[-1][0]] > span:
            groups.append([i])
        else:
            groups[-1].append(i)
    centers = np.array([(values[g[0]] + values[g[-1]]) / 2 for g in groups])
    indices = np.empty(len(values), dtype=np.int32)
    for k, g in enumerate(groups):
        indices[g] = k
    return centers, indices


def source_axes(walls):
    angles = []
    horizontal = []
    for item in walls:
        v = np.array(item['vertices'])
        for f in item['faces']:
            for i, j in zip(f, f[1:] + f[:1]):
                d = v[j] - v[i]
                length = np.linalg.norm(d[:2])
                if length > 1e-8 and abs(d[2]) < 1e-5:
                    edge_angle = np.arctan2(d[1], d[0]) % (np.pi / 2)
                    horizontal.append((length, edge_angle))
                    if length > 2:
                        angles.append(edge_angle)
    if not angles:
        if not horizontal:
            raise ValueError('No measured horizontal edges for source axes')
        longest = max(length for length, angle in horizontal)
        angles = [angle for length, angle in horizontal if length >= longest*.95]
    angle = float(np.median(angles))
    rotation = np.array([[np.cos(angle), np.sin(angle)], [-np.sin(angle), np.cos(angle)]])
    vertices = np.concatenate([np.array(w['vertices']) for w in walls])
    vertices[:, :2] = vertices[:, :2] @ rotation.T
    return angle, rotation, vertices


def contour_axes(walls, vertices, span=0.0004):
    """Keep each measured planar face on ONE plane before global alignment.

    Scalar clustering alone can split the same source plane at a cluster boundary.
    Plane connectivity is therefore authoritative; no topology is inferred from
    a nearby coordinate without checking the complete precision envelope.
    """
    count = len(vertices)
    parents = [np.arange(count) for _ in range(3)]
    def root(p, i):
        while p[i] != i:
            p[i] = p[p[i]]
            i = p[i]
        return int(i)
    offset = 0
    for wall in walls:
        for face in wall['faces']:
            ids = np.array(face) + offset
            extent = np.ptp(vertices[ids], axis=0)
            axis = int(np.argmin(extent))
            if extent[axis] > span:
                raise ValueError(f'Non-orthogonal source: {wall["name"]}')
            p = parents[axis]
            r = root(p, ids[0])
            for i in ids[1:]:
                p[root(p, i)] = r
        offset += len(wall['vertices'])
    axes, indices = [], []
    for a, parent in enumerate(parents):
        components = {}
        for i in range(count):
            components.setdefault(root(parent, i), []).append(i)
        groups = sorted(components.values(), key=lambda g: float(vertices[g, a].min()))
        merged = []
        for g in groups:
            lo, hi = vertices[g, a].min(), vertices[g, a].max()
            if hi-lo > span:
                raise ValueError(f'Plane connectivity exceeds precision budget: {a}, {hi-lo}')
            if merged and max(hi, merged[-1][2])-merged[-1][1] <= span:
                merged[-1][0].extend(g)
                merged[-1][2] = max(hi, merged[-1][2])
            else:
                merged.append([g, lo, hi])
        ax = np.array([(lo+hi)/2 for g, lo, hi in merged])
        idx = np.empty(count, dtype=np.int32)
        for k, (g, lo, hi) in enumerate(merged):
            idx[g] = k
        if (np.diff(ax) <= 0).any():
            raise ValueError('Overlapping precision clusters')
        axes.append(ax)
        indices.append(idx)
    return axes, indices


def rebuild_body(source, out, crosscheck_y=False):
    walls = [x for x in source['items'] if x['group'].startswith('02_')]
    angle, rotation, vertices = source_axes(walls)
    if crosscheck_y:
        vertices = vertices[:, [1, 0, 2]]
    axes, coords = contour_axes(walls, vertices)
    snapped = np.stack([axes[a][coords[a]] for a in range(3)], axis=1)
    displacement = np.linalg.norm(vertices - snapped, axis=1)
    if displacement.max() > 0.00025:
        raise ValueError('Source precision budget exceeded')
    indexed = np.stack(coords, axis=1)
    shape = tuple(len(a) - 1 for a in axes)
    owner = np.zeros(shape, dtype=np.int32)
    centers = [(a[:-1] + a[1:]) / 2 for a in axes]
    all_contours, wall_records, failures = [], [], []
    offset = 0
    for wi, wall in enumerate(walls, 1):
        iv = indexed[offset:offset + len(wall['vertices'])]
        vv = vertices[offset:offset + len(wall['vertices'])]
        offset += len(iv)
        planes = {}
        for tri in wall['triangles']:
            q, iq = vv[tri], iv[tri]
            extent = np.ptp(q, axis=0)
            flat = int(np.argmin(extent))
            if extent[flat] > 0.00025:
                raise ValueError(f'Non-orthogonal wall: {wall["name"]}')
            if flat != 0:
                continue
            if len(set(iq[:, 0])) != 1:
                # A clustering boundary must not split one source plane.
                failures.append({'id': wall['props']['revit_element_id'], 'reason': 'split_source_plane'})
                continue
            poly = Polygon([(axes[1][i[1]], axes[2][i[2]]) for i in iq])
            if poly.area > 1e-12:
                planes.setdefault(int(iq[0, 0]), []).append(poly)
        bounds = [(int(iv[:, a].min()), int(iv[:, a].max())) for a in range(3)]
        (x0, x1), (y0, y1), (z0, z1) = bounds
        if min(x1-x0, y1-y0, z1-z0) <= 0:
            failures.append({'id': wall['props']['revit_element_id'], 'reason': 'collapsed_source'})
            continue
        Y, Z = np.meshgrid(centers[1][y0:y1], centers[2][z0:z1], indexing='ij')
        state = np.zeros(Y.shape, dtype=bool)
        crossing = {}
        for x, polygons in planes.items():
            contour = shapely.union_all(polygons)
            crossing[x] = shapely.contains_xy(contour, Y, Z)
            all_contours.append({'wall_index': wi, 'x_index': x, 'geometry': shapely.to_geojson(contour)})
        count = 0
        overlap_count = 0
        for x in range(x0, x1 + 1):
            if x in crossing:
                state ^= crossing[x]
            if x == x1:
                if state.any():
                    failures.append({'id': wall['props']['revit_element_id'], 'reason': 'unclosed_contour', 'cells': int(state.sum())})
                break
            view = owner[x, y0:y1, z0:z1]
            overlap_count += int(np.count_nonzero(view[state]))
            view[state] = wi
            count += int(state.sum())
        wall_records.append({'index': wi, 'name': wall['name'], 'props': wall['props'],
                             'solid_cells': count, 'overlapping_source_cells': overlap_count})
    report = {'method': 'measured planar contours -> solid union -> conforming quad boundary',
              'axis_rotation_radians': angle, 'grid_shape': shape,
              'source_walls': len(walls), 'source_snap_max_m': float(displacement.max()),
              'source_snap_rms_m': float(np.sqrt(np.mean(displacement**2))),
              'precision_budget_m': 0.00025, 'failures': failures,
              'contours': len(all_contours), 'wall_records': wall_records,
              'local_to_revit_internal_m': source['local_to_revit_internal_m'],
              'status': 'prototype; saved Blender geometry QA required'}
    (out / 'body-contours.json').write_text(json.dumps(all_contours, ensure_ascii=False), encoding='utf-8')
    (out / 'body-build.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if failures:
        print(json.dumps({'failures': failures[:15], 'count': len(failures)}, ensure_ascii=False))
        raise ValueError('Source contour reconstruction is not closed; see body-build.json')
    np.savez_compressed(out / 'body-grid.npz', owner=owner, x=axes[0], y=axes[1], z=axes[2], angle=angle)
    print(json.dumps({k: v for k, v in report.items() if k not in ('wall_records', 'local_to_revit_internal_m')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output_directory', type=Path)
    parser.add_argument('--crosscheck-y', action='store_true')
    args = parser.parse_args()
    source = json.loads((args.output_directory / 'contour-source.json').read_text(encoding='utf-8'))
    out = args.output_directory / 'body-crosscheck-y' if args.crosscheck_y else args.output_directory
    out.mkdir(parents=True, exist_ok=True)
    rebuild_body(source, out, args.crosscheck_y)

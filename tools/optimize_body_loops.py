"""Remove only closed redundant quad loops from the measured BODY.

Every removed edge separates coplanar faces. Every removed vertex has valence
four and its two surviving edges are collinear. A batch never touches a face
twice. Each resulting polygon must still be a convex rectangle with the same
area. No vertex is moved; original face provenance is unioned, never discarded.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def optimize(vertices, faces, sources):
    faces = [list(map(int, f)) for f in faces]
    sources = [set(s) for s in sources]
    history = []
    for iteration in range(100):
        edge_faces, vertex_edges = defaultdict(list), defaultdict(set)
        face_edges = []
        for fi, f in enumerate(faces):
            keys = [tuple(sorted((a, b))) for a, b in zip(f, f[1:]+f[:1])]
            face_edges.append(keys)
            for key in keys:
                edge_faces[key].append(fi)
                for v in key:
                    vertex_edges[v].add(key)
        if any(len(fs) != 2 for fs in edge_faces.values()):
            raise ValueError('Optimizer requires a closed manifold input')
        normals = []
        for f in faces:
            q = vertices[f]
            n = np.cross(q[1]-q[0], q[2]-q[0])
            normals.append(n/np.linalg.norm(n))
        normals = np.array(normals)
        flat = {e for e, (a, b) in edge_faces.items() if np.dot(normals[a], normals[b]) > 1-1e-10}
        transitions = {}
        for e in flat:
            neighbours = []
            for vertex in e:
                incident = vertex_edges[vertex]
                if len(incident) != 4:
                    break
                adjacent = set()
                for fi in edge_faces[e]:
                    adjacent.update(k for k in face_edges[fi] if vertex in k and k != e)
                opposite = incident - adjacent - {e}
                if len(adjacent) != 2 or len(opposite) != 1:
                    break
                other = next(iter(opposite))
                if other not in flat:
                    break
                remaining = [vertices[k[0] if k[1] == vertex else k[1]]-vertices[vertex] for k in adjacent]
                a, b = remaining
                # Surviving crease/surface edges must form one straight segment.
                if np.dot(a, b) >= 0 or np.linalg.norm(np.cross(a, b)) > 1e-9*np.linalg.norm(a)*np.linalg.norm(b):
                    break
                neighbours.append(other)
            if len(neighbours) == 2:
                transitions[e] = neighbours
        loops, seen = [], set()
        for start in sorted(transitions):
            if start in seen:
                continue
            pending, component, valid = [start], set(), True
            while pending:
                e = pending.pop()
                if e in component:
                    continue
                component.add(e)
                if e not in transitions:
                    valid = False
                    continue
                pending.extend(n for n in transitions[e] if n not in component)
            seen.update(component)
            if not valid:
                continue
            touched = [fi for e in component for fi in edge_faces[e]]
            if len(touched) != len(set(touched)):
                continue
            loops.append(component)
        # Prefer short local loops. Disjoint face sets make the operation atomic.
        selected, touched = [], set()
        for loop in sorted(loops, key=lambda x: (len(x), min(x))):
            fs = {fi for e in loop for fi in edge_faces[e]}
            if fs & touched:
                continue
            selected.append(loop)
            touched.update(fs)
        if not selected:
            break
        remove_edges = set().union(*selected)
        remove_vertices = {v for e in remove_edges for v in e}
        new_faces, new_sources = [], []
        for fi, f in enumerate(faces):
            if fi not in touched:
                if remove_vertices.intersection(f):
                    raise ValueError('Loop removal would leave a hanging vertex')
                new_faces.append(f)
                new_sources.append(sources[fi])
        for edge in sorted(remove_edges):
            a, b = edge_faces[edge]
            directed = []
            for fi in (a, b):
                f = faces[fi]
                directed.extend((i, j) for i, j in zip(f, f[1:]+f[:1]) if tuple(sorted((i, j))) != edge)
            successor = dict(directed)
            ring, current = [], directed[0][0]
            for _ in range(6):
                ring.append(current)
                current = successor[current]
            if current != ring[0]:
                raise ValueError('Invalid merged boundary')
            quad = [v for v in ring if v not in remove_vertices]
            if len(quad) != 4 or len(set(quad)) != 4:
                raise ValueError('Loop removal would create a non-quad')
            q = vertices[quad]
            sides = np.roll(q, -1, axis=0)-q
            if any(abs(np.dot(sides[i], sides[(i+1) % 4])) > 1e-8*np.linalg.norm(sides[i])*np.linalg.norm(sides[(i+1) % 4]) for i in range(4)):
                raise ValueError('Merged face is not rectangular')
            def area(f):
                q = vertices[f]
                return np.linalg.norm(np.cross(q[1]-q[0], q[3]-q[0]))
            if abs(area(quad)-area(faces[a])-area(faces[b])) > 1e-9:
                raise ValueError('Loop removal changed surface area')
            new_faces.append(quad)
            new_sources.append(sources[a] | sources[b])
        history.append({'iteration': iteration+1, 'loops': len(selected), 'removed_edges': len(remove_edges),
                        'faces_before': len(faces), 'faces_after': len(new_faces)})
        faces, sources = new_faces, new_sources
        print(history[-1], flush=True)
    used, inverse = np.unique(np.array(faces).ravel(), return_inverse=True)
    return vertices[used], inverse.reshape(-1, 4).astype(np.int32), sources, history


def run(p):
    original = np.load(p/'body-structured-mesh.npz')
    vertices, faces, sources, history = optimize(original['vertices'], original['faces'],
                                                [{int(s)} for s in original['source_indices']])
    groups, lookup, indices = [], {}, []
    for source in sources:
        key = tuple(sorted(source))
        if key not in lookup:
            lookup[key] = len(groups)+1
            groups.append(list(key))
        indices.append(lookup[key])
    np.savez_compressed(p/'body-optimized-mesh.npz', vertices=vertices, faces=faces,
                        source_indices=np.array(indices, dtype=np.int32))
    report = {'input_faces': len(original['faces']), 'output_faces': len(faces),
              'input_vertices': len(original['vertices']), 'output_vertices': len(vertices),
              'reduction_percent': 100*(1-len(faces)/len(original['faces'])),
              'source_groups': groups, 'history': history,
              'method': 'Closed coplanar quad loops; remove only valence-4 vertices with collinear surviving edges',
              'vertices_moved': 0, 'status': 'Saved Blender readback and surface checks pending'}
    (p/'body-optimization.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_groups', 'history')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output_directory', type=Path)
    run(parser.parse_args().output_directory)

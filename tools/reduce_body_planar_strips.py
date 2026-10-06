"""Local quad diagonal collapses on planar interiors; geometric creases fixed.

Only narrow, small faces are considered. The quad link condition and strict
convexity of every affected face are mandatory. Boundary vertices are fixed;
surface area is conserved. Full surface/readback verification remains required.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def reduce(vertices, faces, sources, max_passes=60):
    vertices, faces = vertices.copy(), faces.copy()
    sources = [set(x) for x in sources]
    history = []
    for iteration in range(max_passes):
        vf, neighbours = defaultdict(set), defaultdict(set)
        for fi, f in enumerate(faces):
            for a, b in zip(f, np.roll(f,-1)):
                vf[int(a)].add(fi)
                neighbours[int(a)].add(int(b))
                neighbours[int(b)].add(int(a))
        q = vertices[faces]
        normals = np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0])
        normals /= np.linalg.norm(normals,axis=1)[:,None]
        interior = set()
        for v, fs in vf.items():
            ns = normals[list(fs)]
            if np.min(ns @ ns[0]) > 1-1e-9:
                interior.add(v)
        lengths = np.linalg.norm(np.roll(q,-1,axis=1)-q,axis=2)
        area = np.linalg.norm(np.cross(q[:,1]-q[:,0],q[:,3]-q[:,0]),axis=1)
        candidates = np.flatnonzero((lengths.min(axis=1) < .02) & (area < .1))
        order = candidates[np.argsort(lengths[candidates].min(axis=1))]
        blocked, deleted, changes = set(), set(), []
        for fi in order:
            f = faces[fi]
            for i in (0,1):
                a, b, c, d = map(int,np.roll(f,-i))
                if a not in interior or c not in interior:
                    continue
                affected = vf[a] | vf[c]
                if affected & blocked or neighbours[a] & neighbours[c] != {b,d} or vf[a] & vf[c] != {int(fi)}:
                    continue
                n = normals[fi]
                if any(np.dot(normals[j],n) < 1-1e-9 for j in affected):
                    continue
                position = (vertices[a]+vertices[c])/2
                before_area = after_area = 0.
                replacements = {}
                valid = True
                for j in affected:
                    old = vertices[faces[j]]
                    before_area += sum(np.dot(np.cross(old[k],old[(k+1)%4]),n) for k in range(4))/2
                    if j == fi:
                        continue
                    new_f = np.where(faces[j]==c,a,faces[j])
                    if len(set(new_f)) != 4:
                        valid=False;break
                    pts = vertices[new_f].copy()
                    pts[new_f==a] = position
                    edges=np.roll(pts,-1,axis=0)-pts
                    lens=np.linalg.norm(edges,axis=1)
                    corner_sines=np.cross(edges,np.roll(edges,-1,axis=0)) @ n / (lens*np.roll(lens,-1))
                    # Reject concave/bow-tie/near-collinear corners. A deliberate
                    # transition quad needs a usable angle, not merely four IDs.
                    if lens.min()<1e-7 or corner_sines.min()<.087:
                        valid=False;break
                    after_area += sum(np.dot(np.cross(pts[k],pts[(k+1)%4]),n) for k in range(4))/2
                    replacements[j]=new_f
                if not valid or abs(before_area-after_area)>1e-8:
                    continue
                for j,new_f in replacements.items():
                    faces[j]=new_f
                    sources[j] |= sources[fi]
                vertices[a]=position
                deleted.add(int(fi))
                # Also guard neighbouring faces against stale vertex incidence.
                touched_vertices={int(v) for j in affected for v in faces[j]}
                for v in touched_vertices:
                    blocked.update(vf[v])
                changes.append((a,c))
                break
        if not deleted:
            break
        keep=[j for j in range(len(faces)) if j not in deleted]
        faces=faces[keep]
        sources=[sources[j] for j in keep]
        history.append({'iteration':iteration+1,'removed_quads':len(deleted),'remaining_quads':len(faces)})
        print(history[-1],flush=True)
    used,inverse=np.unique(faces.ravel(),return_inverse=True)
    return vertices[used],inverse.reshape(-1,4).astype(np.int32),sources,history


def run(p, apply=False):
    data=np.load(p/'body-optimized-mesh.npz')
    report=json.loads((p/'body-optimization.json').read_text(encoding='utf-8'))
    sources=[report['source_groups'][i-1] for i in data['source_indices']]
    vertices,faces,sources,history=reduce(data['vertices'],data['faces'],sources)
    groups,lookup,indices=[],{},[]
    for source in sources:
        key=tuple(sorted(source))
        if key not in lookup:
            lookup[key]=len(groups)+1;groups.append(list(key))
        indices.append(lookup[key])
    np.savez_compressed(p/('body-optimized-mesh.npz' if apply else 'body-strip-candidate.npz'),vertices=vertices,faces=faces,source_indices=np.array(indices,dtype=np.int32))
    report.update(output_faces=len(faces),output_vertices=len(vertices),source_groups=groups,
                  strip_history=history,reduction_percent=100*(1-len(faces)/report['input_faces']),
                  method=report['method']+'; planar interior quad transitions',
                  vertices_moved='Planar interior vertices only; all geometric crease vertices fixed',
                  provenance_note='Source-owner sets propagated conservatively to transition faces; may include adjacent source contributions')
    (p/('body-optimization.json' if apply else 'body-strip-candidate.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('RESULT',len(faces))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output_directory',type=Path)
    parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    run(args.output_directory,args.apply)

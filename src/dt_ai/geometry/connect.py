"""Conforming opposite-edge quad subdivision, equivalent to propagated Connect cuts."""
import math
import numpy as np


def _subdivide(vertices,faces,max_side):
    v=np.asarray(vertices,dtype=float);f=np.asarray(faces,dtype=int)
    keys=[];counts={}
    for face in f:
        edges=[tuple(sorted((int(a),int(b)))) for a,b in zip(face,np.roll(face,-1))]
        keys.append(edges)
        for a,b in edges:counts[(a,b)]=max(1,math.ceil(np.linalg.norm(v[a]-v[b])/max_side))
    changed=True
    while changed:
        changed=False
        for edges in keys:
            for a,b in [(edges[0],edges[2]),(edges[1],edges[3])]:
                n=max(counts[a],counts[b])
                if counts[a]!=n or counts[b]!=n:changed=True
                counts[a]=counts[b]=n
    out_v=[];out_f=[];parents=[];lookup={}
    for fi,(face,edges) in enumerate(zip(f,keys)):
        q=v[face];nx,ny=counts[edges[0]],counts[edges[1]]
        grid=[]
        for j in range(ny+1):
            row=[];t=j/ny
            for i in range(nx+1):
                s=i/nx;point=(1-s)*(1-t)*q[0]+s*(1-t)*q[1]+s*t*q[2]+(1-s)*t*q[3]
                key=tuple(np.round(point,8))
                if key not in lookup:lookup[key]=len(out_v);out_v.append(point.tolist())
                row.append(lookup[key])
            grid.append(row)
        for j in range(ny):
            for i in range(nx):
                out_f.append([grid[j][i],grid[j][i+1],grid[j+1][i+1],grid[j+1][i]]);parents.append(fi)
    result=np.array(out_v);faces=np.array(out_f,dtype=int)
    assert np.max(np.linalg.norm(result[faces]-np.roll(result[faces],1,axis=1),axis=2))<=max_side+1e-6
    return result,faces,parents


def connect_quads(vertices, faces, *, max_side_m):
    """Prototype: metres, convex nondegenerate quads; returns vertices, quads, parent IDs.

    Parent IDs preserve provenance for caller-owned material IDs and manual decisions.
    No approval, UV, file export or full topology validation is performed here.
    Coordinate welding at 8 decimal places retains the legacy OBR22 behaviour.
    """
    if not math.isfinite(max_side_m) or max_side_m <= 0:
        raise ValueError("max_side_m must be finite and positive")
    v = np.asarray(vertices, dtype=float)
    f = np.asarray(faces)
    if v.ndim != 2 or v.shape[1] != 3 or not np.isfinite(v).all():
        raise ValueError("vertices must be finite N x 3 coordinates in metres")
    if f.ndim != 2 or f.shape[1] != 4 or not np.issubdtype(f.dtype, np.integer):
        raise ValueError("faces must be integer M x 4 indices")
    if not len(f) or (f < 0).any() or (f >= len(v)).any():
        raise ValueError("faces must be nonempty and reference existing vertices")
    if any(len(set(face)) != 4 for face in f.tolist()):
        raise ValueError("a quad must reference four distinct vertices")
    return _subdivide(v, f, max_side_m)

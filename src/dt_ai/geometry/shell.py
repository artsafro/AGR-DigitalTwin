"""Exterior quads plus inward boundary rims; no inner back faces.

Input is an already reviewed exterior surface in local metres, not raw RVT.
"""
from collections import defaultdict
import math
import numpy as np

class Mesh:
    def __init__(self,name):
        self.name=name;self.vertices=[];self.faces=[];self.materials=[];self.lookup={}
    def face(self,points,normal,material=0):
        q=np.array(points,dtype=float)
        if np.dot(np.cross(q[1]-q[0],q[2]-q[0]),normal)<0:q=q[::-1]
        f=[]
        for v in q:
            key=tuple(np.round(v,9))
            if key not in self.lookup:self.lookup[key]=len(self.vertices);self.vertices.append(v.tolist())
            f.append(self.lookup[key])
        self.faces.append(f);self.materials.append(material)
    def dump(self):return {'name':self.name,'vertices':self.vertices,'faces':self.faces,'materials':self.materials}


def shell_body(vertices, faces, outward_normals, *, thickness_m, name,
               source_refs, units, tolerance_m=1e-7):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a nonempty string")
    if units != "m":
        raise ValueError("Input must explicitly use metres")
    if not math.isfinite(thickness_m) or thickness_m <= 0:
        raise ValueError("thickness_m must be finite and positive")
    if not math.isfinite(tolerance_m) or tolerance_m <= 0:
        raise ValueError("tolerance_m must be finite and positive")
    v = np.asarray(vertices, dtype=float)
    f = np.asarray(faces)
    n = np.asarray(outward_normals, dtype=float)
    if v.ndim != 2 or v.shape[1] != 3 or not np.isfinite(v).all():
        raise ValueError("Expected finite N x 3 vertices")
    if f.ndim != 2 or f.shape[1] != 4 or not len(f) or not np.issubdtype(f.dtype, np.integer):
        raise ValueError("Expected nonempty integer quad indices")
    if (f < 0).any() or (f >= len(v)).any() or any(len(set(q)) != 4 for q in f.tolist()):
        raise ValueError("Invalid quad indices")
    if n.shape != (len(f), 3) or not np.isfinite(n).all():
        raise ValueError("One finite outward normal per face required")
    if len(source_refs) != len(f) or any(not isinstance(r, str) or not r.strip() for r in source_refs):
        raise ValueError("One source reference per face required")
    if not np.allclose(np.linalg.norm(n, axis=1), 1, atol=1e-8, rtol=0):
        raise ValueError("Normals must be unit length")
    # This prototype covers vertical orthogonal facade planes only.
    if not np.all(np.isclose(np.max(np.abs(n[:, :2]), axis=1), 1, atol=1e-8)) or not np.allclose(n[:, 2], 0):
        raise ValueError("Only local orthogonal vertical facade normals supported")
    body = Mesh(name)
    normals = defaultdict(set)
    edges = {}
    refs = []
    seen = set()
    for fi, (face, normal) in enumerate(zip(f, n)):
        if tuple(sorted(face)) in seen:
            raise ValueError("Duplicate input face")
        seen.add(tuple(sorted(face)))
        q = v[face]
        cross = np.cross(q[1]-q[0], q[2]-q[0])
        if np.linalg.norm(cross) <= tolerance_m**2 or np.max(np.abs((q-q[0]) @ normal)) > tolerance_m:
            raise ValueError("Degenerate or nonplanar facade face")
        signs = [np.dot(np.cross(q[(i+1)%4]-q[i], q[(i+2)%4]-q[(i+1)%4]), normal) for i in range(4)]
        if not (all(x > tolerance_m**2 for x in signs) or all(x < -tolerance_m**2 for x in signs)):
            raise ValueError("Expected convex quad")
        body.face(q, normal)
        refs.append({"role": "exterior", "source_face": fi, "source_ref": source_refs[fi]})
        for i in face:
            normals[int(i)].add(tuple(normal))
        for i, j in zip(face, np.roll(face, -1)):
            key = tuple(sorted((int(i), int(j))))
            edges.setdefault(key, []).append((int(i), int(j), fi))
            if len(edges[key]) > 2:
                raise ValueError("Nonmanifold input edge")
    inner = v.copy()
    for i, ns in normals.items():
        A = np.array(list(ns))
        delta = np.linalg.lstsq(A, np.full(len(A), -thickness_m), rcond=None)[0]
        if np.max(np.abs(A @ delta + thickness_m)) > tolerance_m:
            raise ValueError("Incompatible inward corner planes")
        inner[i] += delta
    for uses in edges.values():
        if len(uses) != 1:
            continue
        i, j, fi = uses[0]
        q = np.array([v[i], inner[i], inner[j], v[j]])
        body.face(q, np.cross(q[1]-q[0], q[2]-q[0]))
        refs.append({"role": "rim", "source_face": fi, "source_ref": source_refs[fi], "source_edge": [i, j]})
    return {"mesh": body.dump(), "face_sources": refs,
            "thickness_m": thickness_m, "inner_faces": False}

"""Triangle soup of a mesh dump (tools/source/measure_spec_blender.py) in the object system.

One array set for every mesh of the dump: welded vertices, triangles, material id per triangle
(slot index + 1 = 3ds Max material id), the source polygon sizes when the dump has them, and the
LEVEL_<name> helpers. Pure numpy; never run in Blender.
"""
from dataclasses import dataclass

import numpy as np

LEVEL_PREFIX = "LEVEL_"


@dataclass
class Soup:
    vertices: np.ndarray        # (n, 3) float, object system
    triangles: np.ndarray       # (m, 3) int into vertices
    material_ids: np.ndarray    # (m,) int
    polygon_sizes: np.ndarray | None  # vertex count of every source polygon; None = not in the dump
    levels: dict[str, float]    # LEVEL_<name> helper elevations, object system

    def corners(self) -> np.ndarray:
        """(m, 3, 3) corner points of every triangle."""
        return self.vertices[self.triangles]


def _apply(m: np.ndarray, points) -> np.ndarray:
    p = np.asarray(points, dtype=float).reshape(-1, 3)
    return p @ m[:3, :3].T + m[:3, 3]


def from_dump(dump: dict, to_object=None) -> Soup:
    """All meshes of a dump; to_object: 4x4 matrix from the dump's frame (default identity)."""
    m = np.eye(4) if to_object is None else np.asarray(to_object, dtype=float)
    verts, tris, mids, sizes = [], [], [], []
    has_sizes = all("polygon_sizes" in mesh for mesh in dump["meshes"])
    base = 0
    for mesh in dump["meshes"]:
        v = _apply(m, mesh["vertices"])
        t = np.asarray(mesh["triangles"], dtype=int).reshape(-1, 3)
        verts.append(v)
        tris.append(t + base)
        mids.append(np.asarray(mesh.get("material_ids", [0] * len(t)), dtype=int))
        if has_sizes:
            sizes.append(np.asarray(mesh["polygon_sizes"], dtype=int))
        base += len(v)
    levels = {h["name"][len(LEVEL_PREFIX):]: float(_apply(m, h["location"])[0, 2])
              for h in dump.get("helpers", []) if h["name"].startswith(LEVEL_PREFIX)}
    cat = lambda parts, shape, dtype: np.concatenate(parts) if parts else np.zeros(shape, dtype)  # noqa: E731
    return Soup(cat(verts, (0, 3), float), cat(tris, (0, 3), int), cat(mids, (0,), int),
                cat(sizes, (0,), int) if has_sizes else None, levels)


def weld(vertices: np.ndarray, weld_m: float) -> np.ndarray:
    """Vertex -> welded id; vertices on one weld_m grid cell are one vertex (across meshes)."""
    if len(vertices) == 0:
        return np.zeros(0, dtype=int)
    keys = np.round(vertices / weld_m).astype(np.int64)
    _, ids = np.unique(keys, axis=0, return_inverse=True)
    return ids.reshape(-1)


def edge_uses(triangles: np.ndarray, ids: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Undirected welded edges, how many triangles use each, and the edge index of every triangle side."""
    t = ids[triangles]
    e = np.sort(np.stack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]], axis=1).reshape(-1, 2), axis=1)
    edges, inverse, counts = np.unique(e, axis=0, return_inverse=True, return_counts=True)
    return edges, counts, inverse.reshape(-1, 3)


def parts(triangles: np.ndarray, ids: np.ndarray) -> np.ndarray:
    """Connected part of every triangle through shared welded vertices (union-find)."""
    parent = np.arange(int(ids.max()) + 1 if len(ids) else 0)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b, c in ids[triangles]:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(rc)] = ra
    return np.array([find(a) for a in ids[triangles[:, 0]]], dtype=int)

"""Triangle soup of a mesh dump (tools/source/measure_spec_blender.py) in the object system.

One array set for every mesh of the dump: welded vertices, triangles, material id per triangle
(slot index + 1 = 3ds Max material id), the source polygon sizes when the dump has them, and the
LEVEL_<name> helpers. Pure numpy; never run in Blender.
"""
from dataclasses import dataclass

import numpy as np

LEVEL_PREFIX = "LEVEL_"
COLLISION_PREFIX = "UCX_"  # collision hulls (reg p.36, docs/domain/geometry.md) are no render geometry


@dataclass
class Soup:
    vertices: np.ndarray        # (n, 3) float, object system
    triangles: np.ndarray       # (m, 3) int into vertices
    material_ids: np.ndarray    # (m,) int
    polygon_sizes: np.ndarray | None  # vertex count of every source polygon; None = absent or inconsistent
    levels: dict[str, float]    # LEVEL_<name> helper elevations, object system
    collisions: int = 0         # UCX_ meshes left out
    mesh_names: tuple = ()      # the dump's render mesh names, in order
    mesh_index: np.ndarray | None = None   # (m,) the mesh each triangle comes from (into mesh_names)

    def corners(self) -> np.ndarray:
        """(m, 3, 3) corner points of every triangle."""
        return self.vertices[self.triangles]


def _apply(m: np.ndarray, points) -> np.ndarray:
    p = np.asarray(points, dtype=float).reshape(-1, 3)
    return p @ m[:3, :3].T + m[:3, 3]


def from_dump(dump: dict, to_object=None) -> Soup:
    """Render meshes of a dump (UCX_ collisions left out); to_object: 4x4 matrix from the dump's frame.
    Polygon sizes count only when every mesh has them and they add up to its triangles."""
    m = np.eye(4) if to_object is None else np.asarray(to_object, dtype=float)
    verts, tris, mids, sizes, owner = [], [], [], [], []
    render = [x for x in dump["meshes"] if not x["name"].startswith(COLLISION_PREFIX)]
    has_sizes = all("polygon_sizes" in mesh and len(mesh["triangles"]) ==
                    sum(max(int(k) - 2, 0) for k in mesh["polygon_sizes"]) for mesh in render)
    base = 0
    for mesh in render:
        v = _apply(m, mesh["vertices"])
        t = np.asarray(mesh["triangles"], dtype=int).reshape(-1, 3)
        verts.append(v)
        tris.append(t + base)
        mids.append(np.asarray(mesh.get("material_ids", [0] * len(t)), dtype=int))
        owner.append(np.full(len(t), len(owner), dtype=int))
        if has_sizes:
            sizes.append(np.asarray(mesh["polygon_sizes"], dtype=int))
        base += len(v)
    levels = {h["name"][len(LEVEL_PREFIX):]: float(_apply(m, h["location"])[0, 2])
              for h in dump.get("helpers", []) if h["name"].startswith(LEVEL_PREFIX)}
    cat = lambda parts, shape, dtype: np.concatenate(parts) if parts else np.zeros(shape, dtype)  # noqa: E731
    return Soup(cat(verts, (0, 3), float), cat(tris, (0, 3), int), cat(mids, (0,), int),
                cat(sizes, (0,), int) if has_sizes else None, levels, len(dump["meshes"]) - len(render),
                tuple(m["name"] for m in render), cat(owner, (0,), int))


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


def assign_material_ids(dump: dict, table: dict) -> dict:
    """A copy of a dump whose material ids come from an object's materials table (jobs/<object>/materials.json,
    K01, user 2026-10-11): a mesh named in table["meshes"] takes that id; otherwise every triangle takes the id
    of its UDIM tile (`udim_tiles` of the dump; finishes as tiles, not slots); a tile the table does not name is
    0, unassigned. A source whose finishes are material slots (3ds Max sub-material ids) uses table["slots"]
    {slot: id} instead (an unlisted slot is 0), and table["glass_slots"] [slot, ...] moves the triangles of those
    slots into a mesh "<name>_glass" of id table["glass_id"] (0 when absent), so the extractor finds glass by
    mesh name. A mesh with neither tiles nor a slot table keeps its slot ids."""
    tiles = {int(f["udim"]): int(f["id"]) for f in table.get("finishes", {}).values()}
    by_mesh = {k: int(v) for k, v in table.get("meshes", {}).items()}
    slots = {int(k): int(v) for k, v in table["slots"].items()} if "slots" in table else None
    glass = {int(s) for s in table.get("glass_slots", [])}
    glass_id = int(table.get("glass_id", 0))
    meshes = []
    for mesh in dump["meshes"]:
        mesh = dict(mesh)
        src = mesh.get("material_ids") or [0] * len(mesh["triangles"])
        if glass and mesh["name"] not in by_mesh and any(s in glass for s in src):
            keep = [k for k, s in enumerate(src) if s not in glass]
            moved = [k for k, s in enumerate(src) if s in glass]
            meshes.append(_subset(mesh, moved, f"{mesh['name']}_glass", glass_id))
            mesh = _subset(mesh, keep, mesh["name"], None)
            src = [src[k] for k in keep]
            if not keep:
                continue
        if mesh["name"] in by_mesh:
            mesh["material_ids"] = [by_mesh[mesh["name"]]] * len(mesh["triangles"])
        elif slots is not None:
            mesh["material_ids"] = [slots.get(int(s), 0) for s in src]
        elif "udim_tiles" in mesh:
            mesh["material_ids"] = [tiles.get(int(t), 0) for t in mesh["udim_tiles"]]
        meshes.append(mesh)
    return {**dump, "meshes": meshes}


def _subset(mesh: dict, rows: list, name: str, mid) -> dict:
    """The triangles `rows` of a dumped mesh as a mesh of its own (vertices renumbered); mid: one id for all,
    or None to keep the per-triangle lists."""
    tris = [mesh["triangles"][k] for k in rows]
    used = sorted({i for tr in tris for i in tr})
    new = {old: k for k, old in enumerate(used)}
    out = {"name": name, "vertices": [mesh["vertices"][i] for i in used],
           "triangles": [[new[i] for i in tr] for tr in tris]}
    for key in ("material_ids", "udim_tiles"):
        if key in mesh:
            out[key] = [mesh[key][k] for k in rows]
    sizes = [int(k) for k in mesh.get("polygon_sizes", [])]
    if sizes and sum(max(k - 2, 0) for k in sizes) == len(mesh["triangles"]):
        # source polygons stay with their triangles, so n-gons are still checked (review 1 of #77); a polygon
        # split between the subsets cannot be kept, and then neither part claims polygon sizes
        poly = [p for p, k in enumerate(sizes) for _ in range(max(k - 2, 0))]
        taken = {}
        for k in rows:
            taken[poly[k]] = taken.get(poly[k], 0) + 1
        if all(n == sizes[p] - 2 for p, n in taken.items()):
            out["polygon_sizes"] = [sizes[p] for p in sorted(taken)]
    if mid is not None:
        out["material_ids"] = [mid] * len(tris)
    return out

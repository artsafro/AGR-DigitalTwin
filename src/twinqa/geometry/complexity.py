"""Check `complexity` of pattern primitive-first (user 2026-10-14), blocking, on the modules delivery (a scene of
groups, type meshes and the objects that place them):

- triangles per group against the job's budget (and the total against the NPM limit, 150 000 per FBX); a group
  with no budget fails, as does a decor type that does not report its section metrics;
- a decor element keeps at most `decor_section_points_max` section points (12; storey band frames are measured
  by their contour and are exempt);
- copies are instances: two type meshes of the same geometry fail (they should be one type);
- a profiled element (more points than a box) must pass the silhouette test: its section stands off its box by
  more than `silhouette_dev_min_m`, else it should have been a box."""
from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np

from twinqa.geometry.checks import result

FRAME_GROUPS = ("storey_bands",)


def geometry_key(mesh: dict) -> str:
    """A type's key: its faces - each polygon (or triangle) as the loop of its vertices to the mm (from its least
    vertex, winding kept), relative to the mesh's bbox low corner, with its id. Two meshes with the same key are the same element; a quad split along the
    other diagonal is the same face (review 1 of #106: a vertex set alone made a cap at one end the twin of a cap
    at the other)."""
    v = np.asarray(mesh["vertices"], float)
    if not len(v):
        return hashlib.sha1(b"").hexdigest()
    r = np.round(v - v.min(axis=0), 3)
    mids = mesh.get("material_ids", [])
    def face(ids):                      # the loop from its least vertex, its order kept: the winding (the normal)
        pts = [tuple(r[i]) for i in ids]   # is part of the face (review 2 of #106)
        k = pts.index(min(pts))
        return tuple(pts[k:] + pts[:k])
    if mesh.get("polygons"):
        faces, k = [], 0
        for poly, size in zip(mesh["polygons"], mesh["polygon_sizes"]):
            faces.append((face(poly), int(mids[k]) if k < len(mids) else -1))
            k += size - 2
    else:
        faces = [(face(t), int(m)) for t, m in zip(mesh["triangles"], mids)]
    return hashlib.sha1(repr(sorted(faces)).encode()).hexdigest()


def _hash(mesh: dict) -> str:
    return geometry_key(mesh)


def check_complexity(scene: dict, tol: dict) -> dict:
    """tol: the `complexity` block - budget {group: triangles}, total_max, decor_groups, decor_section_points_max,
    silhouette_dev_min_m."""
    meshes, objects = scene["meshes"], scene["objects"]
    tris = defaultdict(int)
    for ob in objects:
        tris[ob["group"]] += len(meshes[ob["mesh"]]["triangles"])
    total = sum(tris.values())
    over = {g: [n, tol["budget"][g]] for g, n in tris.items() if g in tol["budget"] and n > tol["budget"][g]}
    unbudgeted = sorted(g for g in tris if g not in tol["budget"])
    decor = set(tol["decor_groups"])
    too_many, not_silhouette, missing = [], [], []
    for name, m in meshes.items():
        group = next((ob["group"] for ob in objects if ob["mesh"] == name), None)
        if group not in decor or group in FRAME_GROUPS:
            continue
        meta = m.get("meta", {})
        pts, dev = meta.get("section_points"), meta.get("silhouette_dev_m")
        if pts is None or (pts > 4 and dev is None):  # a metric not reported is no pass (review 1 of #106)
            missing.append(name)
            continue
        if pts > tol["decor_section_points_max"]:
            too_many.append([name, pts])
        if pts > 4 and dev <= tol["silhouette_dev_min_m"]:
            not_silhouette.append([name, dev])
    by_hash = defaultdict(list)
    for name, m in meshes.items():
        group = next((ob["group"] for ob in objects if ob["mesh"] == name), None)
        if group in decor:
            by_hash[_hash(m)].append(name)
    not_instanced = [names for names in by_hash.values() if len(names) > 1]
    count = defaultdict(int)
    for ob in objects:
        count[ob["mesh"]] += 1
    types = {g: len({ob["mesh"] for ob in objects if ob["group"] == g}) for g in decor}
    elements = {g: sum(1 for ob in objects if ob["group"] == g) for g in decor}
    ok = (total <= tol["total_max"] and not over and not unbudgeted and not missing and not too_many
          and not not_instanced and not not_silhouette)
    return result("complexity", ok, total, tol["total_max"],
                  {"triangles_by_group": dict(tris), "over_budget": over, "unbudgeted_groups": unbudgeted, "metrics_missing": missing[:20],
                   "elements_by_group": elements, "types_by_group": types,
                   "section_points_over": too_many[:20], "copies_not_instanced": not_instanced[:20],
                   "profile_without_silhouette": not_silhouette[:20]})

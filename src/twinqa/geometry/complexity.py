"""Check `complexity` of pattern primitive-first (user 2026-10-14), blocking, on the modules delivery (a scene of
groups, type meshes and the objects that place them):

- triangles per group against the job's budget (and the total against the NPM limit, 150 000 per FBX);
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


def geometry_key(vertices, material_ids) -> str:
    """A type's key: its vertex set to the mm, relative to its bbox low corner, and the ids of its triangles (so a
    capped element is not its uncapped twin). Two meshes with the same key are the same element (a different diagonal
    of a quad is no other element)."""
    v = np.asarray(vertices, float)
    v = np.round(v - v.min(axis=0), 3) if len(v) else v
    key = np.unique(v, axis=0).tobytes() + np.sort(np.asarray(material_ids, int)).tobytes()
    return hashlib.sha1(key).hexdigest()


def _hash(mesh: dict) -> str:
    return geometry_key(mesh["vertices"], mesh.get("material_ids", []))


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
    too_many, not_silhouette = [], []
    for name, m in meshes.items():
        group = next((ob["group"] for ob in objects if ob["mesh"] == name), None)
        if group not in decor or group in FRAME_GROUPS:
            continue
        meta = m.get("meta", {})
        pts = meta.get("section_points")
        if pts is not None and pts > tol["decor_section_points_max"]:
            too_many.append([name, pts])
        if pts is not None and pts > 4 and meta.get("silhouette_dev_m", 1.0) <= tol["silhouette_dev_min_m"]:
            not_silhouette.append([name, meta.get("silhouette_dev_m")])
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
    ok = (total <= tol["total_max"] and not over and not too_many and not not_instanced and not not_silhouette)
    return result("complexity", ok, total, tol["total_max"],
                  {"triangles_by_group": dict(tris), "over_budget": over, "unbudgeted_groups": unbudgeted,
                   "elements_by_group": elements, "types_by_group": types,
                   "section_points_over": too_many[:20], "copies_not_instanced": not_instanced[:20],
                   "profile_without_silhouette": not_silhouette[:20]})

# Ported from AGR adapters/sketchup/check_model_clearance.py (sha256 ba09d4967981)
# on 2026-10-06; changes: importable function + CLI wrapper, tolerance from the profile
# (geometry.near_coplanar_spacing_m.min), AGR window/ac/sill categories dropped.
"""Near-parallel face overlap check (reg p.8, 29: 5 mm-2 cm spacing; docs/domain/validation.md).

Finds pairs of almost parallel faces (|cos| > 0.999999), in either orientation, whose planes
are closer than the tolerance and whose projections overlap by more than 1e-7 m2. It is an
independent area test, not a pass of any third-party checker; hits still need classifying
(deliberate embeds vs defects, docs/domain/validation.md "General QA procedure").
"""
import numpy as np
from shapely.geometry import Polygon

PARALLEL_COS_MIN = 0.999999
AREA_MIN_M2 = 1e-7


def _normal(points: np.ndarray) -> np.ndarray:
    # Whole-polygon area vector: robust to collinear leading vertices on welded borders.
    q = points - points.mean(0)
    n = np.cross(q, np.roll(q, -1, axis=0)).sum(0)
    length = np.linalg.norm(n)
    return n / length if length > 1e-12 else np.zeros(3)


def near_parallel_overlaps(faces: list[dict], tolerance_m: float) -> list[dict]:
    """faces: [{object, index, points: [[x,y,z], ...]}] -> overlapping pairs closer than tolerance."""
    pts = [np.asarray(f["points"], dtype=float) for f in faces]
    if not pts:
        return []
    normals = np.array([_normal(p) for p in pts])
    centers = np.array([p.mean(0) for p in pts])
    lows, highs = np.array([p.min(0) for p in pts]), np.array([p.max(0) for p in pts])
    pairs = []
    for i, face in enumerate(faces):
        n = normals[i]
        if np.linalg.norm(n) < 0.9:
            continue
        dot = normals @ n
        cand = np.where((np.abs(dot) > PARALLEL_COS_MIN) & (np.abs((centers - pts[i][0]) @ n) < tolerance_m + 1e-5))[0]
        axes = [k for k in range(3) if k != int(np.argmax(np.abs(n)))]  # project on the dominant plane
        cand = cand[np.all(np.minimum(highs[cand][:, axes], highs[i, axes]) > np.maximum(lows[cand][:, axes], lows[i, axes]), axis=1)]
        a = Polygon(pts[i][:, axes])
        for j in cand:
            if j <= i:
                continue
            area = a.intersection(Polygon(pts[j][:, axes])).area
            if area < AREA_MIN_M2:
                continue
            dist = abs(float((centers[j] - pts[i][0]) @ n))
            if dist >= tolerance_m - 1e-7:
                continue
            pairs.append({"a": [face["object"], face["index"]], "b": [faces[j]["object"], faces[j]["index"]],
                          "distance_m": dist, "same_direction": bool(dot[j] > 0), "projected_area_m2": float(area)})
    return pairs


def summary(pairs: list[dict], tolerance_m: float, face_count: int) -> dict:
    objects = {}
    for p in pairs:
        key = " / ".join(sorted({p["a"][0], p["b"][0]}))
        objects[key] = objects.get(key, 0) + 1
    return {"tool": "near-parallel area-overlap test", "tolerance_m": tolerance_m,
            "parallel_cosine_min": PARALLEL_COS_MIN, "area_threshold_m2": AREA_MIN_M2, "face_count": face_count,
            "pair_count": len(pairs), "by_objects": objects,
            "same_direction": sum(p["same_direction"] for p in pairs),
            "opposite_direction": sum(not p["same_direction"] for p in pairs)}

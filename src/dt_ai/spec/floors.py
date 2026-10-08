"""Floor classification of the spec (HARNESS_PLAN §4, issue #8).

Pattern: typical-floor-repeat (docs/domain/patterns/INDEX.md) — this module writes what it reads.

A floor is typical of the floor below when they have the same storey height, the same level
contour and the same openings (relative to their own level). A run of such floors is written
once: the first floor in full, the rest as one entry {"level": <second>, "typical_of": <first>,
"repeat_to": <last>}. Every floor of a run must match both its neighbour and the run's first
floor within SAME_M, so small differences cannot add up along a long run. Contours are matched
vertex by vertex (any start point), radii travel with their vertices and opening wall indices are
mapped through the match; anything unclear keeps the floor unique (no false repeat).
Unique floors (often the bottom one or two and the top one) stay in full.
"""
import numpy as np

SAME_M = 0.01   # contours, openings and storey heights equal within 1 cm
FIELDS = ("x_m", "sill_m", "w_m", "h_m", "depth_m")
META = ("source", "material_id", "window_type", "plane_conflict")


def _shift(a, b):
    """Shift s with b[(i + s) % n] matching a[i] within SAME_M (same radii), or None."""
    if len(a) != len(b):
        return None
    pa, pb = np.array([p[:2] for p in a], float), np.array([p[:2] for p in b], float)
    ra = [p[2]["r"] if len(p) == 3 else 0.0 for p in a]
    rb = [p[2]["r"] if len(p) == 3 else 0.0 for p in b]
    n = len(a)
    for s in range(n):
        idx = [(i + s) % n for i in range(n)]
        if (np.linalg.norm(pa - pb[idx], axis=1).max() <= SAME_M
                and all(abs(ra[i] - rb[j]) <= SAME_M for i, j in enumerate(idx))):
            return s
    return None


def _same_openings(a, b, shift, n):
    """Same opening multiset: every opening of b, its wall mapped into a's numbering, has a
    partner in a with equal metadata and fields within SAME_M (order does not matter)."""
    if len(a) != len(b):
        return False
    free = list(range(len(a)))
    for y in b:
        wall = (y["wall"] - shift) % n
        hit = next((i for i in free if a[i]["wall"] == wall
                    and all(a[i].get(k, False if k == "plane_conflict" else None) ==
                            y.get(k, False if k == "plane_conflict" else None) for k in META)
                    and all(abs(a[i][k] - y[k]) <= SAME_M for k in FIELDS)), None)
        if hit is None:
            return False
        free.remove(hit)
    return True


def same_floor(lower, upper, lower_h, upper_h):
    """True when `upper` repeats `lower`: storey height, contour and openings within 1 cm."""
    if abs(lower_h - upper_h) > SAME_M:
        return False
    s = _shift(lower["contour"], upper["contour"])
    return s is not None and _same_openings(lower["openings"], upper["openings"], s, len(lower["contour"]))


def collapse(levels, floors):
    """Write runs of typical floors once. Returns (floors for the spec, classification report)."""
    heights = [levels[i + 1]["elev_m"] - levels[i]["elev_m"] for i in range(len(floors))]
    runs, start = [], 0
    for i in range(1, len(floors) + 1):
        if (i == len(floors) or not same_floor(floors[i - 1], floors[i], heights[i - 1], heights[i])
                or not same_floor(floors[start], floors[i], heights[start], heights[i])):
            runs.append((start, i - 1))
            start = i
    out, classes = [], []
    for s, e in runs:
        out.append(floors[s])
        if e > s:
            out.append({"level": floors[s + 1]["level"], "typical_of": floors[s]["level"],
                        "repeat_to": floors[e]["level"]})
            classes.append({"levels": [f["level"] for f in floors[s:e + 1]], "class": "typical",
                            "template": floors[s]["level"]})
        else:
            classes.append({"levels": [floors[s]["level"]], "class": "unique"})
    return out, classes


def expand(spec_floors, level_names):
    """Full per-floor data again from a spec's floors (typical entries copied from their template)."""
    by_level = {f["level"]: f for f in spec_floors if f.get("contour") is not None}
    out = []
    for f in spec_floors:
        if f.get("contour") is not None:
            out.append(f)
            continue
        first, last = level_names.index(f["level"]), level_names.index(f.get("repeat_to") or f["level"])
        template = by_level[f["typical_of"]]
        out.extend({**template, "level": level_names[i]} for i in range(first, last + 1))
    return out

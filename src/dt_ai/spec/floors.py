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
META = ("source", "material_id", "window_type", "plane_conflict", "kind", "panes", "level_from", "level_to")


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


def _fits(x, y, wall):
    return (x["wall"] == wall
            and all(x.get(k, False if k == "plane_conflict" else None) ==
                    y.get(k, False if k == "plane_conflict" else None) for k in META)
            and all(abs(x[k] - y[k]) <= SAME_M for k in FIELDS))


def _same_openings(a, b, shift, n):
    """Same opening multiset: a complete one-to-one matching (augmenting paths) where every
    opening of b, its wall mapped into a's numbering, has a partner in a with equal metadata and
    fields within SAME_M. Order does not matter; a wall outside the contour never matches."""
    if len(a) != len(b) or any(not 0 <= o["wall"] < n for o in list(a) + list(b)):
        return False
    edges = [[i for i, x in enumerate(a) if _fits(x, y, (y["wall"] - shift) % n)] for y in b]
    owner = {}                                      # opening of a -> opening of b
    for j in range(len(b)):                         # breadth-first augmenting path, no recursion
        came, queue, free = {}, [j], None
        seen = set()
        while queue and free is None:
            nxt = []
            for y in queue:
                for i in edges[y]:
                    if i in seen:
                        continue
                    seen.add(i)
                    came[i] = y
                    if i not in owner:
                        free = i
                        break
                    nxt.append(owner[i])
                if free is not None:
                    break
            queue = nxt
        if free is None:
            return False
        i = free
        while True:                                 # flip the path back to j
            y = came[i]
            prev = next((k for k, v in owner.items() if v == y), None)
            owner[i] = y
            if y == j:
                break
            i = prev
    return True


def _reversed(floor):
    """The same floor with its contour in the other direction: wall k becomes n - 2 - k and an
    opening's x is measured from the other end of its wall."""
    pts = floor["contour"]
    n = len(pts)
    rev = list(reversed(pts))
    out = []
    for o in floor["openings"]:
        k = o["wall"]
        if not 0 <= k < n:
            return None
        a, b = np.array(pts[k][:2], float), np.array(pts[(k + 1) % n][:2], float)
        length = float(np.linalg.norm(b - a))
        out.append({**o, "wall": (n - 2 - k) % n, "x_m": length - o["x_m"] - o["w_m"]})
    return {**floor, "contour": rev, "openings": out}


def same_floor(lower, upper, lower_h, upper_h):
    """True when `upper` repeats `lower`: storey height, contour and openings within 1 cm."""
    if abs(lower_h - upper_h) > SAME_M:
        return False
    n = len(lower["contour"])
    for candidate in (upper, _reversed(upper)):          # the same ring in either direction
        if candidate is None:
            continue
        s = _shift(lower["contour"], candidate["contour"])
        if s is not None and _same_openings(lower["openings"], candidate["openings"], s, n):
            return True
    return False


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

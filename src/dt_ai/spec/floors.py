"""Floor classification of the spec (HARNESS_PLAN §4, issue #8).

Pattern: typical-floor-repeat (docs/domain/patterns/INDEX.md) — this module writes what it reads.

A floor is typical of the floor below when they have the same storey height, the same level
contour and the same openings (relative to their own level). A run of such floors is written
once: the first floor in full, the rest as one entry {"level": <second>, "typical_of": <first>,
"repeat_to": <last>}. Unique floors (often the bottom one or two and the top one) stay in full.
Comparison only between neighbours: a floor equal to one further down but not to the one below
starts nothing.
"""
from shapely.geometry import Polygon

SAME_M = 0.01   # contours, openings and storey heights equal within 1 cm


def _ring(contour):
    return Polygon([p[:2] for p in contour])


def _same_contour(a, b):
    if len(a) != len(b):
        return False
    ra = [p[2]["r"] if len(p) == 3 else 0.0 for p in a]
    rb = [p[2]["r"] if len(p) == 3 else 0.0 for p in b]
    if any(abs(x - y) > SAME_M for x, y in zip(ra, rb)):
        return False
    return _ring(a).hausdorff_distance(_ring(b)) <= SAME_M


def _key(o):
    return (o["wall"], o["x_m"], o["sill_m"])


def _same_openings(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(sorted(a, key=_key), sorted(b, key=_key)):
        if (x["wall"], x.get("source"), x.get("material_id"), x.get("window_type")) != \
                (y["wall"], y.get("source"), y.get("material_id"), y.get("window_type")):
            return False
        if any(abs(x[k] - y[k]) > SAME_M for k in ("x_m", "sill_m", "w_m", "h_m", "depth_m")):
            return False
    return True


def same_floor(lower, upper, lower_h, upper_h):
    """True when `upper` repeats `lower`: storey height, contour and openings within 1 cm."""
    return (abs(lower_h - upper_h) <= SAME_M and _same_contour(lower["contour"], upper["contour"])
            and _same_openings(lower["openings"], upper["openings"]))


def collapse(levels, floors):
    """Write runs of typical floors once. Returns (floors for the spec, classification report)."""
    heights = [levels[i + 1]["elev_m"] - levels[i]["elev_m"] for i in range(len(floors))]
    runs, start = [], 0
    for i in range(1, len(floors) + 1):
        if i == len(floors) or not same_floor(floors[i - 1], floors[i], heights[i - 1], heights[i]):
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


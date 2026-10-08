"""Compare two specs of one object in the object system (issue #11, HARNESS_PLAN §4).

Pattern: none — benchmark check code (REVIEW_CHECKLIST Q1: new-case).

Every threshold comes from the benchmark's tolerances.json; nothing is hard-coded here. Each row
gives both measured values, the difference, the threshold and whether it is within. Which side is
the reference for a quantity, and whether a match / no-match verdict is given at all, are also
read from tolerances.json (user decision 2026-10-08: no Rhino verdict until Revit walls come from
location lines, #29). Regions where the contours differ are listed with their side, area, bounds
and how far each reaches out of the other contour, so a cause can be named for each. Measured
values are compared raw and rounded only for display (PR #32 review 1).
"""
import numpy as np
import shapely
from shapely.geometry import Polygon

from dt_ai.spec.model import Spec

DIFF_MIN_M2 = 1e-6       # contour difference regions below this are floating-point slivers, not geometry
REACH_STEP_M = 0.005     # a region's boundary is sampled this densely to measure how far it reaches


class CompareError(ValueError):
    pass


def _ring(contour):
    return [(float(p[0]), float(p[1])) for p in contour]


def _opening_boxes(floor, z0):
    """3D bounds (min xyz, max xyz) of each opening in the object system: along its contour wall
    from x_m over w_m, inward by depth_m (left of a CCW contour, right of a CW one), sill to top."""
    pts = np.array(_ring(floor.contour))
    side = 1.0 if Polygon(pts).exterior.is_ccw else -1.0
    out = []
    for o in floor.openings:
        a, b = pts[o.wall], pts[(o.wall + 1) % len(pts)]
        u = (b - a) / np.linalg.norm(b - a)
        inward = side * np.array([-u[1], u[0]]) * o.depth_m
        p0, p1 = a + u * o.x_m, a + u * (o.x_m + o.w_m)
        xy = np.array([p0, p1, p0 + inward, p1 + inward])
        out.append((np.array([*xy.min(axis=0), z0 + o.sill_m]), np.array([*xy.max(axis=0), z0 + o.sill_m + o.h_m])))
    return out


def _box_diff(p, q):
    """Largest corner shift between two boxes."""
    return float(max(np.abs(p[0] - q[0]).max(), np.abs(p[1] - q[1]).max()))


def _match(boxes_a, boxes_b, tol):
    """Largest set of pairs whose box difference is within tol (augmenting paths), so a valid
    correspondence is never missed by a greedy order (PR #32 review 1). Returns {i: j}."""
    ok = [[j for j, q in enumerate(boxes_b) if _box_diff(p, q) <= tol] for p in boxes_a]
    owner = {}

    def augment(i, seen):
        for j in ok[i]:
            if j not in seen:
                seen.add(j)
                if j not in owner or augment(owner[j], seen):
                    owner[j] = i
                    return True
        return False

    for i in range(len(boxes_a)):
        augment(i, set())
    return {i: j for j, i in owner.items()}


def _shown(x, nd):
    return round(x, nd) + 0.0 if isinstance(x, float) else x


def _row(name, a, b, threshold, kind, reference=None, level=None):
    """One criterion; within is decided on the raw values, the row shows them rounded."""
    if kind == "equal":
        delta, within = (b - a if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None), a == b
    elif kind == "rel":
        delta = abs(b - a) / abs(a) if a else None
        within = delta is not None and delta <= threshold
    else:                                        # "abs": |b - a|, or a distance given as b with a None
        delta = abs(b - a) if a is not None else b
        within = delta is not None and delta <= threshold
    r = {"criterion": name, "a": _shown(a, 3), "b": _shown(b, 3), "delta": _shown(delta, 4),
         "threshold": threshold, "within": bool(within)}
    if level is not None:
        r["level"] = level
    if reference is not None:
        r["reference"] = reference
    return r


def compare_specs(spec_a, spec_b, report_a, report_b, tolerances, names=("a", "b")):
    """Rows per criterion, contour difference regions and the verdict (or why there is none)."""
    t = tolerances["spec_compare"]
    ref = tolerances.get("reference", {})
    sa, sb = Spec.model_validate(spec_a), Spec.model_validate(spec_b)
    if sa.id != sb.id:
        raise CompareError(f"different objects: {sa.id} vs {sb.id}")
    rows, regions = [], []
    rows.append(_row("level count", len(sa.levels), len(sb.levels), None, "equal", ref.get("levels")))
    out = {"sides": dict(zip(("a", "b"), names)), "rows": rows, "contour_differences": regions}
    verdict = tolerances.get("verdict", {})
    if len(sa.levels) != len(sb.levels):        # HARNESS_PLAN §4: the other criteria are not counted
        out["failing"] = ["level count"]
        out["verdict"] = "no match" if verdict.get("enabled") else "deferred"
        if not verdict.get("enabled"):
            out["verdict_note"] = verdict.get("reason", "")
        return out
    for la, lb in zip(sa.levels, sb.levels):
        rows.append(_row("level elevation, m", la.elev_m, lb.elev_m, t["level_elev_m"], "abs", ref.get("levels"), la.name))
    ra, rb = report_a.get("roof", {}), report_b.get("roof", {})
    if "plane_m" in ra and "plane_m" in rb:
        rows.append(_row("roof covering, measured, m", ra["plane_m"], rb["plane_m"], t["level_elev_m"], "abs", ref.get("roof")))
    if "parapet_top_m" in ra and "parapet_top_m" in rb:
        rows.append(_row("parapet top, m", ra["parapet_top_m"], rb["parapet_top_m"], t["level_elev_m"], "abs", ref.get("parapet")))
    if sa.roof and sb.roof:
        rows.append(_row("parapet height, m", sa.roof.parapet_h_m, sb.roof.parapet_h_m, t["level_elev_m"], "abs", ref.get("parapet")))
    elev_a = {lv.name: lv.elev_m for lv in sa.levels}
    elev_b = {lv.name: lv.elev_m for lv in sb.levels}
    floors_a, floors_b = sa.expanded_floors(), sb.expanded_floors()
    names_a, names_b = [f.level for f in floors_a], [f.level for f in floors_b]
    rows.append(_row("floors", names_a, names_b, None, "equal", ref.get("levels")))
    if names_a != names_b:                       # a floor missing on one side is never skipped silently
        rows[-1]["delta"] = sorted(set(names_a) ^ set(names_b))
    by_level_b = {f.level: f for f in floors_b}
    for fa in floors_a:
        fb = by_level_b.get(fa.level)
        if fb is None:
            continue                             # the floors row already fails
        pa, pb = Polygon(_ring(fa.contour)), Polygon(_ring(fb.contour))
        lv, cref = fa.level, ref.get("contours")
        rows.append(_row("contour area, m2 (relative)", pa.area, pb.area, t["contour_area_rel"], "rel", cref, lv))
        rows.append(_row("contour Hausdorff, m", None, pa.hausdorff_distance(pb), t["contour_hausdorff_m"], "abs", cref, lv))
        rows.append(_row("contour kinks", len(fa.contour), len(fb.contour), None, "equal", cref, lv))
        for side, diff, other in ((names[0] + " only", pa.difference(pb), pb), (names[1] + " only", pb.difference(pa), pa)):
            for g in shapely.get_parts(diff):
                if g.area >= DIFF_MIN_M2:        # every region, however small (PR #32 review 1)
                    edge = shapely.segmentize(g.exterior, REACH_STEP_M)       # corners alone sit on the other contour
                    reach = max(other.exterior.distance(shapely.Point(c)) for c in edge.coords)
                    regions.append({"level": lv, "side": side, "area_m2": round(g.area, 4),
                                    "reach_m": round(reach, 3), "bounds": [round(c, 3) for c in g.bounds]})
        rows.append(_row("opening count", len(fa.openings), len(fb.openings), None, "equal", ref.get("openings"), lv))
        ba, bb = _opening_boxes(fa, elev_a[lv]), _opening_boxes(fb, elev_b[lv])
        match = _match(ba, bb, t["opening_bbox_m"])
        worst = max((_box_diff(ba[i], bb[j]) for i, j in match.items()), default=0.0)
        r = _row("opening pairs within bbox tolerance, m (worst pair)", None, worst, t["opening_bbox_m"], "abs",
                 ref.get("openings"), lv)
        r["pairs"] = len(match)
        r["unpaired"] = {names[0]: len(ba) - len(match), names[1]: len(bb) - len(match)}
        r["within"] = len(match) == len(ba) == len(bb)       # two empty sets are a match
        rows.append(r)
    failing = sorted({(r["criterion"] + (f" {r['level']}" if "level" in r else "")) for r in rows if not r["within"]})
    out["failing"] = failing
    if verdict.get("enabled"):
        out["verdict"] = "match" if not failing else "no match"
    else:
        out["verdict"] = "deferred"
        out["verdict_note"] = verdict.get("reason", "")
    return out


def markdown(result):
    """The comparison as a Markdown table, one row per criterion."""
    a, b = result["sides"]["a"], result["sides"]["b"]
    lines = [f"Verdict: **{result['verdict']}**" + (f" — {result['verdict_note']}" if result.get("verdict_note") else ""), "",
             f"| Level | Criterion | {a} | {b} | Difference | Threshold | Within | Reference |",
             "|---|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        extra = f" ({r['pairs']} pairs, unpaired {r['unpaired']})" if "pairs" in r else ""
        lines.append(f"| {r.get('level', '')} | {r['criterion']}{extra} | {'' if r['a'] is None else r['a']} | "
                     f"{'' if r['b'] is None else r['b']} | {'' if r['delta'] is None else r['delta']} | "
                     f"{'equal' if r['threshold'] is None else r['threshold']} | {'yes' if r['within'] else 'no'} | "
                     f"{r.get('reference') or ''} |")
    if result["contour_differences"]:
        lines += ["", "| Level | Contour region | Area, m2 | Reach, m | Bounds (x0, y0, x1, y1) |", "|---|---|---|---|---|"]
        for g in result["contour_differences"]:
            lines.append(f"| {g['level']} | {g['side']} | {g['area_m2']} | {g['reach_m']} | {g['bounds']} |")
    return "\n".join(lines) + "\n"

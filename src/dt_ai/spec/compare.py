"""Compare two specs of one object in the object system (issue #11, HARNESS_PLAN §4).

Pattern: none — benchmark check code (REVIEW_CHECKLIST Q1: new-case).

Every threshold comes from the benchmark's tolerances.json; nothing is hard-coded here. Each row
gives both measured values, the difference, the threshold and whether it is within. Which side is
the reference for a quantity, and whether a match / no-match verdict is given at all, are also
read from tolerances.json (user decision 2026-10-08: no Rhino verdict until Revit walls come from
location lines, #29). Regions where the contours differ are listed with their side, area and
bounds, so a cause can be named for each.
"""
import numpy as np
import shapely
from shapely.geometry import Polygon

from dt_ai.spec.model import Spec

DIFF_MIN_M2 = 0.01       # contour difference regions smaller than this are not listed (numeric slivers)


class CompareError(ValueError):
    pass


def _ring(contour):
    return [(float(p[0]), float(p[1])) for p in contour]


def _opening_boxes(floor, z0):
    """3D bounds (min xyz, max xyz) of each opening: along its contour wall from x_m, sill to top."""
    pts = np.array(_ring(floor.contour))
    out = []
    for o in floor.openings:
        a, b = pts[o.wall], pts[(o.wall + 1) % len(pts)]
        u = (b - a) / np.linalg.norm(b - a)
        p0, p1 = a + u * o.x_m, a + u * (o.x_m + o.w_m)
        lo = [min(p0[0], p1[0]), min(p0[1], p1[1]), z0 + o.sill_m]
        hi = [max(p0[0], p1[0]), max(p0[1], p1[1]), z0 + o.sill_m + o.h_m]
        out.append((np.array(lo), np.array(hi)))
    return out


def _pair(boxes_a, boxes_b):
    """Greedy pairs by nearest box centre; the box difference of a pair is its largest corner shift."""
    cand = sorted((float(np.linalg.norm((la + ha) / 2 - (lb + hb) / 2)), i, j)
                  for i, (la, ha) in enumerate(boxes_a) for j, (lb, hb) in enumerate(boxes_b))
    used_a, used_b, pairs = set(), set(), []
    for _, i, j in cand:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        (la, ha), (lb, hb) = boxes_a[i], boxes_b[j]
        pairs.append((i, j, float(max(np.abs(la - lb).max(), np.abs(ha - hb).max()))))
    return pairs


def _row(name, a, b, threshold, kind, reference=None, level=None):
    if kind == "equal":
        delta, within = (None if a is None or b is None else b - a), a == b
    elif kind == "rel":
        delta = abs(b - a) / abs(a) if a else None
        within = delta is not None and delta <= threshold
    else:                                        # "abs": |b - a| or a distance given as b with a None
        delta = abs(b - a) if a is not None else b
        within = delta is not None and delta <= threshold
    r = {"criterion": name, "a": a, "b": b, "delta": None if delta is None else round(delta, 4),
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
    if len(sa.levels) != len(sb.levels):        # HARNESS_PLAN §4: the other criteria are not counted
        out["verdict"] = "no match" if tolerances.get("verdict", {}).get("enabled") else "deferred"
        out["failing"] = ["level count"]
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
    elev = {lv.name: lv.elev_m for lv in sa.levels}
    for fa, fb in zip(sa.expanded_floors(), sb.expanded_floors()):
        if fa.level != fb.level:
            raise CompareError(f"floors differ: {fa.level} vs {fb.level}")
        pa, pb = Polygon(_ring(fa.contour)), Polygon(_ring(fb.contour))
        lv, cref = fa.level, ref.get("contours")
        rows.append(_row("contour area, m2 (relative)", round(pa.area, 3), round(pb.area, 3), t["contour_area_rel"], "rel", cref, lv))
        rows.append(_row("contour Hausdorff, m", None, round(pa.hausdorff_distance(pb), 4), t["contour_hausdorff_m"], "abs", cref, lv))
        rows.append(_row("contour kinks", len(fa.contour), len(fb.contour), None, "equal", cref, lv))
        for side, diff in ((names[0] + " only", pa.difference(pb)), (names[1] + " only", pb.difference(pa))):
            for g in shapely.get_parts(diff):
                if g.area >= DIFF_MIN_M2:
                    regions.append({"level": lv, "side": side, "area_m2": round(g.area, 3),
                                    "bounds": [round(c, 3) for c in g.bounds]})
        rows.append(_row("opening count", len(fa.openings), len(fb.openings), None, "equal", ref.get("openings"), lv))
        ba, bb = _opening_boxes(fa, elev[lv]), _opening_boxes(fb, elev[lv])
        pairs = _pair(ba, bb)
        worst = max((d for _, _, d in pairs), default=None)
        far = sum(1 for _, _, d in pairs if d > t["opening_bbox_m"])
        r = _row("opening pair bbox, m (worst)", None, None if worst is None else round(worst, 4), t["opening_bbox_m"], "abs",
                 ref.get("openings"), lv)
        r["pairs"], r["pairs_outside"] = len(pairs), far
        r["unpaired"] = {names[0]: len(ba) - len(pairs), names[1]: len(bb) - len(pairs)}
        r["within"] = r["within"] and far == 0 and len(ba) == len(bb)
        rows.append(r)
    failing = sorted({(r["criterion"] + (f" {r['level']}" if "level" in r else "")) for r in rows if not r["within"]})
    out["failing"] = failing
    verdict = tolerances.get("verdict", {})
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
        extra = f" ({r['pairs']} pairs, {r['pairs_outside']} outside, unpaired {r['unpaired']})" if "pairs" in r else ""
        lines.append(f"| {r.get('level', '')} | {r['criterion']}{extra} | {'' if r['a'] is None else r['a']} | "
                     f"{'' if r['b'] is None else r['b']} | {'' if r['delta'] is None else r['delta']} | "
                     f"{'equal' if r['threshold'] is None else r['threshold']} | {'yes' if r['within'] else 'no'} | "
                     f"{r.get('reference') or ''} |")
    if result["contour_differences"]:
        lines += ["", "| Level | Contour region | Area, m2 | Bounds (x0, y0, x1, y1) |", "|---|---|---|---|"]
        for g in result["contour_differences"]:
            lines.append(f"| {g['level']} | {g['side']} | {g['area_m2']} | {g['bounds']} |")
    return "\n".join(lines) + "\n"

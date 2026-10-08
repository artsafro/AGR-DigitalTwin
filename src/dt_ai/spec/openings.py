"""Openings of the spec: a hole in the body or a glass pane at a wall (user decision 2026-10-08, #7).

Pattern: none — this is extractor code, not a building node (REVIEW_CHECKLIST Q1: new-case).

Holes are found in the horizontal sections themselves. Dangling ends of the section are paired
(mutually nearest, at most OPENING_MAX_M apart, not joined by a nearly direct path of the section
itself — no longer than the gap plus two reveals — which is a pier between two openings); from each end the chain is
followed back until it runs along the gap: that point is the mouth on the wall line, and the way
back from it (a reveal, a chamfer) gives the depth. Bridging the mouths closes the section for the
level contour (a door from the floor no longer opens the storey end). An opening must sit on a
contour wall and run along it; a break off the contour (an inner wall, a courtyard) or a break
whose mouth is not found is a question, never an invented facade opening. Glass panes (meshes
named *glass*) parallel to a contour wall project onto it. Faces with an opening material id
(group `opening` of standards/material_id_ranges.yaml, ADR 0001) are opening planes: they are
left out of the body, so the hole stays the anchor, and the plane gives the opening its
material id. window_type stays null until the window library (#4).
"""
from collections import defaultdict

import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, Polygon

SNAP_M = 1e-5            # section points closer than this are one point (real meshes left 1 um gaps at window jambs)
OPENING_MAX_M = 8.0      # widest gap in a wall that is bridged as an opening
REVEAL_PATH_MAX_M = 2.0  # longest way back from a dangling end to its mouth (reveal, chamfer)
ALONG_DEG = 10.0         # a chain runs along the gap within this angle
BRIDGE_DEG = 3.0         # the mouth-to-mouth bridge runs along the gap within this angle
MOUTH_KEY_M = 0.005      # bridges at different heights are one opening when each end moves under 5 mm
ON_WALL_M = 0.05         # an opening mouth lies within this of its contour wall line
PANE_JOIN_M = 0.25       # glass panes closer than this along a wall (mullions) are one opening ...
PANE_BAND_M = 0.05       # ... when their sills and heads agree within this
PANE_WALL_M = 1.0        # a pane further than this from its contour wall is not an opening
MATCH_M = 0.05           # hole and glass, or recess and opening, within 5 cm are one place


def _unit(v):
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def _graph(noded):
    adj = defaultdict(set)
    for g in shapely.get_parts(noded):
        c = [tuple(x) for x in np.asarray(g.coords)]
        for a, b in zip(c, c[1:]):
            if a != b:
                adj[a].add(b)
                adj[b].add(a)
    return adj


def _components(adj):
    comp, n = {}, 0
    for start in adj:
        if start in comp:
            continue
        stack = [start]
        while stack:
            x = stack.pop()
            if x not in comp:
                comp[x] = n
                stack.extend(adj[x])
        n += 1
    return comp


def _linked_within(adj, p, q, limit):
    """True when the section itself joins p to q by a path no longer than limit (a pier between
    two openings, not a gap across one)."""
    import heapq
    best, heap = {p: 0.0}, [(0.0, p)]
    while heap:
        d, x = heapq.heappop(heap)
        if x == q:
            return True
        if d > best.get(x, np.inf):
            continue
        for y in adj[x]:
            nd = d + float(np.hypot(y[0] - x[0], y[1] - x[1]))
            if nd <= limit and nd < best.get(y, np.inf):
                best[y] = nd
                heapq.heappush(heap, (nd, y))
    return False


def _mouth(adj, p, gap):
    """Follow the chain back from dangling end p until it runs along the gap direction: the mouth on
    the wall line and the depth of the way in (0 for a plain break). None if not found in reach."""
    path, prev, cur, length = [np.array(p)], None, p, 0.0
    cos = np.cos(np.radians(ALONG_DEG))
    while length <= REVEAL_PATH_MAX_M:
        nxt = [n for n in adj[cur] if n != prev]
        if len(nxt) != 1:
            return None
        prev, cur = cur, nxt[0]
        here = np.array(cur)
        step = path[-1] - here                          # points back towards the gap
        if float(_unit(step) @ gap) >= cos:            # the wall line, running towards the gap
            mouth = path[-1]
            depth = max(abs(float((q - mouth) @ np.array([-gap[1], gap[0]]))) for q in path)
            return mouth, depth
        length += float(np.linalg.norm(step))
        path.append(here)
    return None


def close_section(segments):
    """Polygonize a section, bridging wall breaks. Returns (outer polygon or None, mouths, unresolved):
    a mouth is (point, point, depth); unresolved breaks are (point, point) pairs left open."""
    if not segments:
        return None, [], []
    noded = shapely.unary_union(shapely.set_precision(MultiLineString(segments), SNAP_M))
    adj = _graph(noded)
    dangles = [p for p, n in adj.items() if len(n) == 1]
    mouths, unresolved = [], []
    if dangles:
        comp = _components(adj)
        pts = np.array(dangles)
        best = {}
        for i, p in enumerate(dangles):
            d = np.linalg.norm(pts - pts[i], axis=1)
            for j in np.argsort(d):
                if j == i or not 1e-6 < d[j] <= OPENING_MAX_M:
                    continue
                # a pier joins the two ends nearly directly (its width plus two reveals at most);
                # the way round the building is long and does not make a pier
                if comp[dangles[j]] != comp[p] or not _linked_within(adj, p, dangles[j], d[j] + 2 * REVEAL_PATH_MAX_M):
                    best[i] = int(j)
                    break
        cos = np.cos(np.radians(BRIDGE_DEG))
        for i, j in best.items():
            if i < j and best.get(j) == i:
                p, q = dangles[i], dangles[j]
                gap = _unit(np.array(q) - np.array(p))
                mp, mq = _mouth(adj, p, gap), _mouth(adj, q, -gap)
                if mp is None or mq is None or float(_unit(mq[0] - mp[0]) @ gap) < cos:
                    unresolved.append((np.array(p), np.array(q)))
                else:
                    mouths.append((mp[0], mq[0], max(mp[1], mq[1])))
    lines = list(shapely.get_parts(noded)) + [LineString([a, b]) for a, b, _ in mouths]
    polys = list(shapely.get_parts(shapely.polygonize(shapely.get_parts(shapely.unary_union(lines)))))
    if not polys:
        return None, mouths, unresolved
    biggest = max(shapely.get_parts(shapely.unary_union(polys)), key=lambda g: g.area)
    return Polygon(biggest.exterior), mouths, unresolved


def _wall_frame(contour_pts, xy, half_width=0.0):
    """Nearest contour wall to a point among the walls whose span holds it (with half_width of
    the element on each side): (wall index, start point, unit direction, length)."""
    pts = np.array([q[:2] for q in contour_pts], dtype=float)
    walls = []
    for w in range(len(pts)):
        a, b = pts[w], pts[(w + 1) % len(pts)]
        u, length = _unit(b - a), float(np.linalg.norm(b - a))
        s = float((np.asarray(xy) - a) @ u)
        fits = -MATCH_M <= s - half_width and s + half_width <= length + MATCH_M
        walls.append((not fits, LineString([a, b]).distance(shapely.Point(xy)), w, a, u, length))
    _, _, w, a, u, length = min(walls, key=lambda t: (t[0], t[1]))
    return w, a, u, length


def _stack(items, same):
    """Group per-height items into runs: same(group, item) decides identity; contiguous spans merge."""
    groups = []
    for it in items:
        for g in groups:
            if same(g, it):
                g["spans"].append(it["span"])
                g["depth"] = max(g["depth"], it.get("depth", 0.0))
                break
        else:
            groups.append({**it, "spans": [it["span"]], "depth": it.get("depth", 0.0)})
    out = []
    for g in groups:
        runs = []
        for a, b in sorted(g["spans"]):
            if runs and a - runs[-1][1] < 1e-6:
                runs[-1][1] = b
            else:
                runs.append([a, b])
        out.extend({**g, "z0": lo, "z1": hi} for lo, hi in runs)
    return out


def _hole_openings(mouth_spans, contour_pts, section):
    """Openings on contour walls, and questions for breaks off the contour or without a mouth."""
    def ends_close(g, it):
        return min(max(np.linalg.norm(g["p"] - it["p"]), np.linalg.norm(g["q"] - it["q"])),
                   max(np.linalg.norm(g["p"] - it["q"]), np.linalg.norm(g["q"] - it["p"]))) <= MOUTH_KEY_M

    mouths = [{"p": mp, "q": mq, "depth": d, "span": (a, b)} for a, b, ms, _ in mouth_spans for mp, mq, d in ms]
    breaks = [{"p": p, "q": q, "span": (a, b)} for a, b, _, us in mouth_spans for p, q in us]
    openings, off = [], []
    for g in _stack(mouths, ends_close):
        width = float(np.linalg.norm(g["p"] - g["q"]))
        w, origin, u, _ = _wall_frame(contour_pts, (g["p"] + g["q"]) / 2, width / 2)
        ring = section.exterior                         # the real wall line, rounded corners included
        on = all(ring.distance(shapely.Point(x)) <= ON_WALL_M for x in (g["p"], g["q"], (g["p"] + g["q"]) / 2))
        if not on:
            off.append({"kind": "wall-break-off-contour", "p": g["p"], "q": g["q"], "z0": g["z0"], "z1": g["z1"]})
            continue
        x0 = min(float((g["p"] - origin) @ u), float((g["q"] - origin) @ u))   # width = the mouth itself,
        openings.append({"wall": w, "x0": x0, "x1": x0 + width, "z0": g["z0"], "z1": g["z1"],  # also on an arc
                         "depth": g["depth"], "source": "hole"})
    for g in _stack(breaks, ends_close):
        off.append({"kind": "unresolved-break", "p": g["p"], "q": g["q"], "z0": g["z0"], "z1": g["z1"]})
    return openings, off


def vertical_parts(v, tris, parts):
    """Vertical parts as (points, unit plane normal in plan); horizontal ones only counted."""
    out, flat = [], 0
    for part in parts:
        pts = v[np.unique(tris[part])]
        normal = np.linalg.svd(pts - pts.mean(axis=0), full_matrices=False)[2][-1]
        if abs(normal[2]) > 0.5:
            flat += 1
        else:
            out.append((pts, _unit(normal[:2])))
    return out, flat


def _project(parts, levels, floors, polys, kind):
    """Project vertical parts parallel to a contour wall onto it: one item per part."""
    out, skipped = [], 0
    for pts, normal in parts:
        zc = float(pts[:, 2].mean())
        li = next((i for i in range(len(floors)) if levels[i]["elev_m"] <= zc < levels[i + 1]["elev_m"]), None)
        if li is None:
            skipped += 1
            continue
        centre = pts[:, :2].mean(axis=0)
        half = float(np.ptp(pts[:, :2], axis=0).max()) / 2
        w, origin, u, _ = _wall_frame(floors[li]["contour"], centre, half)
        wall_n = np.array([u[1], -u[0]])                         # outward for a CCW contour
        along = (pts[:, :2] - origin) @ u
        if (abs(float(normal @ wall_n)) < np.cos(np.radians(ALONG_DEG)) or float(np.ptp(along)) <= 1e-3
                or polys[li].exterior.distance(shapely.Point(centre)) > PANE_WALL_M):
            skipped += 1
            continue
        out.append({"level": li, "wall": w, "x0": float(along.min()), "x1": float(along.max()),
                    "z0": float(pts[:, 2].min()), "z1": float(pts[:, 2].max()),
                    "depth": max(0.0, -float((centre - origin) @ wall_n)), "source": kind, "parts": 1})
    return out, skipped


def _merge_panes(items):
    """Panes of one window: same wall, gap under PANE_JOIN_M, sills and heads within PANE_BAND_M."""
    merged = []
    for o in sorted(items, key=lambda o: (o["level"], o["wall"], o["x0"])):
        m = next((m for m in merged if m["level"] == o["level"] and m["wall"] == o["wall"]
                  and -MATCH_M <= o["x0"] - m["x1"] <= PANE_JOIN_M and abs(o["z0"] - m["z0"]) <= PANE_BAND_M
                  and abs(o["z1"] - m["z1"]) <= PANE_BAND_M), None)
        if m:
            m.update(x1=max(m["x1"], o["x1"]), z0=min(m["z0"], o["z0"]), z1=max(m["z1"], o["z1"]),
                     depth=max(m["depth"], o["depth"]), parts=m["parts"] + 1)
        else:
            merged.append(dict(o))
    return merged


def _overlap(a, b, tol=MATCH_M):
    return (a["wall"] == b["wall"] and a["x0"] < b["x1"] + tol and b["x0"] < a["x1"] + tol
            and a["z0"] < b["z1"] + tol and b["z0"] < a["z1"] + tol)


def assemble(levels, floors, polys, mouth_spans_by_level, panes, planes):
    """Openings per floor, the plan footprints that clear recess questions, break questions, report.
    planes: vertical opening-plane parts as (points, normal, material id or None when mixed)."""
    glass, glass_skipped = _project(panes, levels, floors, polys, "glass")
    glass = _merge_panes(glass)
    plane_items, planes_skipped = [], 0
    for pts, normal, mid in planes:
        items, skipped = _project([(pts, normal)], levels, floors, polys, "plane")
        plane_items.extend({**it, "material_id": mid} for it in items)
        planes_skipped += skipped
    per_floor, footprints, breaks = [], [], []
    for li, floor in enumerate(floors):
        holes, off = _hole_openings(mouth_spans_by_level[li], floor["contour"], polys[li])
        breaks.extend({**b, "level": li} for b in off)
        for g in [g for g in glass if g["level"] == li]:
            matches = [h for h in holes if _overlap(h, g)]
            for h in matches:
                h["source"], h["depth"] = "hole+glass", max(h["depth"], g["depth"])
            if not matches:
                holes.append(g)
        for h in holes:
            ids = {pl["material_id"] for pl in plane_items if pl["level"] == li and _overlap(h, pl)}
            if ids:                                  # two planes with different ids: no id is invented
                h["material_id"] = ids.pop() if len(ids) == 1 else None
                h["plane_conflict"] = len(ids) > 0
        elev = levels[li]["elev_m"]
        pts = np.array([q[:2] for q in floor["contour"]], dtype=float)
        items = []
        for o in sorted(holes, key=lambda o: (o["wall"], o["x0"])):
            items.append({"wall": o["wall"], "x_m": round(max(o["x0"], 0.0), 3), "sill_m": round(o["z0"] - elev, 3),
                          "w_m": round(o["x1"] - o["x0"], 3), "h_m": round(o["z1"] - o["z0"], 3),
                          "depth_m": round(o["depth"], 3), "window_type": None, "source": o["source"],
                          "material_id": o.get("material_id"), "plane_conflict": o.get("plane_conflict", False)})
            a = pts[o["wall"]]
            u = _unit(pts[(o["wall"] + 1) % len(pts)] - a)
            n = np.array([u[1], -u[0]])
            p0, p1 = a + u * o["x0"], a + u * o["x1"]
            out_, in_ = MATCH_M, o["depth"] + MATCH_M
            footprints.append({"level": li, "z0": o["z0"], "z1": o["z1"],
                               "geom": Polygon([p0 + n * out_, p1 + n * out_, p1 - n * in_, p0 - n * in_])})
        per_floor.append(items)
    report = {"glass_openings": len(glass), "glass_parts_skipped": glass_skipped,
              "opening_planes": len(plane_items), "opening_planes_skipped": planes_skipped,
              "opening_planes_mixed_ids": sum(1 for _, _, mid in planes if mid is None),
              "openings_with_conflicting_planes": sum(1 for f in per_floor for o in f if o.get("plane_conflict")),
              "breaks_off_contour": sum(b["kind"] == "wall-break-off-contour" for b in breaks),
              "unresolved_breaks": sum(b["kind"] == "unresolved-break" for b in breaks)}
    return per_floor, footprints, breaks, report


def is_opening_recess(piece, level, footprints):
    """A recess piece is an opening's reveal only when an opening footprint holds it in plan and
    covers its whole height (a taller recess with a short window stays a question)."""
    lo, hi = min(a for a, _ in piece["spans"]), max(b for _, b in piece["spans"])
    return any(f["level"] == level and f["z0"] <= lo + MATCH_M and hi - MATCH_M <= f["z1"]
               and f["geom"].buffer(MATCH_M).contains(piece["geom"]) for f in footprints)


def break_questions(breaks, levels):
    """Questions for wall breaks that are not facade openings."""
    out = []
    for b in breaks:
        mid = (b["p"] + b["q"]) / 2
        out.append({"priority": "high", "kind": b["kind"], "levels": [levels[b["level"]]["name"]], "wall": None,
                    "depth_m": None, "length_m": round(float(np.linalg.norm(b["p"] - b["q"])), 3),
                    "facade_share": None, "heights_m": [round(b["z0"], 3), round(b["z1"], 3)],
                    "at": [round(float(mid[0]), 2), round(float(mid[1]), 2)]})
    return out

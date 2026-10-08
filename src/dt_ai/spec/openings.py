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
material id. window_type stays null until the window library (#4). A door recess of the contour
(mesh._door_recesses, #31) is an opening of kind door; an opening with glass is a window with the
number of its panes (a curtain wall is one opening, the unit of the window library).
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
PANE_JOIN_M = 0.15       # glass panes of one frame (gap <= 0.15 m, user decision 2026-10-08, #31) are one opening ...
PANE_BAND_M = 0.05       # ... when aligned: side by side, one's heights within the other's; stacked, one's width within
DEPTH_EXCEPTION_M = 0.10  # a measured depth further than this from the spec default is written (#36)
GLASS_FRAME_M = 0.20     # glass fills an opening's height when no stretch without glass is longer (a frame member)
LEVEL_JOINT_M = 0.15     # an opening reaching less than this past a level line does not cross it (a frame joint)
# a door opening: from the storey floor, high and wide enough (user decisions 2026-10-08, #31;
# the same numbers as mesh.DOOR_*, for through holes)
DOOR_FLOOR_M = 0.05
DOOR_MIN_H_M = 1.9
DOOR_W_M = (0.7, 3.0)
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


def _within(a, b, axis):
    """One range inside the other along axis (x or z), within PANE_BAND_M."""
    lo, hi = axis + "0", axis + "1"
    return any(p[lo] >= q[lo] - PANE_BAND_M and p[hi] <= q[hi] + PANE_BAND_M for p, q in ((a, b), (b, a)))


def _covered(rects, box):
    """The panes (x0, x1, z0, z1) cover the box up to the joints of one frame (PANE_JOIN_M), so
    a merged rectangle never stands over solid wall (PR #20 F5, PR #33 review 1)."""
    h = PANE_JOIN_M / 2 + 1e-6
    union = shapely.unary_union([shapely.box(x0 - h, z0 - h, x1 + h, z1 + h) for x0, x1, z0, z1 in rects])
    return shapely.box(box[0], box[2], box[1], box[3]).difference(union).area < 1e-6


def _merge_panes(items):
    """Panes of one frame are one opening (user decision 2026-10-08, #31): panes on the same wall
    within PANE_JOIN_M of each other and aligned — side by side with one's heights inside the
    other's, or a transom with one's width inside the other's, within PANE_BAND_M. Two groups join
    only when their panes cover the joined rectangle, so staggered or L-shaped sets stay apart
    (PR #20 F5, PR #33 review 1). The opening counts its panes."""
    groups = [dict(o, rects=[(o["x0"], o["x1"], o["z0"], o["z1"])])
              for o in sorted(items, key=lambda o: (o["level"], o["wall"], o["x0"], o["z0"]))]
    merged = True
    while merged:
        merged = False
        for i, m in enumerate(groups):
            for j in range(i + 1, len(groups)):
                o = groups[j]
                gap_x = max(0.0, o["x0"] - m["x1"], m["x0"] - o["x1"])
                gap_z = max(0.0, o["z0"] - m["z1"], m["z0"] - o["z1"])
                if m["level"] != o["level"] or m["wall"] != o["wall"] or max(gap_x, gap_z) > PANE_JOIN_M + 1e-9:
                    continue
                if not ((gap_z == 0 and _within(o, m, "z")) or (gap_x == 0 and _within(o, m, "x"))):
                    continue
                box = (min(m["x0"], o["x0"]), max(m["x1"], o["x1"]), min(m["z0"], o["z0"]), max(m["z1"], o["z1"]))
                if not _covered(m["rects"] + o["rects"], box):
                    continue
                m.update(x0=box[0], x1=box[1], z0=box[2], z1=box[3], depth=max(m["depth"], o["depth"]),
                         parts=m["parts"] + o["parts"], rects=m["rects"] + o["rects"])
                del groups[j]
                merged = True
                break
            if merged:
                break
    return groups


def _overlap(a, b, tol=MATCH_M):
    return (a["wall"] == b["wall"] and a["x0"] < b["x1"] + tol and b["x0"] < a["x1"] + tol
            and a["z0"] < b["z1"] + tol and b["z0"] < a["z1"] + tol)


def _door_items(doors, li, contour):
    """Door recesses of one level as opening items on their contour wall."""
    out = []
    for d in doors:
        pts = np.array(d["geom"].exterior.coords)[:-1]
        w, a, u, _ = _wall_frame(contour, np.array(d["geom"].centroid.coords[0]))
        along = (pts - a) @ u
        n = np.array([u[1], -u[0]])
        out.append({"level": li, "wall": w, "x0": float(along.min()), "x1": float(along.max()), "z0": d["z0"],
                    "z1": d["z1"], "depth": max(0.0, float(-((pts - a) @ n).min())), "source": "hole", "door": True})
    return out


def _glass_fills(o):
    """Glass fills the opening's height: no stretch of it without glass longer than GLASS_FRAME_M."""
    top = o["z0"]
    for z0, z1 in sorted(o.get("glass_z", [])):
        if z0 - top > GLASS_FRAME_M:
            return False
        top = max(top, z1)
    return o["z1"] - top <= GLASS_FRAME_M


def _kind(o):
    """window when glass fills the height; door for a door recess without glass or with glass over
    part of its height (user decision 2026-10-08, #31)."""
    if o.get("glass_z") and _glass_fills(o):
        return "window"
    return "door" if o.get("door") else ("window" if o.get("glass_z") else None)


def _door_size(o, elev):
    """A through opening from the storey floor with a door's height and width."""
    return (o["z0"] - elev <= DOOR_FLOOR_M and o["z1"] - o["z0"] >= DOOR_MIN_H_M - 1e-6
            and DOOR_W_M[0] - 1e-6 <= o["x1"] - o["x0"] <= DOOR_W_M[1] + 1e-6)


def _join_material(a, b):
    """Material evidence of two parts of one opening: one id kept, two different ids or a conflict
    on either side give no id and plane_conflict (PR #33 review 2)."""
    ids = {o["material_id"] for o in (a, b) if o.get("material_id") is not None}
    if a.get("plane_conflict") or b.get("plane_conflict") or len(ids) > 1:
        a["material_id"], a["plane_conflict"] = None, True
    elif ids:
        a["material_id"] = ids.pop()


def _world(o, contour):
    pts = np.array([q[:2] for q in contour], dtype=float)
    a = pts[o["wall"]]
    u = _unit(pts[(o["wall"] + 1) % len(pts)] - a)
    return a + u * o["x0"], a + u * o["x1"], u


def _across_levels(by_level, levels, floors):
    """One record for an opening that crosses a level (user decision 2026-10-08, spec v0.2): an
    opening of the floor above on the same facade line and plan span, starting within PANE_JOIN_M
    above the top of one of the floor below (either may reach past the level), joins it when their
    rectangles are covered as one frame; the lower floor keeps it with level_to. Runs top down, so
    a chain over several levels ends in the lowest floor."""
    for li in range(len(by_level) - 2, -1, -1):
        elev = levels[li + 1]["elev_m"]
        for up in list(by_level[li + 1]):
            pb0, pb1, ub = _world(up, floors[li + 1]["contour"])
            for low in by_level[li]:
                pa0, pa1, ua = _world(low, floors[li]["contour"])
                n = np.array([ua[1], -ua[0]])
                if (abs(float(ua @ ub)) < np.cos(np.radians(ALONG_DEG))
                        or max(abs(float((q - pa0) @ n)) for q in (pb0, pb1)) > MATCH_M):
                    continue
                s0, s1 = sorted(float((q - pa0) @ ua) for q in (pb0, pb1))
                lower = {"x0": 0.0, "x1": float((pa1 - pa0) @ ua), "z0": low["z0"], "z1": low["z1"]}
                upper = {"x0": s0, "x1": s1, "z0": up["z0"], "z1": up["z1"]}
                if not (upper["z0"] - lower["z1"] <= PANE_JOIN_M + 1e-9 and lower["z0"] < elev < upper["z1"]
                        and _within(lower, upper, "x")):
                    continue
                box = (min(0.0, s0), max(lower["x1"], s1), lower["z0"], max(lower["z1"], upper["z1"]))
                rects = [(r["x0"], r["x1"], r["z0"], r["z1"]) for r in (lower, upper)]
                if not _covered(rects, box):
                    continue
                _join_material(low, up)
                low.update(x0=low["x0"] + box[0], x1=low["x0"] + box[1], z1=box[3], depth=max(low["depth"], up["depth"]),
                           parts=low.get("parts", 0) + up.get("parts", 0),
                           glass_z=low.get("glass_z", []) + up.get("glass_z", []),
                           glass_world=low.get("glass_world", []) + up.get("glass_world", []),
                           kind_fixed=low.get("kind_fixed") or up.get("kind_fixed"),
                           no_reveal=low.get("no_reveal") or up.get("no_reveal"),   # uncertainty of either part (PR #39 r2)
                           door=low.get("door") or up.get("door"), level_to=up.get("level_to", li + 1),
                           source=low["source"] if low["source"] == up["source"] else "hole+glass")
                by_level[li + 1].remove(up)
                break


def _owners(by_level, levels, floors):
    """Every opening belongs to the floor of its bottom and records the highest level it crosses,
    from its whole height: one pane through a level line is one record too (PR #33 review 2).
    A record moved down is re-measured on the lower floor's contour wall."""
    top_floor = len(floors) - 1
    for li in range(len(by_level)):
        for o in list(by_level[li]):
            owner = max([k for k in range(top_floor + 1) if levels[k]["elev_m"] <= o["z0"] + LEVEL_JOINT_M] or [0])
            last = max([k for k in range(top_floor + 1) if levels[k]["elev_m"] < o["z1"] - LEVEL_JOINT_M] or [0])
            if owner < li:
                p0, p1, _ = _world(o, floors[li]["contour"])
                w, a, u, _ = _wall_frame(floors[owner]["contour"], (p0 + p1) / 2, float(np.linalg.norm(p1 - p0)) / 2)
                x0, x1 = sorted(float((q - a) @ u) for q in (p0, p1))
                o.update(wall=w, x0=x0, x1=x1, level=owner)
                by_level[li].remove(o)
                by_level[owner].append(o)
            last = max(last, o.get("level_to", owner))
            if last > owner:
                o["level_to"] = last
            else:
                o.pop("level_to", None)


def _span_world(contour, wall, x0, x1):
    pts = np.array([q[:2] for q in contour], dtype=float)
    a = pts[wall]
    u = _unit(pts[(wall + 1) % len(pts)] - a)
    return a + u * x0, a + u * x1, u


def _inward(contour, u):
    """Unit normal of a contour wall pointing into the building."""
    side = 1.0 if Polygon([q[:2] for q in contour]).exterior.is_ccw else -1.0
    return side * np.array([-u[1], u[0]])


def _reveal(o, recesses, contour):
    """The rough opening around a glass group from the reveal of the body (spec v0.3, #36): the
    recess pieces of its level that touch the glass footprint, in the height run that overlaps the
    glass. Returns (x0, x1, z0, z1, depth) on the glass's wall, or None; whether the glass fills it
    up to a frame is checked for all glass of one reveal (_fills)."""
    p0, p1, u = _span_world(contour, o["wall"], o["x0"], o["x1"])
    n = _inward(contour, u)
    foot = Polygon([p0 - u * MATCH_M - n * MATCH_M, p1 + u * MATCH_M - n * MATCH_M,
                    p1 + u * MATCH_M + n * (o["depth"] + MATCH_M), p0 - u * MATCH_M + n * (o["depth"] + MATCH_M)])
    near = [r for r in recesses if r["geom"].intersects(foot) and r["geom"].intersection(foot).area > 1e-6]
    spans = sorted(((a, b, r) for r in near for a, b in r["spans"]), key=lambda t: (t[0], t[1]))
    runs = []
    for a, b, r in spans:
        if runs and a <= runs[-1]["z1"] + 1e-6:
            runs[-1]["z1"] = max(runs[-1]["z1"], b)
            runs[-1]["pieces"].append(r)
        else:
            runs.append({"z0": a, "z1": b, "pieces": [r]})
    run = next((r for r in runs if r["z0"] < o["z1"] and r["z1"] > o["z0"]), None)
    if run is None:
        return None
    pts = np.array([xy for r in run["pieces"] for g in shapely.get_parts(r["geom"]) for xy in g.exterior.coords])
    a, _, _ = _span_world(contour, o["wall"], 0.0, 0.0)
    along = (pts - a) @ u
    x0, x1 = float(along.min()), float(along.max())
    if x0 > o["x0"] + MATCH_M or x1 < o["x1"] - MATCH_M:
        return None                              # the recess does not hold the glass
    depth = float(max(((pts - a) @ n).max(), o["depth"]))
    return x0, x1, min(run["z0"], o["z0"]), max(run["z1"], o["z1"]), depth


def _fills(rough, rects):
    """Glass fills the reveal up to a frame: the rectangle of the reveal (x0, x1, z0, z1) is covered
    by the glass rectangles on its wall, each grown by GLASS_FRAME_M — jointly, not axis by axis, so an
    L-shaped set of panes never makes a rectangle over solid wall (PR #20 F5, PR #39 review 1), and a
    tall recess with a short window is no frame (F6). The glass may belong to any level (a frame
    through a level line)."""
    x0, x1, z0, z1 = rough[:4]
    g = GLASS_FRAME_M + 1e-6
    cover = shapely.unary_union([shapely.box(a - g, c - g, b_ + g, d + g) for a, b_, c, d in rects]) if rects else Polygon()
    return shapely.box(x0, z0, x1, z1).difference(cover).area < 1e-6


def _glass_on_wall(o, contour, glass):
    """Every glass rectangle on the wall line of o, from all glass groups, in o's wall frame."""
    a, _, u = _span_world(contour, o["wall"], 0.0, 1.0)
    n = _inward(contour, u)
    out = []
    for g in glass:
        for x0w, y0w, x1w, y1w, z0, z1 in g["glass_world"]:
            p0, p1 = np.array([x0w, y0w]), np.array([x1w, y1w])
            if max(abs(float((q - a) @ n)) for q in (p0, p1)) > PANE_WALL_M:
                continue
            t0, t1 = sorted(float((q - a) @ u) for q in (p0, p1))
            out.append((t0, t1, z0, z1))
    return out


def _source_items(items, li, contour):
    """Openings a source gives explicitly (Revit, #36): rough opening, kind, glass, on their wall."""
    out = []
    for d in items:
        q0, q1 = np.asarray(d["p0"], float), np.asarray(d["p1"], float)
        w, a, u, _ = _wall_frame(contour, (q0 + q1) / 2, float(np.linalg.norm(q1 - q0)) / 2)
        x0, x1 = sorted(float((q - a) @ u) for q in (q0, q1))
        out.append({"level": li, "wall": w, "x0": x0, "x1": x1, "z0": d["z0"], "z1": d["z1"], "depth": d["depth"],
                    "source": "hole+glass" if (d.get("glass") or d.get("glazed")) else "hole", "kind_fixed": d["kind"],
                    "glazed": bool(d.get("glazed")),
                    "parts": d.get("panes") or 0, "glass_world": [tuple(g) for g in d.get("glass", [])],
                    "glass_z": [(g[2], g[3]) for g in d.get("glass", [])], "door": d["kind"] == "door"})
    return out


def assemble(levels, floors, polys, mouth_spans_by_level, panes, planes, doors=None, recesses=None, sources=None,
             depth_default=0.2):
    """Openings per floor, the plan footprints that clear recess questions, break questions, report.
    planes: vertical opening-plane parts as (points, normal, material id or None when mixed);
    doors: door recesses per level (mesh._door_recesses); recesses: recess pieces per level (the
    reveals that give a glass opening its rough size, #36); sources: openings a source gives
    explicitly, per level (Revit)."""
    glass, glass_skipped = _project(panes, levels, floors, polys, "glass")
    glass = _merge_panes(glass)
    rough_from_reveal = 0
    for g in glass:
        g["glass_z"] = [(z0, z1) for _, _, z0, z1 in g["rects"]]
        contour = floors[g["level"]]["contour"]
        g["glass_world"] = [(*_span_world(contour, g["wall"], x0, x1)[0], *_span_world(contour, g["wall"], x0, x1)[1], z0, z1)
                            for x0, x1, z0, z1 in g["rects"]]
        g["rough"] = _reveal(g, (recesses or [[]] * len(floors))[g["level"]], contour)
    for g in glass:                              # a reveal counts only when glass fills it up to a frame
        if g.get("rough") is not None and not _fills(g["rough"], _glass_on_wall(g, floors[g["level"]]["contour"], glass)):
            g["rough"] = None
    glass = _join_same_reveal(glass)             # so only panes of an accepted reveal are joined (PR #39 review 1)
    for g in glass:                              # the opening is the hole with its frame, not the glass
        if g.get("rough") is not None:
            g["x0"], g["x1"], g["z0"], g["z1"], g["depth"] = g["rough"]
            rough_from_reveal += 1
        else:
            g["no_reveal"] = True                # size unknown: the glass stands in, and a question asks (#36)
    plane_items, planes_skipped = [], 0
    for pts, normal, mid in planes:
        items, skipped = _project([(pts, normal)], levels, floors, polys, "plane")
        plane_items.extend({**it, "material_id": mid} for it in items)
        planes_skipped += skipped
    by_level, breaks = [], []
    for li, floor in enumerate(floors):
        holes, off = _hole_openings(mouth_spans_by_level[li], floor["contour"], polys[li])
        for h in holes:                          # a through hole of a door's size is a door (#31)
            h["door"] = _door_size(h, levels[li]["elev_m"])
        for d in (_source_items((sources or [[]] * len(floors))[li], li, floor["contour"])
                  + _door_items((doors or [[]] * len(floors))[li], li, floor["contour"])):
            same = next((h for h in holes if d.get("door") and h.get("door") and _overlap(h, d)), None)
            if same is None:                     # a door family and its wall opening are one door (Revit, #29)
                holes.append(d)
            else:
                same.update(x0=min(same["x0"], d["x0"]), x1=max(same["x1"], d["x1"]), z0=min(same["z0"], d["z0"]),
                            z1=max(same["z1"], d["z1"]), depth=max(same["depth"], d["depth"]))
        breaks.extend({**b, "level": li} for b in off)
        for g in [g for g in glass if g["level"] == li]:
            matches = [h for h in holes if _overlap(h, g)]
            for h in matches:
                h["source"], h["depth"] = "hole+glass", max(h["depth"], g["depth"])
                h["parts"] = h.get("parts", 0) + g["parts"]
                h["glass_z"] = h.get("glass_z", []) + g["glass_z"]
                h["glass_world"] = h.get("glass_world", []) + g["glass_world"]
                if h.get("door"):                    # the frame's glass may reach past the recess
                    h["z0"], h["z1"] = min(h["z0"], g["z0"]), max(h["z1"], g["z1"])
            if not matches:
                holes.append(g)
        for h in holes:
            ids = {pl["material_id"] for pl in plane_items if pl["level"] == li and _overlap(h, pl)}
            if ids:                                  # two planes with different ids: no id is invented
                h["material_id"] = ids.pop() if len(ids) == 1 else None
                h["plane_conflict"] = len(ids) > 0
        by_level.append(holes)
    _across_levels(by_level, levels, floors)
    _owners(by_level, levels, floors)
    for li, holes in enumerate(by_level):        # a glass opening without a reveal: its size is a question
        for o in holes:
            if o.get("no_reveal"):
                p0, p1, _ = _world(o, floors[li]["contour"])
                breaks.append({"kind": "opening-size-unknown", "p": p0, "q": p1, "z0": o["z0"], "z1": o["z1"], "level": li})
    per_floor, footprints = [], []
    for li, (floor, holes) in enumerate(zip(floors, by_level)):
        elev = levels[li]["elev_m"]
        pts = np.array([q[:2] for q in floor["contour"]], dtype=float)
        items = []
        for o in sorted(holes, key=lambda o: (o["wall"], o["x0"])):
            item = {"wall": o["wall"], "x_m": round(max(o["x0"], 0.0), 3), "sill_m": round(o["z0"] - elev, 3),
                    "w_m": round(o["x1"] - o["x0"], 3), "h_m": round(o["z1"] - o["z0"], 3),
                    "window_type": None, "source": o["source"],
                    "material_id": o.get("material_id"), "plane_conflict": o.get("plane_conflict", False),
                    "kind": o.get("kind_fixed") or _kind(o),
                    "panes": (o.get("parts") or None) if (o.get("glass_z") or o.get("glazed")) else None,
                    **_glass_size(o, floor["contour"])}
            if not o.get("kind_fixed") and abs(o["depth"] - depth_default) > DEPTH_EXCEPTION_M:
                item["depth_m"] = round(o["depth"], 3)   # an exception to the default; a source gives none (#36)
            if "level_to" in o:
                item["level_from"], item["level_to"] = levels[li]["name"], levels[o["level_to"]]["name"]
            items.append(item)
            a = pts[o["wall"]]
            u = _unit(pts[(o["wall"] + 1) % len(pts)] - a)
            n = np.array([u[1], -u[0]])
            p0, p1 = a + u * o["x0"], a + u * o["x1"]
            out_, in_ = MATCH_M, o["depth"] + MATCH_M
            geom = Polygon([p0 + n * out_, p1 + n * out_, p1 - n * in_, p0 - n * in_])
            for lj in range(li, o.get("level_to", li) + 1):
                footprints.append({"level": lj, "z0": o["z0"], "z1": o["z1"], "geom": geom})
        per_floor.append(items)
    report = {"glass_openings": len(glass), "glass_parts_skipped": glass_skipped,
              "rough_from_reveal": rough_from_reveal,
              "openings_size_unknown": sum(1 for b in breaks if b["kind"] == "opening-size-unknown"),
              "source_openings": sum(len(x) for x in (sources or [])),
              "door_openings": sum(1 for f in per_floor for o in f if o["kind"] == "door"),
              "openings_across_levels": sum(1 for f in per_floor for o in f if o.get("level_to")),
              "opening_planes": len(plane_items), "opening_planes_skipped": planes_skipped,
              "opening_planes_mixed_ids": sum(1 for _, _, mid in planes if mid is None),
              "openings_with_conflicting_planes": sum(1 for f in per_floor for o in f if o.get("plane_conflict")),
              "breaks_off_contour": sum(b["kind"] == "wall-break-off-contour" for b in breaks),
              "unresolved_breaks": sum(b["kind"] == "unresolved-break" for b in breaks)}
    return per_floor, footprints, breaks, report


def _glass_size(o, contour):
    """glass_w / glass_h: the extent of the opening's glass along its wall and in height (#36)."""
    gw = o.get("glass_world")
    if not gw:
        return {}
    _, _, u = _span_world(contour, o["wall"], 0.0, 1.0)
    along = [float(np.dot(np.array(p[:2]), u)) for g in gw for p in ((g[0], g[1]), (g[2], g[3]))]
    w, h = max(along) - min(along), max(g[5] for g in gw) - min(g[4] for g in gw)
    return {"glass_w": round(w, 3), "glass_h": round(h, 3)} if w > 1e-3 and h > 1e-3 else {}


def _join_same_reveal(glass):
    """Glass groups in one reveal are one opening: the hole with its frame holds all its panes."""
    out = []
    for g in glass:
        r = g.get("rough")
        same = next((o for o in out if r is not None and o.get("rough") is not None and o["level"] == g["level"]
                     and o["wall"] == g["wall"] and all(abs(u - w) <= MATCH_M for u, w in zip(o["rough"][:4], r[:4]))), None)
        if same is None:
            out.append(g)
        else:
            same.update(x0=min(same["x0"], g["x0"]), x1=max(same["x1"], g["x1"]), z0=min(same["z0"], g["z0"]),
                        z1=max(same["z1"], g["z1"]), parts=same["parts"] + g["parts"], rects=same["rects"] + g["rects"],
                        glass_z=same["glass_z"] + g["glass_z"], glass_world=same["glass_world"] + g["glass_world"],
                        depth=max(same["depth"], g["depth"]))
    return out


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
        out.append({"priority": "normal" if b["kind"] == "opening-size-unknown" else "high",
                    "kind": b["kind"], "levels": [levels[b["level"]]["name"]], "wall": None,
                    "depth_m": None, "length_m": round(float(np.linalg.norm(b["p"] - b["q"])), 3),
                    "facade_share": None, "heights_m": [round(b["z0"], 3), round(b["z1"], 3)],
                    "at": [round(float(mid[0]), 2), round(float(mid[1]), 2)]})
    return out

"""Openings of the spec: a hole in the body or a glass pane at a wall (user decision 2026-10-08, #7).

Holes are found in the horizontal sections themselves: where a wall breaks, its two dangling ends
are bridged along the wall line. Before a bridge, a dangling reveal leg (the wall turning in for at
most REVEAL_MAX_M) is followed back to the wall line, so the bridge closes the mouth and the leg is
the reveal depth. Bridges close the section for the level contour (a door from the floor no longer
opens the storey end) and stack over heights into openings. Glass panes (meshes named *glass*)
project onto their nearest contour wall. A hole and glass at one place are one opening.
"""
from collections import defaultdict

import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, Polygon

SNAP_M = 1e-5          # section points closer than this are one point (KPP1: 1 um gaps at window jambs)
OPENING_MAX_M = 8.0    # widest gap in a wall that is bridged as an opening
REVEAL_MAX_M = 1.0     # deepest reveal leg followed back to the wall line
BRIDGE_DEG = 3.0       # a bridge runs along the wall line within this angle
MOUTH_KEY_M = 0.01     # bridges at different heights within 1 cm are one opening
PANE_JOIN_M = 0.25     # glass panes closer than this along a wall (mullions) are one opening
PANE_WALL_M = 1.0      # a pane further than this from every contour wall is not an opening
MATCH_M = 0.05         # hole and glass, or recess and opening, overlapping within 5 cm are one place


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


def _ends(adj, p):
    """Two readings of a dangling end: the end itself on the wall line, or the mouth reached by
    following a short straight reveal leg back to where the wall turns. (mouth, dir to gap, depth)."""
    path, prev, cur = [p], None, p
    while len(path) < 400:
        nxt = [n for n in adj[cur] if n != prev]
        if len(nxt) != 1:
            break
        prev, cur = cur, nxt[0]
        path.append(cur)
    pts = np.array(path)
    direct = (pts[0], _unit(pts[0] - pts[1]), 0.0)
    leg = _unit(pts[0] - pts[1])
    for k in range(1, len(pts) - 1):
        d = _unit(pts[k] - pts[k + 1])
        if float(d @ leg) < np.cos(np.radians(10)):            # the leg ends where the wall turns
            depth = float(np.linalg.norm(pts[0] - pts[k]))
            return [direct] + ([(pts[k], d, depth)] if depth <= REVEAL_MAX_M else [])
    return [direct]


def _pair(ends):
    """Mutually nearest dangling ends that face each other along one wall line."""
    cos = np.cos(np.radians(BRIDGE_DEG))
    best = {}
    for i, (mi, ei, _) in enumerate(ends):
        for j, (mj, ej, _) in enumerate(ends):
            u = mj - mi
            dist = float(np.linalg.norm(u))
            if i == j or not 1e-6 < dist <= OPENING_MAX_M:
                continue
            if float(_unit(u) @ ei) >= cos and float(-_unit(u) @ ej) >= cos and dist < best.get(i, (np.inf,))[0]:
                best[i] = (dist, j)
    return [(i, j) for i, (_, j) in best.items() if best.get(j, (0, -1))[1] == i and i < j]


def close_section(segments):
    """Polygonize a section, bridging wall breaks. Returns (outer polygon or None, mouths), where a
    mouth is (point, point, reveal depth)."""
    if not segments:
        return None, []
    noded = shapely.unary_union(shapely.set_precision(MultiLineString(segments), SNAP_M))
    adj = _graph(noded)
    dangles = [p for p, n in adj.items() if len(n) == 1]
    mouths, used = [], set()
    if dangles:
        readings = {p: _ends(adj, p) for p in dangles}
        for level in (0, 1):                                    # wall-line ends first, then reveal mouths
            free = [(p, readings[p][min(level, len(readings[p]) - 1)]) for p in dangles if p not in used]
            for i, j in _pair([r for _, r in free]):
                (p, (mp, _, dp)), (q, (mq, _, dq)) = free[i], free[j]
                used.update((p, q))
                mouths.append((mp, mq, max(dp, dq)))
    lines = list(shapely.get_parts(noded)) + [LineString([a, b]) for a, b, _ in mouths]
    polys = list(shapely.get_parts(shapely.polygonize(shapely.get_parts(shapely.unary_union(lines)))))
    if not polys:
        return None, mouths
    biggest = max(shapely.get_parts(shapely.unary_union(polys)), key=lambda g: g.area)
    return Polygon(biggest.exterior), mouths


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


def _hole_openings(mouth_spans, contour_pts):
    """Stack bridges of one storey into openings: one per mouth and contiguous height run."""
    groups = []
    for a, b, mouths in mouth_spans:
        for mp, mq, depth in mouths:
            for g in groups:
                if (min(np.linalg.norm(g["p"] - mp) + np.linalg.norm(g["q"] - mq),
                        np.linalg.norm(g["p"] - mq) + np.linalg.norm(g["q"] - mp)) <= 2 * MOUTH_KEY_M):
                    g["spans"].append((a, b))
                    g["depth"] = max(g["depth"], depth)
                    break
            else:
                groups.append({"p": mp, "q": mq, "spans": [(a, b)], "depth": depth})
    out = []
    for g in groups:
        runs = []
        for a, b in sorted(g["spans"]):
            if runs and a - runs[-1][1] < 1e-6:
                runs[-1][1] = b
            else:
                runs.append([a, b])
        w, origin, u, _ = _wall_frame(contour_pts, (g["p"] + g["q"]) / 2, float(np.linalg.norm(g["p"] - g["q"])) / 2)
        x = sorted(((g["p"] - origin) @ u, (g["q"] - origin) @ u))
        for lo, hi in runs:
            out.append({"wall": w, "x0": float(x[0]), "x1": float(x[1]), "z0": lo, "z1": hi,
                        "depth": g["depth"], "source": "hole"})
    return out


def glass_panes(v, tris, parts):
    """Vertical glass panes as (points, plane normal); horizontal glass is reported, not an opening."""
    panes, flat = [], 0
    for part in parts:
        pts = v[np.unique(tris[part])]
        centred = pts - pts.mean(axis=0)
        normal = np.linalg.svd(centred, full_matrices=False)[2][-1]
        if abs(normal[2]) > 0.5:
            flat += 1
            continue
        panes.append(pts)
    return panes, flat


def _glass_openings(panes, levels, floors, polys):
    out, far = [], 0
    for pts in panes:
        zc = float(pts[:, 2].mean())
        li = next((i for i in range(len(floors)) if levels[i]["elev_m"] <= zc < levels[i + 1]["elev_m"]), None)
        if li is None:
            far += 1
            continue
        centre = pts[:, :2].mean(axis=0)
        half = float(np.ptp(pts[:, :2], axis=0).max()) / 2
        w, origin, u, _ = _wall_frame(floors[li]["contour"], centre, half)
        if polys[li].exterior.distance(shapely.Point(centre)) > PANE_WALL_M:
            far += 1
            continue
        along = (pts[:, :2] - origin) @ u
        normal = np.array([u[1], -u[0]])                         # outward for a CCW contour
        depth = max(0.0, -float((centre - origin) @ normal))
        out.append({"level": li, "wall": w, "x0": float(along.min()), "x1": float(along.max()),
                    "z0": float(pts[:, 2].min()), "z1": float(pts[:, 2].max()), "depth": depth,
                    "source": "glass", "panes": 1})
    merged = []
    for o in sorted(out, key=lambda o: (o["level"], o["wall"], o["x0"])):
        m = merged[-1] if merged else None
        if (m and m["level"] == o["level"] and m["wall"] == o["wall"] and o["x0"] - m["x1"] <= PANE_JOIN_M
                and o["z0"] < m["z1"] and m["z0"] < o["z1"]):
            m.update(x1=max(m["x1"], o["x1"]), z0=min(m["z0"], o["z0"]), z1=max(m["z1"], o["z1"]),
                     depth=max(m["depth"], o["depth"]), panes=m["panes"] + 1)
        else:
            merged.append(dict(o))
    return merged, far


def _overlap(a, b, tol=MATCH_M):
    return (a["wall"] == b["wall"] and a["x0"] < b["x1"] + tol and b["x0"] < a["x1"] + tol
            and a["z0"] < b["z1"] + tol and b["z0"] < a["z1"] + tol)


def assemble(levels, floors, polys, mouth_spans_by_level, panes):
    """Openings per floor for the spec, plus the plan footprints used to clear recess questions."""
    glass, far = _glass_openings(panes, levels, floors, polys)
    per_floor, footprints = [], []
    for li, floor in enumerate(floors):
        holes = _hole_openings(mouth_spans_by_level[li], floor["contour"])
        for g in [g for g in glass if g["level"] == li]:
            match = next((h for h in holes if _overlap(h, g)), None)
            if match:
                match["source"] = "hole+glass"
                match["depth"] = max(match["depth"], g["depth"])
            else:
                holes.append(g)
        elev = levels[li]["elev_m"]
        pts = np.array([q[:2] for q in floor["contour"]], dtype=float)
        items = []
        for o in sorted(holes, key=lambda o: (o["wall"], o["x0"])):
            items.append({"wall": o["wall"], "x_m": round(max(o["x0"], 0.0), 3), "sill_m": round(o["z0"] - elev, 3),
                          "w_m": round(o["x1"] - o["x0"], 3), "h_m": round(o["z1"] - o["z0"], 3),
                          "depth_m": round(o["depth"], 3), "window_type": None, "source": o["source"]})
            a = pts[o["wall"]]
            u = _unit(pts[(o["wall"] + 1) % len(pts)] - a)
            n = np.array([u[1], -u[0]])
            p0, p1 = a + u * o["x0"], a + u * o["x1"]
            out_, in_ = MATCH_M, o["depth"] + MATCH_M
            footprints.append({"level": li, "z0": o["z0"], "z1": o["z1"],
                               "geom": Polygon([p0 + n * out_, p1 + n * out_, p1 - n * in_, p0 - n * in_])})
        per_floor.append(items)
    return per_floor, footprints, {"glass_openings": len(glass), "glass_far_or_off_level": far}


def is_opening_recess(piece, level, footprints):
    """A recess piece that sits in an opening's footprint at its heights is the opening's reveal."""
    lo, hi = min(a for a, _ in piece["spans"]), max(b for _, b in piece["spans"])
    return any(f["level"] == level and f["z0"] < hi + MATCH_M and lo < f["z1"] + MATCH_M
               and f["geom"].buffer(MATCH_M).contains(piece["geom"]) for f in footprints)

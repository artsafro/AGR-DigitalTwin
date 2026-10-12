"""Facade decor from the non-body parts of a mesh dump (pattern facade-decor-inset; spec v0.5).

User decisions 2026-10-11/12: one simple solid per element; projection <= 0.10 m is texture, > 0.10 m
geometry, boundary included, never a question; source pieces with the same cross-section on one axis with
seams up to plate_gap_m x 12 are one element (a pilaster split per storey); a free-standing column is its
own element. A question only where these rules do not cover a piece.

A part is wall decor when it lies on one contour wall of the storey of its bottom: its back at the wall
face (within SHARE_TOL_M) or embedded up to EMBED_MAX_M, nothing further out than PROJECTION_MAX_M, inside
that wall's span, and on a wall of the same line and span in every storey it crosses. It must be a box in
the wall frame: faces axis-aligned and its front face covering its whole front rectangle at full projection
(an L, a stepped profile or a flat sheet is no box). A wall piece that fails this, or is deeper than
ATTACHMENT_FROM_M is no decor but an attachment candidate (balcony, canopy, bay: EG2; user 2026-10-12): kept
out of the spec, listed in the report and asked once per type. A column stands free: an axis-aligned box
COLUMN_MIN_H_M high, COLUMN_MIN_M to COLUMN_MAX_M a side, its bottom on a level; one starting mid-storey is a
`decor-column` question (user 2026-10-12). Questions are grouped by type: one kind and one cross-section
(projection and height) is one question, its count and positions listed (user 2026-10-12: no avalanche). Every other
part stays an attachment, as before. Pieces join when the joined pieces fill one rectangle up to the seams
(a row, a stack or a full grid); any other arrangement of joinable pieces is a `decor-merge` question and
the pieces stay apart (reviews of PR #74).
Pattern: facade-decor-inset (draft).
"""
from collections import defaultdict

import numpy as np
import shapely
from shapely.ops import unary_union

from dt_ai.spec.model import DECOR_TEXTURE_M

SHARE_TOL_M = 0.005       # a piece's back at the wall face within this
EMBED_MAX_M = 0.05        # ... or embedded into the wall up to this
PROJECTION_MAX_M = 1.5    # deeper than this off a wall is no facade decor (canopy, balcony)
ATTACHMENT_FROM_M = 0.8   # projection over this: an attachment candidate, not decor (user 2026-10-12)
SPAN_TOL_M = 0.01         # a piece lies within its wall's span within this ...
RUN_ON_MAX_M = 0.8        # ... or runs on past a building corner by at most this (an element's projection)
SAME_M = 0.005            # one cross-section / one axis within this
COVER = 0.99              # a box's front face covers this share of its front rectangle
SEAM_FACTOR = 12          # seams up to plate_gap_m x 12 (0.06 m by default) join pieces (user 2026-10-12)
AXIS_COS = np.cos(np.radians(1.0))
COLUMN_MIN_H_M = 2.0
COLUMN_MAX_M = 1.5
COLUMN_MIN_M = 0.05       # ... and at least this on each side: a vertical sheet is no column
COLUMN_BASE_M = 0.05      # ... standing on a level (its bottom within this of one)
BAND_RATIO = 3.0          # band: width >= 3 x height; strip: height >= 3 x width; else panel
ROUND = 6                 # metres to the micron in the spec ...
ROUND_OUT = 9             # ... projections to the nanometre: the texture boundary is decided on the written value


def _walls(contour):
    """(start, unit along, unit outward, length) per contour wall."""
    pts = np.array([p[:2] for p in contour], dtype=float)
    x, y = pts[:, 0], pts[:, 1]
    ccw = (x * np.roll(y, -1) - np.roll(x, -1) * y).sum() > 0
    out = []
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        length = float(np.linalg.norm(b - a))
        u = (b - a) / length
        n = np.array([u[1], -u[0]]) if ccw else np.array([-u[1], u[0]])
        out.append((a, u, n, length))
    return out


def _wall_at(contour, u, c, s0, s1):
    """(wall index, x_m) of the wall on line (u, c) whose span holds s0..s1 (absolute along u); None if none
    (review 1 of PR #74: on a concave contour several walls share a line)."""
    for w, (a, wu, n, length) in enumerate(_walls(contour)):
        start = float(a @ wu)
        if (wu @ u >= AXIS_COS and abs(float(a @ n) - c) <= SAME_M
                and s0 >= start - SPAN_TOL_M and s1 <= start + length + SPAN_TOL_M):
            return w, s0 - start
    return None


def _storey(levels, z):
    for i in range(len(levels) - 1):
        if z < levels[i + 1]["elev_m"] - SAME_M:
            return i
    return len(levels) - 2


def _normals(t):
    nv = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    area = np.linalg.norm(nv, axis=1) / 2
    keep = area > 1e-12
    return nv[keep] / (2 * area[keep, None]), area[keep], t[keep]


AT_FACE_M = 0.0006        # a face this close to the wall face is at it (the engine's corner ends start 0.5 mm off)
DEPTH_TOL_M = 1e-4        # depths of one face (a thin box keeps its two faces, review 3 of PR #74)


def _levels_of(values, tol):
    """Distinct values within tol."""
    out = []
    for x in sorted(values):
        if not out or x - out[-1] > tol:
            out.append(x)
    return out


def _covered(t, normals, coords, axis, sign, floor=None):
    """Whether the faces facing `sign` along `axis` at that extreme cover the whole rectangle of the other two
    coordinates (reviews 1-3 of PR #74: summed areas or one face do not prove a solid). floor: {axis: lowest
    value} that clips the rectangle (a wall element: only its part out of the wall face must be closed; the
    engine's end faces start at the wall face at a building corner, review 1 of PR #75)."""
    c = coords[axis]
    end = c.max() if sign > 0 else c.min()
    face = (sign * normals[:, axis] >= AXIS_COS) & (np.abs(c - end).max(axis=1) <= DEPTH_TOL_M)
    i, j = [k for k in range(3) if k != axis]
    lo = [max(coords[k].min(), (floor or {}).get(k, -np.inf)) for k in (i, j)]
    target = shapely.box(lo[0], lo[1], coords[i].max(), coords[j].max())
    cover = unary_union([shapely.Polygon(np.column_stack([coords[i][k], coords[j][k]])) for k in np.flatnonzero(face)])
    return target.area > 0 and cover.intersection(target).area >= COVER * target.area


def _is_box(t, u, n, c, hosts=()):
    """A box in the wall frame (reviews 1-3 of PR #74): faces axis-aligned, two depths only (back and front,
    no stepped profile), and front, top, bottom and both ends each covering their whole rectangle; the back
    may be open (inset decor). Inner s / z values are allowed: pieces of a row or a stack welded into one.
    An end (top, bottom or a side end) may be missing where it lies inside another element of the wall line
    (hosts: {s0, s1, z0, z1, d1} absolute): a subordinate element run into a main one (user 2026-10-12); its
    extent is then clipped at the main one's face. Returns the clip {key: value} (empty when whole), or None
    when it is no box."""
    normals, _, t = _normals(t)
    axes = np.array([[*u, 0.0], [*n, 0.0], [0.0, 0.0, 1.0]])
    if not len(normals) or not (np.abs(normals @ axes.T).max(axis=1) >= AXIS_COS).all():
        return None
    coords = (t[..., :2] @ u, t[..., :2] @ n, t[..., 2])
    local = normals @ axes.T
    # two depths out of the wall face: the face and the front (the inset part inside the body is not seen)
    seen = np.maximum(coords[1].ravel(), c + AT_FACE_M)
    if np.ptp(coords[0]) <= SAME_M or np.ptp(coords[2]) <= SAME_M or len(_levels_of(seen, DEPTH_TOL_M)) != 2:
        return None
    face = {1: c}                                      # out of the wall face (c along n) only
    if not _covered(t, local, coords, 1, 1, face):
        return None
    lo = {k: float(coords[k].min()) for k in (0, 2)}
    hi = {k: float(coords[k].max()) for k in (0, 2)}
    front = float(coords[1].max())
    clip = {}
    for axis, sign in ((2, 1), (2, -1), (0, 1), (0, -1)):
        if _covered(t, local, coords, axis, sign, face):
            continue
        end = hi[axis] if sign > 0 else lo[axis]
        other = 2 if axis == 0 else 0
        key = {0: ("s0", "s1"), 2: ("z0", "z1")}
        def holds(h):
            if h.get("corner"):                       # across walls: the end lies on the main one's back plane
                inside = h[key[axis][0]] - DEPTH_TOL_M <= end <= h[key[axis][1]] + DEPTH_TOL_M
            else:
                inside = h[key[axis][0]] + DEPTH_TOL_M < end < h[key[axis][1]] - DEPTH_TOL_M
            return (inside and h[key[other][0]] - DEPTH_TOL_M <= lo[other] and hi[other] <= h[key[other][1]] + DEPTH_TOL_M
                    and front <= h["d1"] + DEPTH_TOL_M)
        host = next((h for h in hosts if holds(h)), None)
        if host is None or (axis == 2 and host.get("corner")):
            return None
        if host.get("corner"):                        # the source extent reaches the corner
            clip[key[axis][1] if sign > 0 else key[axis][0]] = host["to1"] if sign > 0 else host["to0"]
        elif sign > 0:
            clip[key[axis][1]] = host[key[axis][0]]
        else:
            clip[key[axis][0]] = host[key[axis][1]]
    return clip


def _is_column(t):
    """An axis-aligned box in the object frame: rectangular footprint (two x, two y values) and four sides and
    the top each covering their whole rectangle; the bottom may be open (reviews 2-3 of PR #74)."""
    normals, _, t = _normals(t)
    if not len(normals) or not (np.abs(normals).max(axis=1) >= AXIS_COS).all():
        return False
    p = t.reshape(-1, 3)
    if len(_levels_of(p[:, 0], DEPTH_TOL_M)) != 2 or len(_levels_of(p[:, 1], DEPTH_TOL_M)) != 2:
        return False
    coords = (t[..., 0], t[..., 1], t[..., 2])
    return all(_covered(t, normals, coords, axis, sign) for axis, sign in ((0, 1), (0, -1), (1, 1), (1, -1), (2, 1)))


def _piece(v, part_tris, levels, contours, polys):
    """A wall piece, a non-box wall piece ("shape"), a column, or None (an attachment)."""
    p = v[np.unique(part_tris)]
    t = v[part_tris]
    z0, z1 = float(p[:, 2].min()), float(p[:, 2].max())
    li = _storey(levels, z0)
    best = None
    for w, (a, u, n, length) in enumerate(_walls(contours[li])):
        s = (p[:, :2] - a) @ u
        d = (p[:, :2] - a) @ n
        # at a building corner the main element runs on past the wall end by the other's projection
        # (user 2026-10-12); a piece fully inside the span is preferred
        if (d.min() < -EMBED_MAX_M or d.min() > SHARE_TOL_M or d.max() > PROJECTION_MAX_M or d.max() <= 0
                or s.min() < -RUN_ON_MAX_M or s.max() > length + RUN_ON_MAX_M):
            continue
        over = s.min() < -SPAN_TOL_M or s.max() > length + SPAN_TOL_M
        if best is None or (over, abs(d.min())) < (best[2], abs(best[1])):
            best = (w, float(d.min()), over)
    if best is not None:
        a, u, n, length = _walls(contours[li])[best[0]]
        s, d = p[:, :2] @ u, p[:, :2] @ n                 # absolute along / out, comparable across storeys
        c, o = float(a @ n), float(a @ u)
        s0, s1 = float(s.min()), float(s.max())
        if best[2]:                                       # a run-on: the source extent ends at the wall end
            s0, s1 = max(s0, o) if s0 < o - SPAN_TOL_M else s0, min(s1, o + length) if s1 > o + length + SPAN_TOL_M else s1
        pc = {"li": li, "u": u, "n": n, "c": c, "o": o, "length": length, "s0": s0, "s1": s1, "z0": z0, "z1": z1,
              "out": float(d.max() - c), "embed": float(c - d.min()), "run_on": best[2],
              "foot": shapely.MultiPoint(p[:, :2]).convex_hull}
        # every storey it crosses has a wall on the same line holding its span (review 1 of PR #74)
        crossed = range(li, _storey(levels, z1 - SAME_M) + 1)
        on_walls = all(_wall_at(contours[k], u, c, pc["s0"], pc["s1"]) is not None for k in crossed)
        pc["type"] = "wall" if on_walls and _is_box(t, u, n, c) is not None else "shape"
        pc["t"], pc["on_walls"] = t, on_walls
        return pc
    lo, hi = p[:, :2].min(axis=0), p[:, :2].max(axis=0)
    foot = shapely.box(*lo, *hi)                          # clear of the body in every storey it crosses
    free = all(polys[k].distance(foot) > SHARE_TOL_M for k in range(li, _storey(levels, z1 - SAME_M) + 1))
    grounded = any(abs(z0 - lv["elev_m"]) <= COLUMN_BASE_M for lv in levels)
    if (free and z1 - z0 >= COLUMN_MIN_H_M and COLUMN_MIN_M <= (hi - lo).min()
            and (hi - lo).max() <= COLUMN_MAX_M and _is_column(t)):
        return {"type": "column" if grounded else "column-off-level", "li": li,
                "box": [float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])], "z0": z0, "z1": z1,
                "out": float((hi - lo).max()), "s0": 0.0, "s1": float((hi - lo).min())}
    return None


def _corner_arms(v, tris, part, levels, contours):
    """A part round one or more convex building corners (elements meeting there, or a belt wrapped round),
    split into one arm per wall, or None (user 2026-10-12: of one rank the longer continues; review 2 of PR
    #75: any number of corners). A triangle belongs to the wall whose span holds its centre (in front of that
    wall); a corner block past two wall ends goes to the longer of the two arms; an oblique corner: None; the other higher than the longer: "decor-corner"."""
    p = v[np.unique(tris[part])]
    li = _storey(levels, float(p[:, 2].min()))
    walls = _walls(contours[li])
    centre = v[tris[part]].mean(axis=1)[:, :2]
    own = np.full(len(part), -1)
    for w, (a, u, n, length) in enumerate(walls):
        s, d = (centre - a) @ u, (centre - a) @ n
        hit = (s > EMBED_MAX_M) & (s < length - EMBED_MAX_M) & (d >= -EMBED_MAX_M) & (d <= PROJECTION_MAX_M)
        if (hit & (own >= 0)).any():
            return None
        own[hit] = w
    arms = sorted(set(own[own >= 0]))
    if len(arms) < 2:
        return None
    reach = {}
    for w in arms:
        a, u, _, length = walls[w]
        s = (centre[own == w] - a) @ u
        reach[w] = float(s.max() - s.min())
    for k in np.flatnonzero(own < 0):                  # corner blocks
        near = []
        for w in arms:
            nxt = (w + 1) % len(walls)
            if nxt in arms:
                corner = walls[nxt][0]
                if np.linalg.norm(centre[k] - corner) <= RUN_ON_MAX_M + EMBED_MAX_M:
                    near.append((w, nxt))
        if len(near) != 1:
            return None
        w0, w1 = near[0]
        u0, u1 = walls[w0][1], walls[w1][1]
        if abs(float(u0 @ u1)) > 1 - AXIS_COS or u0[0] * u1[1] - u0[1] * u1[0] <= 0:
            return None                                # an oblique or concave corner: not read
        if abs(reach[w0] - reach[w1]) <= SAME_M:
            return None                                # one length: which continues is the user's
        own[k] = w0 if reach[w0] > reach[w1] else w1
        main_w, other_w = (w0, w1) if reach[w0] > reach[w1] else (w1, w0)
        zm = v[tris[part[own == main_w]]][..., 2]
        zo = v[tris[part[own == other_w]]][..., 2]
        if zo.min() < zm.min() - SAME_M or zo.max() > zm.max() + SAME_M:
            return "decor-corner"                        # the other higher than the main one (user 2026-10-12)
    return [part[own == w] for w in arms]


def _texture(out):
    return round(out, ROUND_OUT) <= DECOR_TEXTURE_M     # exactly the rule (review 3 of PR #74)


def _joinable(a, b, seam):
    """Same cross-section on one axis, gap at most the seam: stacked (same s span) or in a row (same z span);
    never across the texture boundary (review 1 of PR #74)."""
    if a["u"] @ b["u"] < AXIS_COS or abs(a["c"] - b["c"]) > SAME_M or abs(a["out"] - b["out"]) > SAME_M:
        return False
    if _texture(a["out"]) != _texture(b["out"]):
        return False
    same_s = abs(a["s0"] - b["s0"]) <= SAME_M and abs(a["s1"] - b["s1"]) <= SAME_M
    same_z = abs(a["z0"] - b["z0"]) <= SAME_M and abs(a["z1"] - b["z1"]) <= SAME_M
    if same_s:
        gap = max(a["z0"], b["z0"]) - min(a["z1"], b["z1"])
        return -SAME_M <= gap <= seam + 1e-9
    if same_z:
        gap = max(a["s0"], b["s0"]) - min(a["s1"], b["s1"])
        return -SAME_M <= gap <= seam + 1e-9
    return False


def _merge(pieces, seam):
    """(elements, ambiguous groups). Joinable pieces form groups (independent of order); a group whose pieces
    fill one rectangle up to the seams is one element, any other group stays apart and is asked."""
    parent = list(range(len(pieces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            if _joinable(pieces[i], pieces[j], seam):
                parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i in range(len(pieces)):
        groups[find(i)].append(pieces[i])
    elements, ambiguous = [], []
    for g in sorted(groups.values(), key=lambda g: min((p["s0"], p["z0"]) for p in g)):
        if len(g) == 1:
            elements.append(dict(g[0], pieces=1))
            continue
        half = seam / 2 + 1e-9
        s0, s1 = min(p["s0"] for p in g), max(p["s1"] for p in g)
        z0, z1 = min(p["z0"] for p in g), max(p["z1"] for p in g)
        filled = unary_union([shapely.box(p["s0"] - half, p["z0"] - half, p["s1"] + half, p["z1"] + half)
                              for p in g])
        outs = [p["out"] for p in g]                     # one cross-section over the whole group (review 2)
        if filled.area >= (s1 - s0 + 2 * half) * (z1 - z0 + 2 * half) - 1e-6 and max(outs) - min(outs) <= SAME_M:
            elements.append(dict(g[0], s0=s0, s1=s1, z0=z0, z1=z1, li=min(p["li"] for p in g), pieces=len(g),
                                 out=max(p["out"] for p in g), embed=max(p["embed"] for p in g),
                                 ids=set().union(*(p["ids"] for p in g)),
                                 part=np.concatenate([p["part"] for p in g])))
        else:
            ambiguous.append(g)
            elements += [dict(p, pieces=1) for p in g]
    return elements, ambiguous


def _question(kind, levels, li, out, s0, s1, z0, z1, at=None):
    return {"priority": "low", "kind": kind, "levels": [levels[li]["name"]], "wall": None,
            "depth_m": round(out, 3), "length_m": round(s1 - s0, 3), "facade_share": None,
            "heights_m": [round(z0, 3), round(z1, 3)], "at": at}


def _at(piece, s):
    """Plan point on the wall face at s along the wall (a question's position)."""
    p = piece["u"] * s + piece["n"] * piece["c"]
    return [round(float(p[0]), 2), round(float(p[1]), 2)]


def _grouped(questions, names):
    """One question per type: same kind and cross-section (projection and height within SAME_M); the first
    position stands for the group, all positions and the count are listed (user 2026-10-12)."""
    groups = []
    for q in sorted(questions, key=lambda q: (names.index(q["levels"][0]), q["heights_m"][0], q["at"] or [0, 0])):
        h = q["heights_m"][1] - q["heights_m"][0]
        for g in groups:
            if (g["kind"] == q["kind"] and abs(g["depth_m"] - q["depth_m"]) <= SAME_M
                    and abs(g["heights_m"][1] - g["heights_m"][0] - h) <= SAME_M):
                g["count"] += 1
                g["positions"].append(q["at"])
                g["levels"] = sorted(set(g["levels"]) | set(q["levels"]), key=names.index)
                if g["wall"] != q["wall"]:
                    g["wall"] = None
                break
        else:
            groups.append(dict(q, count=1, positions=[q["at"]]))
    return groups


def extract(v, tris, mats, parts, levels, contours, polys, plate_gap_m, attachment_ids, with_parts=False):
    """(decor entries for the spec, questions, report) from the non-body parts. parts: triangle-index arrays
    of the parts other than the body; contours / polys: per storey. with_parts: also the triangle indices of
    every entry, in the entries' order (the checker reads the model with it)."""
    seam = plate_gap_m * SEAM_FACTOR
    found, questions, kept = [], [], 0
    pieces = []
    for part in parts:
        pc = _piece(v, tris[part], levels, contours, polys)
        if pc is None or pc["type"] == "shape":
            arms = _corner_arms(v, tris, part, levels, contours)
            if arms == "decor-corner":                # its part above the main one is closed by nothing
                p = v[np.unique(tris[part])]
                questions.append(_question("decor-corner", levels, _storey(levels, float(p[:, 2].min())), 0.0, 0.0,
                                           0.0, float(p[:, 2].min()), float(p[:, 2].max()),
                                           [round(float(c), 2) for c in p[:, :2].mean(axis=0)]))
                continue
            if arms:                                  # a belt round a building corner: one element per wall
                found_arms = [(arm, _piece(v, tris[arm], levels, contours, polys)) for arm in arms]
                if all(a_pc is not None for _, a_pc in found_arms):
                    pieces += found_arms
                    continue
        if pc is None:
            kept += 1
            continue
        pieces.append((part, pc))
    for _, m in pieces:                               # a corner's other element higher than the main one (run on)
        if not m.get("run_on"):
            continue
        for part, o in pieces:
            if (o is m or "foot" not in o or o.get("type") == "corner" or abs(float(o["u"] @ m["u"])) > 1 - AXIS_COS
                    or o["foot"].distance(m["foot"]) > AT_FACE_M):
                continue
            if o["z0"] < m["z0"] - SAME_M or o["z1"] > m["z1"] + SAME_M:
                o["type"] = "corner"                     # user 2026-10-12: its part beyond the main one is open
    whole = [pc for _, pc in pieces if pc["type"] == "wall"]
    for part, pc in pieces:                           # a subordinate element run into a main one (user 2026-10-12)
        if pc["type"] == "shape" and pc["on_walls"]:
            hosts = [{"s0": h["s0"], "s1": h["s1"], "z0": h["z0"], "z1": h["z1"], "d1": h["c"] + h["out"]}
                     for h in whole if h is not pc and h["u"] @ pc["u"] >= AXIS_COS and abs(h["c"] - pc["c"]) <= SAME_M]
            for h in whole:                           # the main one of a building corner, on the next wall
                if h is pc or abs(float(h["u"] @ pc["u"])) > 1 - AXIS_COS:
                    continue
                hs, hd = h["t"][..., :2] @ pc["u"], h["t"][..., :2] @ pc["n"]
                hosts.append({"s0": float(hs.min()), "s1": float(hs.max()), "z0": h["z0"], "z1": h["z1"],
                              "d1": float(hd.max()), "corner": True, "to0": pc["o"], "to1": pc["o"] + pc["length"]})
            clip = _is_box(pc["t"], pc["u"], pc["n"], pc["c"], hosts) if hosts else None
            if clip:
                pc.update(clip, type="wall", inset_into=True)
    for part, pc in pieces:
        pc["part"] = part
        pc["ids"] = set(int(i) for i in np.unique(mats[part]))
        if pc["type"] in ("shape", "wall") and pc["out"] > ATTACHMENT_FROM_M:
            pc["type"] = "deep"
        if pc["type"] in ("shape", "deep", "column-off-level", "corner"):
            at = [round(float(c), 2) for c in v[np.unique(tris[part])][:, :2].mean(axis=0)]
            kind = {"shape": "decor-shape", "deep": "decor-deep", "column-off-level": "decor-column",
                    "corner": "decor-corner"}[pc["type"]]
            questions.append(_question(kind, levels, pc["li"], pc["out"], pc["s0"], pc["s1"], pc["z0"], pc["z1"], at))
            continue
        found.append(pc)
    walls, ambiguous = _merge([p for p in found if p["type"] == "wall"], seam)
    for g in ambiguous:                                   # placed by wall and position: answers stay with it
        li, s0, s1 = min(p["li"] for p in g), min(p["s0"] for p in g), max(p["s1"] for p in g)
        q = _question("decor-merge", levels, li, max(p["out"] for p in g), s0, s1,
                      min(p["z0"] for p in g), max(p["z1"] for p in g), _at(g[0], (s0 + s1) / 2))
        q["wall"] = (_wall_at(contours[li], g[0]["u"], g[0]["c"], s0, s1) or (None,))[0]
        questions.append(q)
    columns = [dict(p, pieces=1) for p in found if p["type"] == "column"]
    decor, owned = [], []
    for e in walls + columns:
        li = e["li"]
        lv = levels[li]
        mid = sorted(e["ids"])[0] if len(e["ids"]) == 1 and next(iter(e["ids"])) in attachment_ids else None
        entry = {"level": lv["name"], "z_m": round(e["z0"] - lv["elev_m"], ROUND), "h_m": round(e["z1"] - e["z0"], ROUND),
                 "material_id": mid, "pieces": e["pieces"]}
        if e["type"] == "column":
            x0, y0, x1, y1 = e["box"]
            decor.append({"kind": "column", **entry, "w_m": round(max(x1 - x0, y1 - y0), ROUND),
                          "footprint": [round(x0, ROUND), round(y0, ROUND), round(x1, ROUND), round(y1, ROUND)]})
            owned.append(e["part"])
            continue
        at = _wall_at(contours[li], e["u"], e["c"], e["s0"], e["s1"])
        if at is None:                                    # cannot happen for a checked piece; never guess
            questions.append(_question("decor-shape", levels, li, e["out"], e["s0"], e["s1"], e["z0"], e["z1"],
                                       _at(e, (e["s0"] + e["s1"]) / 2)))
            continue
        w_m, h_m = e["s1"] - e["s0"], e["z1"] - e["z0"]
        kind = "band" if w_m >= BAND_RATIO * h_m else "strip" if h_m >= BAND_RATIO * w_m else "panel"
        out = round(e["out"], ROUND_OUT)
        decor.append({"kind": kind, **entry, "wall": at[0], "x_m": round(at[1], ROUND), "w_m": round(w_m, ROUND),
                      "projection_m": out, "texture": _texture(out)})
        owned.append(e["part"])
    names = [lv["name"] for lv in levels]
    questions = _grouped(questions, names)
    candidates = [{"projection_m": q["depth_m"], "h_m": round(q["heights_m"][1] - q["heights_m"][0], 3),
                   "count": q["count"], "levels": q["levels"], "at": q["positions"]}
                  for q in questions if q["kind"] == "decor-deep"]
    order = sorted(range(len(decor)), key=lambda k: (names.index(decor[k]["level"]), decor[k].get("wall") or 0,
                                                     decor[k].get("x_m") or 0.0, decor[k]["z_m"]))
    decor, owned = [decor[k] for k in order], [owned[k] for k in order]
    report = {"pieces": len(found), "elements": len(decor), "texture": sum(d.get("texture", False) for d in decor),
              "columns": len(columns), "seam_m": round(seam, 4), "not_decor_parts": kept,
              "ambiguous_groups": len(ambiguous), "attachment_candidates": candidates, "questions": len(questions)}
    return (decor, questions, report, owned) if with_parts else (decor, questions, report)

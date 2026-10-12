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
DEEP_ASK_M (canopy, porch or decor: the rules do not say), is a question. A column stands free: an
axis-aligned box COLUMN_MIN_H_M high, COLUMN_MIN_M to COLUMN_MAX_M a side, standing on a level. Every other
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
DEEP_ASK_M = 0.8          # deeper than the catalogue's common decor (0.8 m): canopy, porch or decor? a question
                          # (proposed 2026-10-12, awaiting the user)
SPAN_TOL_M = 0.01         # a piece lies within its wall's span within this
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


def _levels_of(values):
    """Distinct values within SAME_M."""
    out = []
    for x in sorted(values):
        if not out or x - out[-1] > SAME_M:
            out.append(x)
    return out


def _is_box(t, u, n):
    """Axis-aligned in the wall frame, only two depths (back and front: no stepped profile) and its front face
    covering the whole front rectangle at full projection (reviews 1-2 of PR #74). Inner s / z values are
    allowed: pieces of a row or a stack welded into one part."""
    normals, _, t = _normals(t)
    axes = np.array([[*u, 0.0], [*n, 0.0], [0.0, 0.0, 1.0]])
    if not len(normals) or not (np.abs(normals @ axes.T).max(axis=1) >= AXIS_COS).all():
        return False
    s, d, z = t[..., :2] @ u, t[..., :2] @ n, t[..., 2]
    w, h = s.max() - s.min(), z.max() - z.min()
    if w <= SAME_M or h <= SAME_M or len(_levels_of(d.ravel())) != 2:
        return False
    front = (normals @ axes[1] >= AXIS_COS) & (np.abs(d - d.max()).max(axis=1) <= SAME_M)
    cover = unary_union([shapely.Polygon(np.column_stack([s[k], z[k]])) for k in np.flatnonzero(front)])
    return cover.area >= COVER * w * h


def _is_column(t):
    """An axis-aligned box in the object frame: two x and two y values only (no L footprint, review 2 of
    PR #74) and its sides covering the whole perimeter x height."""
    normals, area, _ = _normals(t)
    if not len(normals) or not (np.abs(normals).max(axis=1) >= AXIS_COS).all():
        return False
    p = t.reshape(-1, 3)
    if len(_levels_of(p[:, 0])) != 2 or len(_levels_of(p[:, 1])) != 2:
        return False
    dx, dy, h = np.ptp(p[:, 0]), np.ptp(p[:, 1]), np.ptp(p[:, 2])
    sides = area[np.abs(normals[:, 2]) < 1 - AXIS_COS].sum()
    return sides >= COVER * 2 * (dx + dy) * h


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
        if (d.min() < -EMBED_MAX_M or d.min() > SHARE_TOL_M or d.max() > PROJECTION_MAX_M or d.max() <= 0
                or s.min() < -SPAN_TOL_M or s.max() > length + SPAN_TOL_M):
            continue
        if best is None or abs(d.min()) < abs(best[1]):
            best = (w, float(d.min()))
    if best is not None:
        a, u, n, _ = _walls(contours[li])[best[0]]
        s, d = p[:, :2] @ u, p[:, :2] @ n                 # absolute along / out, comparable across storeys
        c = float(a @ n)
        pc = {"li": li, "u": u, "n": n, "c": c, "s0": float(s.min()), "s1": float(s.max()), "z0": z0, "z1": z1,
              "out": float(d.max() - c), "embed": float(c - d.min())}
        # every storey it crosses has a wall on the same line holding its span (review 1 of PR #74)
        crossed = range(li, _storey(levels, z1 - SAME_M) + 1)
        on_walls = all(_wall_at(contours[k], u, c, pc["s0"], pc["s1"]) is not None for k in crossed)
        pc["type"] = "wall" if on_walls and _is_box(t, u, n) else "shape"
        return pc
    lo, hi = p[:, :2].min(axis=0), p[:, :2].max(axis=0)
    foot = shapely.box(*lo, *hi)                          # clear of the body in every storey it crosses
    free = all(polys[k].distance(foot) > SHARE_TOL_M for k in range(li, _storey(levels, z1 - SAME_M) + 1))
    grounded = any(abs(z0 - lv["elev_m"]) <= COLUMN_BASE_M for lv in levels)
    if (free and grounded and z1 - z0 >= COLUMN_MIN_H_M and COLUMN_MIN_M <= (hi - lo).min()
            and (hi - lo).max() <= COLUMN_MAX_M and _is_column(t)):
        return {"type": "column", "li": li, "box": [float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])],
                "z0": z0, "z1": z1}
    return None


def _texture(out):
    return round(out, ROUND_OUT) <= DECOR_TEXTURE_M + 1e-9


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
                                 ids=set().union(*(p["ids"] for p in g))))
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


def extract(v, tris, mats, parts, levels, contours, polys, plate_gap_m, attachment_ids):
    """(decor entries for the spec, questions, report) from the non-body parts. parts: triangle-index arrays
    of the parts other than the body; contours / polys: per storey."""
    seam = plate_gap_m * SEAM_FACTOR
    found, questions, kept = [], [], 0
    for part in parts:
        pc = _piece(v, tris[part], levels, contours, polys)
        if pc is None:
            kept += 1
            continue
        pc["ids"] = set(int(i) for i in np.unique(mats[part]))
        if pc["type"] in ("shape", "wall") and pc["out"] > DEEP_ASK_M:
            pc["type"] = "deep"
        if pc["type"] in ("shape", "deep"):
            at = [round(float(c), 2) for c in v[np.unique(tris[part])][:, :2].mean(axis=0)]
            questions.append(_question(f"decor-{pc['type']}", levels, pc["li"], pc["out"], pc["s0"], pc["s1"],
                                       pc["z0"], pc["z1"], at))
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
    decor = []
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
    names = [lv["name"] for lv in levels]
    decor.sort(key=lambda d: (names.index(d["level"]), d.get("wall") or 0, d.get("x_m") or 0.0, d["z_m"]))
    report = {"pieces": len(found), "elements": len(decor), "texture": sum(d.get("texture", False) for d in decor),
              "columns": len(columns), "seam_m": round(seam, 4), "not_decor_parts": kept,
              "ambiguous_groups": len(ambiguous), "questions": len(questions)}
    return decor, questions, report

"""Facade decor from the non-body parts of a mesh dump (pattern facade-decor-inset; spec v0.5).

User decisions 2026-10-11/12: one simple solid per element; projection <= 0.10 m is texture, > 0.10 m
geometry, boundary included, never a question; source pieces with the same cross-section on one axis with
seams up to plate_gap_m x 12 are one element (a pilaster split per storey); a free-standing column is its
own element. A question only where these rules do not cover a piece.

A part is wall decor when it lies on one contour wall of the storey of its bottom: its back at the wall
face (within SHARE_TOL_M) or embedded up to EMBED_MAX_M, nothing further out than PROJECTION_MAX_M, and
inside the wall's span. Its faces must be axis-aligned in the wall frame (a box, or boxes welded into
one); anything else on a wall is a `decor-shape` question. A column stands free: COLUMN_MIN_H_M high, its
footprint COLUMN_MIN_M to COLUMN_MAX_M a side, standing on a level. A wall piece deeper than DEEP_ASK_M is a
`decor-deep` question (canopy, porch or decor: the rules do not say). Every other part stays an attachment, as before.
Pattern: facade-decor-inset (draft).
"""
import numpy as np
import shapely

from dt_ai.spec.model import DECOR_TEXTURE_M

SHARE_TOL_M = 0.005       # a piece's back at the wall face within this
EMBED_MAX_M = 0.05        # ... or embedded into the wall up to this
PROJECTION_MAX_M = 1.5    # deeper than this off a wall is no facade decor (canopy, balcony)
DEEP_ASK_M = 0.8          # deeper than the catalogue's common decor (0.8 m): canopy, porch or decor? a question
SPAN_TOL_M = 0.01         # a piece lies within its wall's span within this
SAME_M = 0.005            # one cross-section / one axis within this
SEAM_FACTOR = 12          # seams up to plate_gap_m x 12 (0.06 m by default) join pieces (user 2026-10-12)
AXIS_COS = np.cos(np.radians(1.0))
COLUMN_MIN_H_M = 2.0
COLUMN_MAX_M = 1.5
COLUMN_MIN_M = 0.05        # ... and at least this on each side: a vertical sheet is no column
COLUMN_BASE_M = 0.05       # ... standing on a level (its bottom within this of one)
BAND_RATIO = 3.0          # band: width >= 3 x height; strip: height >= 3 x width; else panel


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


def _storey(levels, z):
    for i in range(len(levels) - 1):
        if z < levels[i + 1]["elev_m"] - SAME_M:
            return i
    return len(levels) - 2


def _piece(v, part_tris, levels, contours, polys):
    """A wall piece {wall line, s0, s1, z0, z1, d0, d1}, a column, or a reason it is neither."""
    idx = np.unique(part_tris)
    p = v[idx]
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
        w = best[0]
        a, u, n, _ = _walls(contours[li])[w]
        t = v[part_tris]
        normals = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        normals = normals[np.linalg.norm(normals, axis=1) > 1e-12]
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        axes = np.array([[*u, 0.0], [*n, 0.0], [0.0, 0.0, 1.0]])
        aligned = bool((np.abs(normals @ axes.T).max(axis=1) >= AXIS_COS).all())
        s, d = p[:, :2] @ u, p[:, :2] @ n                 # absolute along / out, comparable across storeys
        c = float(a @ n)
        return {"type": "wall" if aligned else "shape", "li": li, "u": u, "n": n, "c": c,
                "s0": float(s.min()), "s1": float(s.max()), "z0": z0, "z1": z1,
                "out": float(d.max() - c), "embed": float(c - d.min())}
    xy = p[:, :2]
    lo, hi = xy.min(axis=0), xy.max(axis=0)
    free = polys[li].exterior.distance(shapely.Point(*((lo + hi) / 2))) > SHARE_TOL_M and \
        not polys[li].buffer(-SHARE_TOL_M).intersects(shapely.box(*lo, *hi))
    grounded = any(abs(z0 - lv["elev_m"]) <= COLUMN_BASE_M for lv in levels)
    if free and grounded and z1 - z0 >= COLUMN_MIN_H_M and COLUMN_MIN_M <= (hi - lo).min() and \
            (hi - lo).max() <= COLUMN_MAX_M:
        return {"type": "column", "li": li, "box": [float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])],
                "z0": z0, "z1": z1}
    return None


def _joinable(a, b, seam):
    """Same cross-section on one axis, gap at most the seam: stacked (same s span) or in a row (same z span)."""
    if a["type"] != "wall" or b["type"] != "wall":
        return False
    if a["u"] @ b["u"] < AXIS_COS or abs(a["c"] - b["c"]) > SAME_M or abs(a["out"] - b["out"]) > SAME_M:
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
    elements = [dict(p, pieces=1, ids=set(p["ids"])) for p in pieces]
    changed = True
    while changed:
        changed = False
        for i in range(len(elements)):
            for j in range(i + 1, len(elements)):
                a, b = elements[i], elements[j]
                if _joinable(a, b, seam):
                    a.update(s0=min(a["s0"], b["s0"]), s1=max(a["s1"], b["s1"]), z0=min(a["z0"], b["z0"]),
                             z1=max(a["z1"], b["z1"]), li=min(a["li"], b["li"]), pieces=a["pieces"] + b["pieces"],
                             embed=max(a["embed"], b["embed"]), ids=a["ids"] | b["ids"])
                    del elements[j]
                    changed = True
                    break
            if changed:
                break
    return elements


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
        ids = set(int(i) for i in np.unique(mats[part]))
        pc["ids"] = ids
        if pc["type"] in ("shape", "wall") and pc["out"] > DEEP_ASK_M:
            pc["type"] = "deep"
        if pc["type"] in ("shape", "deep"):
            questions.append({"priority": "low", "kind": f"decor-{pc['type']}", "levels": [levels[pc["li"]]["name"]],
                              "wall": None, "depth_m": round(pc["out"], 3), "length_m": round(pc["s1"] - pc["s0"], 3),
                              "facade_share": None, "heights_m": [round(pc["z0"], 3), round(pc["z1"], 3)],
                              "at": [round(float(c), 2) for c in v[np.unique(tris[part])][:, :2].mean(axis=0)]})
            continue
        found.append(pc)
    walls = _merge([p for p in found if p["type"] == "wall"], seam)
    columns = [dict(p, pieces=1) for p in found if p["type"] == "column"]
    decor = []
    for e in walls + columns:
        li = e["li"]
        lv = levels[li]
        mid = sorted(e["ids"])[0] if len(e["ids"]) == 1 and next(iter(e["ids"])) in attachment_ids else None
        entry = {"level": lv["name"], "z_m": round(e["z0"] - lv["elev_m"], 4), "h_m": round(e["z1"] - e["z0"], 4),
                 "material_id": mid, "pieces": e["pieces"]}
        if e["type"] == "column":
            x0, y0, x1, y1 = e["box"]
            decor.append({"kind": "column", **entry, "w_m": round(max(x1 - x0, y1 - y0), 4),
                          "footprint": [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]})
            continue
        # wall and x_m in the contour of the storey of its bottom
        best = None
        for w, (a, u, n, length) in enumerate(_walls(contours[li])):
            if u @ e["u"] >= AXIS_COS and abs(a @ n - e["c"]) <= SAME_M:
                best = (w, float(e["s0"] - a @ u))
        if best is None:                                  # its wall line is not a wall of that storey
            questions.append({"priority": "low", "kind": "decor-shape", "levels": [lv["name"]], "wall": None,
                              "depth_m": round(e["out"], 3), "length_m": round(e["s1"] - e["s0"], 3),
                              "facade_share": None, "heights_m": [round(e["z0"], 3), round(e["z1"], 3)], "at": None})
            continue
        w_m, h_m = e["s1"] - e["s0"], e["z1"] - e["z0"]
        kind = "band" if w_m >= BAND_RATIO * h_m else "strip" if h_m >= BAND_RATIO * w_m else "panel"
        out = round(e["out"], 4)
        decor.append({"kind": kind, **entry, "wall": best[0], "x_m": round(best[1], 4), "w_m": round(w_m, 4),
                      "projection_m": out, "texture": out <= DECOR_TEXTURE_M + 1e-9})
    decor.sort(key=lambda d: ([lv["name"] for lv in levels].index(d["level"]), d.get("wall") or 0,
                              d.get("x_m") or 0.0, d["z_m"]))
    report = {"pieces": len(found), "elements": len(decor), "texture": sum(d.get("texture", False) for d in decor),
              "columns": len(columns), "seam_m": round(seam, 4), "not_decor_parts": kept,
              "questions": len(questions)}
    return decor, questions, report

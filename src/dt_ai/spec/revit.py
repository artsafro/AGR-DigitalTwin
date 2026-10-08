"""Revit data -> the mesh dump the spec extractor reads (issue #10). Pure Python.

Pattern: none — extractor code (REVIEW_CHECKLIST Q1: new-case).

Neither Revit MCP route exposes wall location lines (user decision 2026-10-08), so geometry comes
from bounding boxes: every wall and roof becomes a box (the body), a roof's top sits at its mean
covering height (bottom + volume / plan area), and every window and door becomes a vertical pane
in the middle plane of its box (an opening anchor, source `glass`), and so does every curtain wall
(system family Витраж / Curtain Wall: its box holds mullion and frame depth, not a facade face).
A wall runs along X or Y only when its box's short side equals its width (type parameter) and its
long side is at least its length (joins extend the box past the location line's ends). The width
is the proof: a wall of length L and width w at angle t has a short side w*cos(t) + L*sin(t), so a
turn the tolerance hides moves the wall by at most LENGTH_TOL_M; the length alone proves nothing
(PR #30 review 1: 10 x 1 m at 10 degrees has a long side within 2 cm of its length). Any other
wall stops the extraction with a question and is never approximated. A curtain wall has no width
and its box holds frame depth, so its box proves nothing (PR #30 review 2: 2.41 x 1 m at 45 degrees
has both box sides equal to its length). Revit embeds a curtain wall in a host wall along the
host's line, so its axis is the one where a box side equals its length AND the line through the
box middle lies inside a parallel proven wall over the curtain wall's height; exactly one such axis, or a question. It becomes an
opening anchor along that axis and never shapes the contour. The result goes through the same
`extract_spec` as a scanned mesh.
"""
FT = 0.3048
CURTAIN_FAMILIES = {"Витраж", "Curtain Wall"}   # Revit system family of curtain walls (RU / EN)
LENGTH_TOL_M = 0.05       # a box side equals the wall width / length within this


class RevitDataError(ValueError):
    pass


def _box(name, lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return {"name": name, "vertices": v, "triangles": [t for a, b, c, d in quads for t in ([a, b, c], [a, c, d])]}


def _pane(name, lo, hi, along_x=None):
    """A vertical pane in the middle plane of a box, along X or Y (default: along its long side)."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    if along_x if along_x is not None else x1 - x0 >= y1 - y0:
        y = (y0 + y1) / 2
        v = [[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]]
    else:
        x = (x0 + x1) / 2
        v = [[x, y0, z0], [x, y1, z0], [x, y1, z1], [x, y0, z1]]
    return {"name": name, "vertices": v, "triangles": [[0, 1, 2], [0, 2, 3]]}


def _m(p):
    return [p["x"] * FT, p["y"] * FT, p["z"] * FT]


def _hosted_axes(lo, hi, length, walls):
    """Axes (True = X) along which a curtain wall's box side equals its length and the middle plane
    of the box, over its full length and height, lies inside parallel proven wall boxes (its host,
    possibly stacked by height; PR #30 review 3: a wall below the curtain wall proves nothing)."""
    out = []
    for along_x in (True, False):
        a, b = (0, 1) if along_x else (1, 0)       # a: along the line, b: across it
        if abs(hi[a] - lo[a] - length) > LENGTH_TOL_M:
            continue
        mid = (lo[b] + hi[b]) / 2
        spans = sorted((wlo[2], whi[2]) for wlo, whi, wx in walls
                       if wx == along_x and wlo[a] - LENGTH_TOL_M <= lo[a] and hi[a] <= whi[a] + LENGTH_TOL_M
                       and wlo[b] - LENGTH_TOL_M <= mid <= whi[b] + LENGTH_TOL_M)
        top = lo[2]                              # host walls may be stacked (cladding by height bands)
        for z0, z1 in spans:
            if z0 - LENGTH_TOL_M <= top:
                top = max(top, z1)
        if top >= hi[2] - LENGTH_TOL_M:
            out.append(along_x)
    return out


def to_dump(data):
    """The mesh dump of revit-data (tools/source/measure_spec_revit.mjs): body boxes and panes."""
    if data.get("kind") != "revit-data":
        raise RevitDataError("not revit-data")
    meshes, body, skew, walls, curtains = [], [], [], [], []
    for e in data["elements"]:
        lo, hi = _m(e["bbox_ft"]["min"]), _m(e["bbox_ft"]["max"])
        dx, dy = hi[0] - lo[0], hi[1] - lo[1]
        if e["category"] == "OST_Walls":
            length, width = (e.get("length_ft") or 0.0) * FT, (e.get("width_ft") or 0.0) * FT
            if e.get("family") in CURTAIN_FAMILIES:     # glazing, placed after its host walls are known
                curtains.append((e["id"], lo, hi, length))
                continue
            if not (length > 0 and width > 0 and max(dx, dy) >= length - LENGTH_TOL_M
                    and abs(min(dx, dy) - width) <= LENGTH_TOL_M):
                skew.append(e["id"])
                continue
            walls.append((lo, hi, dx >= dy))
            name = f"wall_{e['id']}"
            meshes.append(_box(name, lo, hi))
            body.append(name)
        elif e["category"] == "OST_Roofs":
            plan = dx * dy
            volume = (e.get("volume_ft3") or 0.0) * FT ** 3
            if plan <= 0 or volume <= 0:
                continue
            top = min(hi[2], lo[2] + volume / plan)      # mean covering top: bottom + volume / plan area
            name = f"roof_{e['id']}"
            meshes.append(_box(name, lo, [hi[0], hi[1], top]))
            body.append(name)
        elif e["category"] in ("OST_Windows", "OST_Doors"):
            meshes.append(_pane(f"glass_{e['category'][4:-1].lower()}_{e['id']}", lo, hi))
    for i, lo, hi, length in curtains:
        axes = _hosted_axes(lo, hi, length, walls) if length > 0 else []
        if len(axes) == 1:
            meshes.append(_pane(f"glass_curtain_{i}", lo, hi, along_x=axes[0]))
        else:
            skew.append(i)
    if skew:
        raise RevitDataError(f"{len(skew)} walls are not proven to run along X or Y — box is not length x width, or a "
                             "curtain wall not along one proven host wall "
                             f"(ids {skew[:10]}): wall location lines are not available from Revit here (#29), "
                             "so they are not approximated; ask the user")
    return {"source": data.get("source", "revit"), "document": data.get("document"), "units": "m",
            "meshes": meshes, "helpers": [], "body": body}

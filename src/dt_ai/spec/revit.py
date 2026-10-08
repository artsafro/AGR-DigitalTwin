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
wall stops the extraction with a question and is never approximated. A curtain wall has no width:
one box side must equal its length; it becomes an opening anchor and never shapes the contour. The result goes through the same `extract_spec` as a scanned mesh.
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


def _pane(name, lo, hi):
    """A vertical pane in the middle plane of a box, across its thin side."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    if x1 - x0 >= y1 - y0:
        y = (y0 + y1) / 2
        v = [[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]]
    else:
        x = (x0 + x1) / 2
        v = [[x, y0, z0], [x, y1, z0], [x, y1, z1], [x, y0, z1]]
    return {"name": name, "vertices": v, "triangles": [[0, 1, 2], [0, 2, 3]]}


def _m(p):
    return [p["x"] * FT, p["y"] * FT, p["z"] * FT]


def to_dump(data):
    """The mesh dump of revit-data (tools/source/measure_spec_revit.mjs): body boxes and panes."""
    if data.get("kind") != "revit-data":
        raise RevitDataError("not revit-data")
    meshes, body, skew = [], [], []
    for e in data["elements"]:
        lo, hi = _m(e["bbox_ft"]["min"]), _m(e["bbox_ft"]["max"])
        dx, dy = hi[0] - lo[0], hi[1] - lo[1]
        if e["category"] == "OST_Walls":
            length, width = (e.get("length_ft") or 0.0) * FT, (e.get("width_ft") or 0.0) * FT
            curtain = e.get("family") in CURTAIN_FAMILIES
            if curtain:    # mullion and frame depth may exceed a short curtain wall's length
                along = length > 0 and min(abs(dx - length), abs(dy - length)) <= LENGTH_TOL_M
            else:
                along = (length > 0 and width > 0 and max(dx, dy) >= length - LENGTH_TOL_M
                         and abs(min(dx, dy) - width) <= LENGTH_TOL_M)
            if not along:
                skew.append(e["id"])
                continue
            if curtain:    # a curtain wall is glazing: its box carries mullion and frame depth, not a facade face
                meshes.append(_pane(f"glass_curtain_{e['id']}", lo, hi))
                continue
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
    if skew:
        raise RevitDataError(f"{len(skew)} walls are not proven to run along X or Y — box is not length x width "
                             f"(ids {skew[:10]}): wall location lines are not available from Revit here (#29), "
                             "so they are not approximated; ask the user")
    return {"source": data.get("source", "revit"), "document": data.get("document"), "units": "m",
            "meshes": meshes, "helpers": [], "body": body}

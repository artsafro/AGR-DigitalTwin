"""Revit floor exports -> the mesh dump the spec extractor reads (issue #29). Pure Python.

Pattern: none — extractor code (REVIEW_CHECKLIST Q1: new-case).

The TwinPack command `twin_export_floor` of the revit-http add-in (tools/source/measure_spec_revit_twin.mjs)
writes, per storey band, `floor.json` (exterior walls with location lines, thickness and heights;
openings with host, point, hand, width, sill and head; curtain panels; roofs) and `reference.obj`
(the elements' real geometry, named `<kind>_<revitId>`).

- body: every wall as a prism on its location line (line +- thickness / 2, and half the thickness
  past an end where another wall meets it, which fills the corner of a join; its heights),
  so a wall at any angle is read and no bounding box stands in for it (#29 replaces the box route
  of #10). Curtain walls are not body: their panels are glass and their host wall carries the
  facade; a curtain wall not embedded in an exterior wall is body on its own line. Revit may split
  a wall at a door, so every opening of an exterior wall is closed by a prism on its host line over
  its heights (the contour runs over openings; the opening itself comes from the records). Walls of
  every function are read: a model may mark facade layers as inner walls (KPP1 plinth cladding);
  the contour is the outer ring, and the extractor keeps only openings on it. Wall openings are not cut: the contour runs
  over them (pattern wall-from-contour) and openings come from the Revit records below. Roofs are
  their real geometry. A curved wall is its real geometry from reference.obj.
- glass: by material, not by name: curtain panels with a transparent material (real geometry) and
  one pane per window with a transparent material along its host (a grille in the window category
  is no glass); opaque panels are not read (point, hand,
  width; heights of the family box).
- doors: the door records (host line, point, hand, width, sill, head) go to the extractor as door
  openings; a door gets no pane.
- attachment (user decision 2026-10-08, #29): a wall or curtain wall mostly outside the convex hull
  of the main walls (walls whose stack reaches their band's top) whose own stack — the wall and the
  walls standing on it — ends below its band's top is not body (entrance frames, vestibules,
  portals) and becomes a question.
- Bands are exported with a 1 mm gap (top = next bottom - 1 mm); roof and panel vertices on a band
  top are moved up by that 1 mm so a parapet top is read at its level.
"""
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

TOP_TOL_M = 0.05          # a stack ends below the band top by more than this; walls stand on each other within it
STACK_SHARE = 0.5         # a wall stands on another when it covers this share of the other's footprint
BAND_GAP_M = 0.001        # twin_export_floor: band top = next band bottom - 1 mm
JOIN_TOL_M = 0.01         # another wall's plan within this of a wall end is a join
EMBED_SHARE = 0.9         # a curtain wall is embedded when this share of its line lies in an exterior wall
OUTSIDE_SHARE = 0.5       # an attachment has more than this share of its plan outside the main walls' hull


class TwinDataError(ValueError):
    pass


def _obj(text):
    """Objects of an OBJ text: {name: (vertices, triangles)} with local vertex indices."""
    verts, objects, name = [], {}, None
    for line in text.splitlines():
        if line.startswith("v "):
            verts.append([float(c) for c in line.split()[1:4]])
        elif line.startswith("o "):
            name = line[2:].strip()
            objects.setdefault(name, [])
        elif line.startswith("f ") and name is not None:
            idx = [int(c.split("/")[0]) for c in line.split()[1:]]
            idx = [i - 1 if i > 0 else len(verts) + i for i in idx]
            objects[name].extend([idx[0], idx[k], idx[k + 1]] for k in range(1, len(idx) - 1))
    out = {}
    for name, tris in objects.items():
        used = sorted({i for t in tris for i in t})
        local = {g: n for n, g in enumerate(used)}
        out[name] = ([list(verts[g]) for g in used], [[local[i] for i in t] for t in tris])
    return out


def _footprint(w, cap="flat"):
    """Plan of a wall: its location line +- thickness / 2; cap "square" also runs half the thickness
    past both ends, as Revit extends joined walls into their corner."""
    return LineString([p[:2] for p in w["locationLine"]]).buffer(w["thickness"] / 2, cap_style=cap, join_style="mitre")


def _occupied(parts):
    """The plan a wall's real geometry occupies: the union of its triangles seen from above."""
    polys = []
    for m in parts:
        v = m["vertices"]
        for a, b, c in m["triangles"]:
            t = Polygon([v[a][:2], v[b][:2], v[c][:2]])
            if t.area > 1e-9:
                polys.append(t)
    return unary_union(polys).buffer(0) if polys else Polygon()


def attachments(bands, native=None):
    """Ids of walls and curtain walls that are attachments (module docstring): mostly outside the
    convex hull of the main walls — walls whose stack reaches their band's top — and with a stack
    that ends below the band top. Walls of every function: a model may mark facade layers as inner
    walls (KPP1 plinth cladding)."""
    native = native or {}                        # curved walls: their occupied plan (PR #35 review 2)
    walls = [(b["band"]["top"], w) for b in bands for w in b["walls"]]
    foot = {w["id"]: native[w["id"]] if w["id"] in native else _footprint(w) for _, w in walls}
    on = {w["id"]: [o for _, o in walls if o["id"] != w["id"] and abs(o["bboxMin"][2] - w["bboxMax"][2]) <= TOP_TOL_M
                    and foot[o["id"]].intersection(foot[w["id"]]).area >= STACK_SHARE * foot[w["id"]].area]
          for _, w in walls}

    def stack_top(w, seen=()):
        return max([w["bboxMax"][2]] + [stack_top(o, seen + (w["id"],)) for o in on[w["id"]] if o["id"] not in seen])

    short = {w["id"] for top, w in walls if stack_top(w) < top - TOP_TOL_M}
    main = [foot[w["id"]] for _, w in walls if w["id"] not in short and w.get("function") != "curtain"]
    if not main:
        return []
    hull = unary_union(main).convex_hull
    return sorted(i for i in short if foot[i].area > 0 and foot[i].difference(hull).area > OUTSIDE_SHARE * foot[i].area)


def _pane(o):
    """A vertical pane of a window along its host: point +- hand * width / 2, family box heights.
    A window without an insertion point (hosted in a frame wall) is centred in its family box."""
    centre = o.get("point") or [(o["bboxMin"][k] + o["bboxMax"][k]) / 2 for k in range(3)]
    (px, py, _), (hx, hy, _) = centre, o["hand"]
    half = o["width"] / 2
    z0, z1 = o["bboxMin"][2], o["bboxMax"][2]
    a, b = (px - hx * half, py - hy * half), (px + hx * half, py + hy * half)
    return {"name": f"glass_window_{o['id']}", "vertices": [[*a, z0], [*b, z0], [*b, z1], [*a, z1]],
            "triangles": [[0, 1, 2], [0, 2, 3]]}


def _ends(w, others):
    """How far the wall runs past each end of its location line: half its thickness where another
    wall meets that end (a Revit join fills the corner), nothing at a free end (PR #35 review 1)."""
    out = []
    for p in (w["locationLine"][0], w["locationLine"][-1]):
        end = Point(p[:2])
        out.append(w["thickness"] / 2 if any(f.distance(end) <= JOIN_TOL_M for f in others) else 0.0)
    return out


def _prism(name, w, ends=(0.0, 0.0)):
    """A wall as a closed prism on its location line, +- thickness / 2, run past its ends by `ends`,
    over its heights."""
    (x0, y0), (x1, y1) = [p[:2] for p in w["locationLine"][:1] + w["locationLine"][-1:]]
    length = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    line = LineString([(x0 - ux * ends[0], y0 - uy * ends[0]), (x1 + ux * ends[1], y1 + uy * ends[1])])
    ring = list(line.buffer(w["thickness"] / 2, cap_style="flat", join_style="mitre").exterior.coords)[:-1]
    z0, z1 = w["bboxMin"][2], w["bboxMax"][2]
    n = len(ring)
    verts = [[x, y, z0] for x, y in ring] + [[x, y, z1] for x, y in ring]
    tris = [[0, k + 1, k] for k in range(1, n - 1)] + [[n, n + k, n + k + 1] for k in range(1, n - 1)]
    for k in range(n):
        j = (k + 1) % n
        tris += [[k, j, n + j], [k, n + j, n + k]]
    return {"name": name, "vertices": verts, "triangles": tris}


def _plug(name, line, thickness, z0, z1):
    """A prism over an opening or a free curtain wall on its line: the contour runs over openings."""
    return _prism(name, {"locationLine": line, "thickness": thickness, "bboxMin": [0, 0, z0], "bboxMax": [0, 0, z1]})


def _span(o):
    """Ends of an opening on its host line: point +- hand * width / 2 (family box centre without a point)."""
    centre = o.get("point") or [(o["bboxMin"][k] + o["bboxMax"][k]) / 2 for k in range(3)]
    (px, py, _), (hx, hy, _) = centre, o["hand"]
    half = o["width"] / 2
    return [[px - hx * half, py - hy * half, 0.0], [px + hx * half, py + hy * half, 0.0]]


def _door(o, walls):
    """A door record as a door opening in the object system: its span on the host line."""
    (px, py, _), (hx, hy, _) = o["point"], o["hand"]
    half = o["width"] / 2
    host = walls.get(o.get("hostId"))
    base = o["bboxMin"][2] - o.get("sill", 0.0)              # the level the sill is measured from
    return {"revit_id": o["id"], "p0": [px - hx * half, py - hy * half], "p1": [px + hx * half, py + hy * half],
            "z0": base + o.get("sill", 0.0), "z1": base + (o.get("head") or o["height"]),
            "depth": host["thickness"] if host else 0.0,
            "host_line": [p[:2] for p in host["locationLine"]] if host else None,
            "host_thickness": host["thickness"] if host else None}


def _clear(band):
    """Ids of the band's transparent materials (glass), from the export's material table."""
    return {m["revitId"] for m in band.get("materials", {}).values() if m.get("transparency", 0) > 0 and "revitId" in m}


def to_dump(bands, objs, document=None):
    """The mesh dump of the band exports: bands = floor.json dicts, objs = their reference.obj texts."""
    if not bands:
        raise TwinDataError("no band exports")
    for b in bands:
        if b.get("schema") != "twin-floor/1":
            raise TwinDataError(f"not a twin_export_floor result: {b.get('schema')}")
    walls = {}
    for b in bands:                              # a wall through several bands is exported in each
        for w in b["walls"]:
            walls.setdefault(w["id"], w)
    objects = [_obj(text) for text in objs]
    curved = {i for i, w in walls.items() if w.get("curved") or len(w["locationLine"]) != 2}
    native = {}                                  # a curved wall is its real geometry from the export
    for b, obj in zip(bands, objects):
        for name, (verts, tris) in obj.items():
            kind, _, rid = name.partition("_")
            if kind == "wall" and int(rid) in curved:
                native.setdefault(int(rid), []).append({"name": f"wall_{rid}_b{b['band']['band']}",
                                                        "vertices": verts, "triangles": tris})
    missing = sorted(curved - set(native))
    if missing:
        raise TwinDataError(f"{len(missing)} curved walls without geometry in reference.obj (ids {missing[:10]}); ask the user")
    occupied = {i: _occupied(parts) for i, parts in native.items()}
    attached = set(attachments(bands, occupied))
    meshes, body, doors = [], [], {}
    outer = [_footprint(w, "square").buffer(0.01) for w in walls.values() if w.get("function") != "curtain"]
    plans = {i: _footprint(w) for i, w in walls.items() if w.get("function") != "curtain" and i not in curved}
    plans.update(occupied)                        # a curved wall's occupied plan for the joins of its neighbours
    for i, w in walls.items():
        if w.get("function") == "curtain":       # glazing: its panels are glass; its host carries the facade
            if i in attached:
                continue
            line = LineString([p[:2] for p in w["locationLine"]])
            if not any(f.intersection(line).length >= EMBED_SHARE * line.length for f in outer):
                meshes.append(_prism(f"curtain_{i}", w))     # a free curtain wall stands in the facade line
                body.append(f"curtain_{i}")
            continue
        if i in curved:
            meshes.extend(native[i])
            if i not in attached:
                body.extend(m["name"] for m in native[i])
            continue
        name = f"attachment_{i}" if i in attached else f"wall_{i}"
        meshes.append(_prism(name, w, _ends(w, [f for j, f in plans.items() if j != i])))
        if i not in attached:
            body.append(name)
    for b, obj in zip(bands, objects):
        top = b["band"]["top"]
        clear = _clear(b)
        glazed = {p["id"] for p in b.get("curtainPanels", []) if clear.intersection(p.get("materials", []))}
        for name, (verts, tris) in obj.items():
            kind, _, rid = name.partition("_")
            if kind not in ("roof", "panel") or (kind == "panel" and int(rid) not in glazed):
                continue                         # walls are prisms; opaque panels, mullions, families, slabs are not read
            for v in verts:                      # close the 1 mm band gap
                if abs(v[2] - top) <= 1e-6:
                    v[2] = top + BAND_GAP_M
            mesh_name = f"{'glass_' if kind == 'panel' else ''}{name}_b{b['band']['band']}"
            meshes.append({"name": mesh_name, "vertices": verts, "triangles": tris})
            if kind == "roof":
                body.append(mesh_name)
        for o in b["openings"]:
            host = walls.get(o.get("hostId"))
            if host is None:
                continue
            if host.get("function") != "curtain" and o.get("hostId") not in attached:   # walls may be split at it
                plug = f"plug_{o['id']}"
                if plug not in body:
                    meshes.append(_plug(plug, _span(o), host["thickness"], o["bboxMin"][2], o["bboxMax"][2]))
                    body.append(plug)
            if o["kind"] == "window" and clear.intersection(o.get("materials", [])):
                meshes.append(_pane(o))         # a window without glass (a grille) is no opening anchor
            elif o["kind"] == "door" and "point" in o:
                doors.setdefault(o["id"], _door(o, walls))
    questions = []
    groups = []                                  # touching attachment elements are one attachment
    for i in sorted(attached):
        f = _footprint(walls[i]).buffer(0.01)
        hit = [g for g in groups if g["geom"].intersects(f)]
        for g in hit:
            groups.remove(g)
        groups.append({"geom": unary_union([f] + [g["geom"] for g in hit]),
                       "ids": [i] + [j for g in hit for j in g["ids"]]})
    for g in groups:
        ws = [walls[i] for i in sorted(g["ids"])]
        c = g["geom"].centroid
        box = g["geom"].minimum_rotated_rectangle.exterior.coords
        sides = sorted(LineString([box[k], box[k + 1]]).length for k in range(4))
        questions.append({"priority": "normal", "kind": "attachment", "wall": None,
                          "depth_m": round(sides[0], 3), "length_m": round(sides[-1], 3), "facade_share": None,
                          "heights_m": [round(min(w["bboxMin"][2] for w in ws), 3), round(max(w["bboxMax"][2] for w in ws), 3)],
                          "at": [round(c.x, 2), round(c.y, 2)], "revit_ids": sorted(g["ids"])})
    return {"source": "revit", "document": document, "units": "m", "meshes": meshes, "helpers": [], "body": body,
            "doors": list(doors.values()), "questions": questions}


def load(index_path):
    """Read a revit-twin index (measure_spec_revit_twin.mjs) and its band folders into a dump."""
    index_path = Path(index_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    bands, objs = [], []
    for band in index["bands"]:
        folder = index_path.parent / band["dir"]
        bands.append(json.loads((folder / "floor.json").read_text(encoding="utf-8")))
        objs.append((folder / "reference.obj").read_text(encoding="utf-8"))
    return {**to_dump(bands, objs, index.get("document")), "levels": index.get("levels", [])}

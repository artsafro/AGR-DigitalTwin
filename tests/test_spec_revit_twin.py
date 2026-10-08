"""Revit floor exports (twin_export_floor) as a spec source (issue #29). Synthetic data; not a real object."""
import json
import math

import pytest
from shapely.geometry import Polygon

from dt_ai.cli.main import main
from dt_ai.spec import SpecError, extract_spec
from dt_ai.spec.revit_twin import TwinDataError, attachments, to_dump

OBJ = {"id": "bench-synth-box", "frames": {"revit": {"to_object": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}},
       "levels": [{"name": "L0", "elev_m": 0.0}, {"name": "L1", "elev_m": 3.3}, {"name": "roof", "elev_m": 6.6}]}
BAND = {"band": 1, "level": "L0", "elevation": 0.0, "bottom": -0.5, "top": 7.199}


def wall(i, a, b, t=0.3, z0=0.0, z1=7.2, function="Interior"):
    """A wall on its location line a -> b (plan), thickness t; Interior by default, as KPP1 marks facade layers."""
    xs, ys = (a[0], b[0]), (a[1], b[1])
    return {"id": i, "kind": "wall", "function": function, "thickness": t, "curved": False,
            "locationLine": [[*a, 0.0], [*b, 0.0]], "bboxMin": [min(xs) - t, min(ys) - t, z0], "bboxMax": [max(xs) + t, max(ys) + t, z1],
            "type": "Wall"}


def ring(c=0.15, n=10.0, rot=0.0, z1=7.2):
    """Four 0.3 m walls whose outer faces are the square 0..n (location lines 0.15 inside), turned by rot degrees."""
    r = math.radians(rot)

    def t(p):
        return [round(p[0] * math.cos(r) - p[1] * math.sin(r), 9), round(p[0] * math.sin(r) + p[1] * math.cos(r), 9)]
    pts = [(c, c), (n - c, c), (n - c, n - c), (c, n - c)]
    return [wall(k + 1, t(pts[k]), t(pts[(k + 1) % 4]), z1=z1) for k in range(4)], t


def roof_obj(t, n=10.0, z0=6.5, z1=6.6, name="roof_20"):
    """A roof slab as an OBJ object (a closed box) over the whole plan, under the parapet."""
    q = [t((0.0, 0.0)), t((n, 0.0)), t((n, n)), t((0.0, n))]
    lines = [f"o {name}"] + [f"v {x} {y} {z}" for z in (z0, z1) for x, y in q]
    faces = [(1, 4, 3, 2), (5, 6, 7, 8), (1, 2, 6, 5), (2, 3, 7, 6), (3, 4, 8, 7), (4, 1, 5, 8)]
    return "\n".join(lines + [f"f {a} {b} {c} {d}" for a, b, c, d in faces]) + "\n"


def band(walls, openings=(), band_=BAND):
    return {"schema": "twin-floor/1", "band": band_, "walls": walls, "openings": list(openings), "curtainPanels": []}


def spec_of(walls, openings=(), extra_obj="", rot=0.0):
    _, t = ring(rot=rot)
    return extract_spec(to_dump([band(walls, openings)], [roof_obj(t) + extra_obj]), OBJ)


def contour(spec, level=0):
    return Polygon([p[:2] for p in spec.expanded_floors()[level].contour])


def test_walls_at_an_angle_are_read_on_their_location_lines():
    walls, t = ring(rot=30.0)
    spec, _ = spec_of(walls, rot=30.0)
    assert contour(spec).area == pytest.approx(100.0, abs=0.01)
    assert contour(spec).symmetric_difference(Polygon([t((0, 0)), t((10, 0)), t((10, 10)), t((0, 10))])).area < 0.01


def test_inner_function_facade_layer_is_body():
    # KPP1 marks plinth cladding and outer concrete walls as Interior: the function never decides body
    walls, _ = ring()
    spec, _ = spec_of(walls)
    assert contour(spec).area == pytest.approx(100.0, abs=0.01)


def door(i, x0, x1, host, sill=0.0, head=2.1, family="Door"):
    return {"id": i, "kind": "door", "hostId": host, "family": family, "point": [(x0 + x1) / 2, 0.15, 0.0],
            "hand": [1, 0, 0], "width": x1 - x0, "height": head - sill, "sill": sill, "head": head,
            "bboxMin": [x0, -0.1, sill], "bboxMax": [x1, 0.4, head]}


def test_wall_split_at_a_door_is_closed_and_the_door_is_one_opening():
    # the south wall in two pieces with a door between them, recorded twice (door family + its wall opening)
    walls, _ = ring()
    walls[0:1] = [wall(1, (0.15, 0.15), (4.0, 0.15)), wall(5, (5.0, 0.15), (9.85, 0.15)),
                  wall(7, (4.0, 0.15), (5.0, 0.15), z0=2.1)]                 # the lintel over the door
    spec, report = spec_of(walls, [door(30, 4.0, 5.0, 1), door(31, 4.0, 5.0, 1, family="MEP opening")])
    assert contour(spec).area == pytest.approx(100.0, abs=0.01)
    o = spec.expanded_floors()[0].openings
    assert [(x.x_m, x.w_m, x.sill_m, x.h_m, x.kind) for x in o] == [(4.0, 1.0, 0.0, 2.1, "door")]


def test_inner_door_is_no_facade_opening():
    walls, _ = ring()
    inner = wall(6, (5.0, 0.3), (5.0, 9.7), t=0.12, z1=3.3)
    d = door(32, 3.0, 4.0, 6)
    d["point"], d["hand"] = [5.0, 3.5, 0.0], [0, 1, 0]
    spec, report = spec_of(walls + [inner], [d])
    assert spec.expanded_floors()[0].openings == [] and report["openings"]["source_doors_skipped"] == 1


def test_entrance_frame_outside_the_building_is_an_attachment_question():
    # a U frame 0.6 m out of the south facade, 2.7 m high in a 3.3 m storey: not body, one question
    walls, _ = ring()
    frame = [wall(40, (4.0, 0.0), (4.0, -0.6), t=0.14, z1=2.7), wall(41, (4.0, -0.6), (5.0, -0.6), t=0.14, z1=2.7),
             wall(42, (5.0, -0.6), (5.0, 0.0), t=0.14, z1=2.7)]
    b = band(walls + frame, band_={**BAND, "top": 3.299})
    assert attachments([b]) == [40, 41, 42]
    spec, report = spec_of(walls + frame)
    assert contour(spec).area == pytest.approx(100.0, abs=0.01)
    q = [x for x in report["questions"] if x["kind"] == "attachment"]
    assert len(q) == 1 and q[0]["revit_ids"] == [40, 41, 42] and q[0]["levels"] == ["L0"]


def test_wall_reaching_the_storey_top_outside_is_no_attachment():
    walls, _ = ring()
    tower = [wall(43, (4.0, 0.0), (4.0, -0.6), t=0.14, z1=7.2)]
    assert attachments([band(walls + tower)]) == []


def curtain(i, a, b, z0=0.0, z1=2.7):
    w = wall(i, a, b, t=0.025, z0=z0, z1=z1)
    w["function"] = "curtain"
    return w


def test_embedded_curtain_wall_is_glazing_not_body():
    walls, _ = ring()
    spec, _ = spec_of(walls + [curtain(50, (3.0, 0.02), (6.0, 0.02))])
    assert len(spec.expanded_floors()[0].contour) == 4        # no 2.5 mm step from the curtain line


def test_free_curtain_wall_closes_the_facade_line():
    walls, _ = ring()
    walls[0:1] = [wall(1, (0.15, 0.15), (3.0, 0.15)), wall(5, (6.0, 0.15), (9.85, 0.15))]
    spec, _ = spec_of(walls + [curtain(51, (3.0, 0.0125), (6.0, 0.0125), z1=7.2)])   # in the facade plane
    assert contour(spec).area == pytest.approx(100.0, abs=0.05)


def box_obj(name, x0, y0, x1, y1, z0, z1, offset=0):
    """A closed box as an OBJ object; offset = vertices written before it (OBJ indices run over the file)."""
    q = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    lines = [f"o {name}"] + [f"v {x} {y} {z}" for z in (z0, z1) for x, y in q]
    faces = [(1, 4, 3, 2), (5, 6, 7, 8), (1, 2, 6, 5), (2, 3, 7, 6), (3, 4, 8, 7), (4, 1, 5, 8)]
    return "\n".join(lines + [f"f {a + offset} {b + offset} {c + offset} {d + offset}" for a, b, c, d in faces]) + "\n"


def test_curved_wall_is_its_real_geometry():
    # the south wall flagged curved: read from reference.obj, not refused (PR #35 review 1)
    walls, t = ring()
    walls[0]["curved"] = True
    obj = roof_obj(t) + box_obj("wall_1", 0.0, 0.0, 10.0, 0.3, 0.0, 7.2, offset=8)
    dump = to_dump([band(walls)], [obj])
    assert "wall_1_b1" in dump["body"] and "wall_1" not in dump["body"]
    spec, _ = extract_spec(dump, OBJ)
    assert contour(spec).area == pytest.approx(100.0, abs=0.01)


def test_curved_wall_without_geometry_stops_with_a_question():
    walls, t = ring()
    walls[0]["curved"] = True
    with pytest.raises(TwinDataError, match="curved walls without geometry"):
        to_dump([band(walls)], [roof_obj(t)])


def test_free_wall_end_is_not_extended():
    # a wall with one free end: no half thickness invented past it (PR #35 review 1)
    walls, t = ring()
    stub = wall(60, (5.0, 9.7), (5.0, 8.0), t=0.2)              # meets the north wall at 9.7, free at 8.0
    dump = to_dump([band(walls + [stub])], [roof_obj(t)])
    ys = [v[1] for m in dump["meshes"] if m["name"] == "wall_60" for v in m["vertices"]]
    assert min(ys) == pytest.approx(8.0) and max(ys) == pytest.approx(9.8)


def test_door_of_an_attachment_adds_no_plug_to_the_body():
    walls, _ = ring()
    frame = [wall(40, (4.0, 0.0), (4.0, -0.6), t=0.14, z1=2.7), wall(41, (4.0, -0.6), (5.0, -0.6), t=0.14, z1=2.7),
             wall(42, (5.0, -0.6), (5.0, 0.0), t=0.14, z1=2.7)]
    d = door(33, 4.2, 4.8, 41)
    d["point"] = [4.5, -0.6, 0.0]
    dump = to_dump([band(walls + frame, [d])], [""])
    assert not any(n.startswith("plug_") for n in dump["body"])


def test_inner_door_parallel_to_the_facade_is_no_facade_opening():
    # an inner wall 0.6 m behind an intact south wall, with a door: the host is not on the facade
    walls, _ = ring()
    inner = wall(61, (0.3, 0.6), (9.7, 0.6), t=0.12, z1=3.3)
    d = door(34, 4.0, 5.0, 61)
    d["point"] = [4.5, 0.6, 0.0]
    spec, report = spec_of(walls + [inner], [d])
    assert spec.expanded_floors()[0].openings == [] and report["openings"]["source_doors_skipped"] == 1


def test_detached_lining_never_makes_a_roof_hole_a_shaft():
    # a 1 m2 hole in the roof, lined by Revit walls only at 4.85-5.05 m, 1.55 m below it: all walls are
    # body, so the lining must reach the upper part of the top storey (PR #35 reviews 1-2, P1)
    walls, t = ring()
    lining = [wall(70 + k, a, b, t=0.1, z0=4.85, z1=5.05) for k, (a, b) in enumerate(
        [((4.45, 4.45), (5.55, 4.45)), ((5.55, 4.45), (5.55, 5.55)), ((5.55, 5.55), (4.45, 5.55)), ((4.45, 5.55), (4.45, 4.45))])]
    outer, hole = [(0, 0), (10, 0), (10, 10), (0, 10)], [(4.5, 4.5), (5.5, 4.5), (5.5, 5.5), (4.5, 5.5)]
    roof = ["o roof_20"] + [f"v {x} {y} 6.6" for x, y in outer + hole]
    roof += [f"f {a + 1} {(a + 1) % 4 + 1} {(a + 1) % 4 + 5} {a + 5}" for a in range(4)]   # one surface around the hole
    dump = to_dump([band(walls + lining)], ["\n".join(roof) + "\n"])
    assert all(f"wall_{70 + k}" in dump["body"] for k in range(4))
    with pytest.raises(SpecError, match="not a shaft"):
        extract_spec(dump, OBJ)
    for w in lining:                                 # the same lining up to the roof is a shaft
        w["bboxMin"][2], w["bboxMax"][2] = 3.3, 6.6
    spec, report = extract_spec(to_dump([band(walls + lining)], ["\n".join(roof) + "\n"]), OBJ)
    assert report["roof"]["closed_share"] >= 0.99


def arc_obj(name, cx, cy, r, t, z0, z1, a0, a1, n=32, offset=0):
    """A curved wall: a closed ring sector between radii r -+ t/2 from angle a0 to a1 (degrees)."""
    ang = [math.radians(a0 + (a1 - a0) * k / n) for k in range(n + 1)]
    ring_ = [(cx + (r + t / 2) * math.cos(a), cy + (r + t / 2) * math.sin(a)) for a in ang]
    ring_ += [(cx + (r - t / 2) * math.cos(a), cy + (r - t / 2) * math.sin(a)) for a in reversed(ang)]
    m = len(ring_)
    lines = [f"o {name}"] + [f"v {x} {y} {z}" for z in (z0, z1) for x, y in ring_]
    faces = [f"f {k + 1 + offset} {(k + 1) % m + 1 + offset} {(k + 1) % m + 1 + m + offset} {k + 1 + m + offset}" for k in range(m)]
    for k in range(n):                               # caps as strips (no triangle over the hollow side)
        o0, o1, i0, i1 = k, k + 1, m - 1 - k, m - 2 - k
        faces += [f"f {o0 + 1 + offset} {i0 + 1 + offset} {i1 + 1 + offset} {o1 + 1 + offset}",
                  f"f {o0 + 1 + m + offset} {o1 + 1 + m + offset} {i1 + 1 + m + offset} {i0 + 1 + m + offset}"]
    return "\n".join(lines + faces) + "\n"


def curved(i, cx, cy, r, t, a0, a1, z1):
    a, b = [(cx + r * math.cos(math.radians(x)), cy + r * math.sin(math.radians(x))) for x in (a0, a1)]
    w = wall(i, a, b, t=t, z1=z1)
    w["curved"] = True
    return w


def test_curved_attachment_outside_the_building_is_a_question():
    # a semicircular 0.14 m wall, 2.7 m high, in front of the south facade (PR #35 review 2)
    walls, t = ring()
    arc = curved(80, 5.0, 0.0, 1.0, 0.14, 180, 360, 2.7)
    b = band(walls + [arc], band_={**BAND, "top": 3.299})
    dump = to_dump([b], [roof_obj(t) + arc_obj("wall_80", 5.0, 0.0, 1.0, 0.14, 0.0, 2.7, 180, 360, offset=8)])
    assert "wall_80_b1" not in dump["body"] and [q["revit_ids"] for q in dump["questions"]] == [[80]]


def test_wall_end_near_a_curved_wall_is_not_extended_by_its_hull():
    # a stub ending inside the hull of a semicircle but 0.75 m from its strip (PR #35 review 2)
    walls, t = ring()
    arc = curved(81, 5.0, 5.0, 1.0, 0.14, 180, 360, 7.2)
    stub = wall(82, (5.0, 2.0), (5.0, 4.8), t=0.2)
    obj = roof_obj(t) + arc_obj("wall_81", 5.0, 5.0, 1.0, 0.14, 0.0, 7.2, 180, 360, offset=8)
    dump = to_dump([band(walls + [arc, stub])], [obj])
    ys = [v[1] for m in dump["meshes"] if m["name"] == "wall_82" for v in m["vertices"]]
    assert max(ys) == pytest.approx(4.8)


def test_inner_door_whose_host_reaches_the_facade_elsewhere_is_no_facade_opening():
    # the inner wall 0.6 m behind the south facade runs to the west facade; its door is not on the facade
    walls, _ = ring()
    inner = wall(62, (0.0, 0.6), (9.7, 0.6), t=0.12, z1=3.3)
    d = door(35, 4.0, 5.0, 62)
    d["point"] = [4.5, 0.6, 0.0]
    spec, report = spec_of(walls + [inner], [d])
    assert spec.expanded_floors()[0].openings == [] and report["openings"]["source_doors_skipped"] == 1


def test_cli_reads_a_twin_index(tmp_path):
    walls, t = ring()
    (tmp_path / "band-1").mkdir()
    (tmp_path / "band-1" / "floor.json").write_text(json.dumps(band(walls)), encoding="utf-8")
    (tmp_path / "band-1" / "reference.obj").write_text(roof_obj(t), encoding="utf-8")
    (tmp_path / "twin-data.json").write_text(json.dumps({"kind": "revit-twin", "source": "revit", "document": "synthetic",
                                                          "bands": [{"band": 1, "dir": "band-1"}]}), encoding="utf-8")
    (tmp_path / "object.json").write_text(json.dumps(OBJ), encoding="utf-8")
    out = tmp_path / "spec.json"
    assert main(["spec", "extract", "--dump", str(tmp_path / "twin-data.json"), "--object", str(tmp_path / "object.json"),
                 "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["frame"]["source"] == "revit"


def test_box_route_data_is_refused_with_the_new_route():
    # revit-data of #10 (bounding boxes) is no longer read
    with pytest.raises(SpecError, match="measure_spec_revit_twin"):
        extract_spec({"kind": "revit-data", "source": "revit", "elements": []}, OBJ)

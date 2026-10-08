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


def test_curved_wall_stops_with_a_question():
    walls, _ = ring()
    walls[0]["curved"] = True
    with pytest.raises(TwinDataError, match="curved walls"):
        to_dump([band(walls)], [""])


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

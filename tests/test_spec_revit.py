"""Revit data path of the spec extractor (issue #10). Synthetic revit-data; not a real object."""
import json
import math

import pytest

from dt_ai.cli.main import main
from dt_ai.spec import SpecError, extract_spec
from dt_ai.spec.revit import FT, to_dump

OBJ = {"id": "bench-synth-box", "frames": {"revit": {"to_object": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}},
       "levels": [{"name": "L0", "elev_m": 0.0}, {"name": "L1", "elev_m": 3.3}, {"name": "roof", "elev_m": 6.6}]}


def bbox(x0, y0, z0, x1, y1, z1):
    return {"min": {"x": x0 / FT, "y": y0 / FT, "z": z0 / FT}, "max": {"x": x1 / FT, "y": y1 / FT, "z": z1 / FT}}


def wall(i, x0, y0, x1, y1, top=7.2, length=None):
    length = length if length is not None else max(x1 - x0, y1 - y0)
    return {"id": i, "category": "OST_Walls", "type": "Wall 300", "bbox_ft": bbox(x0, y0, 0.0, x1, y1, top),
            "length_ft": length / FT}


def revit_box(extra=()):
    """A 10 x 10 m box of 0.3 m walls along X and Y, a window and a door on the south wall and a
    covering roof (6.5 -> 6.7, volume giving a mean top of 6.6)."""
    els = [wall(1, 0, 0, 10, 0.3), wall(2, 9.7, 0, 10, 10), wall(3, 0, 9.7, 10, 10), wall(4, 0, 0, 0.3, 10),
           {"id": 10, "category": "OST_Windows", "type": "W 1500", "bbox_ft": bbox(2.0, 0.0, 0.9, 3.5, 0.3, 2.4)},
           {"id": 11, "category": "OST_Doors", "type": "D 1000", "bbox_ft": bbox(5.0, 0.0, 0.0, 6.0, 0.3, 2.1)},
           {"id": 20, "category": "OST_Roofs", "type": "Covering", "bbox_ft": bbox(0.3, 0.3, 6.5, 9.7, 9.7, 6.7),
            "volume_ft3": 9.4 * 9.4 * 0.1 / FT ** 3}]
    return {"kind": "revit-data", "source": "revit", "document": "synthetic", "units": "ft",
            "levels": OBJ["levels"], "elements": els + list(extra)}


def test_revit_box_gives_contour_openings_and_roof():
    spec, report = extract_spec(revit_box(), OBJ)
    pts = spec.expanded_floors()[0].contour
    assert [p[:2] for p in pts] == [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    got = sorted((o.wall, o.x_m, o.sill_m, o.w_m, o.h_m, o.source) for o in spec.expanded_floors()[0].openings)
    assert got == [(0, 2.0, 0.9, 1.5, 1.5, "glass"), (0, 5.0, 0.0, 1.0, 2.1, "glass")]
    assert report["roof"]["plane_m"] == pytest.approx(6.6, abs=0.001)
    assert spec.roof.parapet_h_m == pytest.approx(0.6, abs=0.01)
    assert spec.frame.source == "revit"


def test_wall_not_along_x_or_y_stops_with_a_question():
    skew = {"id": 99, "category": "OST_Walls", "type": "Wall 300", "bbox_ft": bbox(0, 0, 0, 3, 3, 7.2),
            "length_ft": math.hypot(3, 3) / FT}
    with pytest.raises(SpecError, match="1 walls do not run along X or Y .*99"):
        extract_spec(revit_box([skew]), OBJ)


def test_roof_box_top_is_the_mean_covering_height():
    dump = to_dump(revit_box())
    roof = next(m for m in dump["meshes"] if m["name"] == "roof_20")
    assert max(v[2] for v in roof["vertices"]) == pytest.approx(6.6, abs=1e-6)
    assert "roof_20" in dump["body"] and not any(n.startswith("glass") for n in dump["body"])


def test_cli_reads_revit_data(tmp_path):
    data, obj, out = tmp_path / "revit-data.json", tmp_path / "object.json", tmp_path / "spec-v001.json"
    data.write_text(json.dumps(revit_box()), encoding="utf-8")
    obj.write_text(json.dumps(OBJ), encoding="utf-8")
    assert main(["spec", "extract", "--dump", str(data), "--object", str(obj), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["frame"]["source"] == "revit"


def test_curtain_wall_is_glazing_not_a_wall_box():
    # a curtain wall embedded in the south wall with a 1 m deep box (mullions and frames, as in KPP1):
    # as a box it would push the contour 0.5 m out; as glazing the contour stays on the facade
    curtain = {"id": 30, "category": "OST_Walls", "type": "Curtain", "family": "Витраж",
               "bbox_ft": bbox(7.0, -0.5, 0.0, 9.0, 0.5, 2.5), "length_ft": 2.0 / FT}
    spec, _ = extract_spec(revit_box([curtain]), OBJ)
    f = spec.expanded_floors()[0]
    assert [p[:2] for p in f.contour] == [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    assert (0, 7.0, 0.0, 2.0, 2.5, "glass") in [(o.wall, o.x_m, o.sill_m, o.w_m, o.h_m, o.source) for o in f.openings]
    assert not any("curtain" in n for n in to_dump(revit_box([curtain]))["body"])

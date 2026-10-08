"""Spec v0.3: an opening is the hole in the wall with its frame, glass is its attribute (issue #36,
user decision 2026-10-08). Synthetic data; not a real object."""
import json
from pathlib import Path

import pytest

from dt_ai.spec import extract_spec
from dt_ai.spec.model import Spec
from dt_ai.spec.revit_twin import to_dump
from test_spec_contour_shapes import at
from test_spec_openings import building, pane
from test_spec_revit_twin import OBJ, band, ring, roof_obj, wall

ROOT = Path(__file__).resolve().parents[1]


def ops(spec, level=0):
    return [(o.x_m, o.sill_m, o.w_m, o.h_m, o.glass_w, o.glass_h, o.panes, o.depth_m)
            for o in spec.expanded_floors()[level].openings]


def test_window_in_a_reveal_is_the_reveal_with_the_glass_as_attributes():
    # a 1.2 x 1.8 m recess 0.26 m deep (the hole with its frame) and a 0.94 x 1.56 m pane in it (KPP1 type)
    spec, report = extract_spec(building(boxes=[(0, 2.0, 3.2, 1.2, 3.0, -0.26)],
                                         extra=[pane("glass", 2.13, 3.07, 1.32, 2.88, y=0.2)]), at(L0=0.5))
    assert ops(spec) == [(2.0, 1.2, 1.2, 1.8, 0.94, 1.56, 1, None)]
    assert report["openings"]["rough_from_reveal"] == 1 and report["questions"] == []


def test_panes_in_one_reveal_are_one_opening():
    # two 0.785 m panes 0.19 m apart in one 1.9 m reveal (KPP1 L1 west)
    spec, _ = extract_spec(building(boxes=[(0, 2.0, 3.9, 1.0, 2.7, -0.26)],
                                    extra=[pane("glass", 2.06, 2.845, 1.07, 2.63, y=0.2),
                                           pane("glass2", 3.035, 3.82, 1.07, 2.63, y=0.2)]), at(L0=0.5))
    assert ops(spec) == [(2.0, 1.0, 1.9, 1.7, 1.76, 1.56, 2, None)]


def test_tall_recess_with_a_short_window_is_no_frame():
    # PR #20 F6: glass 1.0-1.2 in a recess 0.2-2.8: not its frame, the recess stays a question
    spec, report = extract_spec(building(boxes=[(0, 2.0, 3.5, 0.2, 2.8, -0.2)],
                                         extra=[pane("Glass", 2.0, 3.5, 1.0, 1.2, y=0.2)]), at(L0=0.1))
    assert ops(spec) == [(2.0, 1.0, 1.5, 0.2, 1.5, 0.2, 1, None)] and report["openings"]["rough_from_reveal"] == 0
    assert [q["kind"] for q in report["questions"]] == ["recess"]


def test_glass_without_a_reveal_is_its_own_size():
    spec, report = extract_spec(building(extra=[pane("glass", 2.0, 3.5, 1.32, 2.7, y=0.15)]), at())
    assert ops(spec) == [(2.0, 1.32, 1.5, 1.38, 1.5, 1.38, 1, None)] and report["openings"]["rough_from_reveal"] == 0


def test_reveal_cut_by_the_level_goes_on_above():
    # one frame through the L1 line: a reveal 1.2-4.6 m, glass 1.32-3.2 and 3.32-4.48 (KPP1 south)
    spec, _ = extract_spec(building(boxes=[(0, 2.0, 3.2, 1.2, 4.6, -0.26)],
                                    extra=[pane("glass", 2.13, 3.07, 1.32, 3.2, y=0.2),
                                           pane("glass2", 2.13, 3.07, 3.32, 4.48, y=0.2)]), at(L0=0.5, L1=5.0))
    (o,) = spec.expanded_floors()[0].openings
    assert (o.sill_m, o.h_m, o.level_to, o.panes) == (1.2, 3.4, "L1", 2)


def test_depth_is_written_only_as_an_exception():
    deep = building(boxes=[(0, 2.0, 3.2, 1.2, 3.0, -0.6)], extra=[pane("glass", 2.13, 3.07, 1.32, 2.88, y=0.55)])
    spec, _ = extract_spec(deep, at(L0=0.5))
    assert spec.expanded_floors()[0].openings[0].depth_m == pytest.approx(0.6, abs=0.01)   # 0.6 m reveal: exception
    spec, _ = extract_spec(deep, {**at(L0=0.5), "opening_depth_default_m": 0.6})
    assert spec.expanded_floors()[0].openings[0].depth_m is None and spec.opening_depth_default_m == 0.6


def panel(i, host, x0, x1, z0, z1, mat=2):
    return {"id": i, "kind": "panel", "hostId": host, "materials": [mat], "bboxMin": [x0, -0.01, z0], "bboxMax": [x1, 0.01, z1]}


GLASS = {"m1": {"revitId": 1, "transparency": 0}, "m2": {"revitId": 2, "transparency": 70}}


def test_revit_curtain_wall_is_one_opening_with_its_glazed_panels():
    walls, t = ring()
    curtain = wall(90, (3.0, 0.15), (6.0, 0.15), t=0.025, z0=1.0, z1=2.8)
    curtain["function"] = "curtain"
    b = {**band(walls + [curtain]), "materials": GLASS,
         "curtainPanels": [panel(91, 90, 3.05, 4.45, 1.05, 2.75), panel(92, 90, 4.55, 5.95, 1.05, 2.75),
                           panel(93, 90, 3.05, 5.95, 2.75, 2.8, mat=1)]}           # an opaque panel is no glass
    spec, _ = extract_spec(to_dump([b], [roof_obj(t)]), OBJ)
    assert ops(spec) == [(3.0, 1.0, 3.0, 1.8, 2.9, 1.7, 2, None)]


def test_revit_grille_is_no_opening():
    walls, t = ring()
    grille = {"id": 94, "kind": "window", "hostId": 1, "materials": [1], "hand": [1, 0, 0], "width": 0.3, "height": 0.4,
              "bboxMin": [4.0, 0.0, 3.0], "bboxMax": [4.3, 0.3, 3.4]}
    dump = to_dump([{**band(walls, [grille]), "materials": GLASS}], [roof_obj(t)])
    assert dump["openings"] == [] and dump["grilles_not_openings"] == 1


def test_b01_example_is_spec_v03_and_matches_harness_plan():
    # the spec example of HARNESS_PLAN §3 and its fixture are the same document and valid v0.3
    fixture = json.loads((ROOT / "tests" / "fixtures" / "spec-b01-v0.3.json").read_text(encoding="utf-8"))
    plan = (ROOT / "docs" / "HARNESS_PLAN.md").read_text(encoding="utf-8")
    block = plan[plan.index("```json", plan.index("## 3.")) + 7:]
    assert json.loads(block[:block.index("```")]) == fixture
    spec = Spec.model_validate(fixture)
    assert spec.spec_version == "0.3" and spec.floors[0].openings[0].glass_w is not None


def test_v02_spec_still_needs_its_depth():
    doc = json.loads((ROOT / "tests" / "fixtures" / "spec-b01-v0.3.json").read_text(encoding="utf-8"))
    doc["spec_version"] = "0.2"
    with pytest.raises(ValueError):
        Spec.model_validate(doc)

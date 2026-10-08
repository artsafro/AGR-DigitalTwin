"""Door recesses, relief and panes of one frame (issue #31, user decisions 2026-10-08).
Synthetic data; not a real object."""
import pytest

from dt_ai.spec import extract_spec
from test_spec_contour_shapes import SQUARE10, at
from test_spec_extract import close
from test_spec_openings import building, pane


def doors(spec, level=0):
    return [(o.wall, o.x_m, o.sill_m, o.w_m, o.h_m, o.depth_m, o.source)
            for o in spec.expanded_floors()[level].openings if o.kind == "door"]


def test_recess_from_the_floor_is_a_door_and_leaves_the_contour():
    # KPP1: door recesses 0.23 m deep, 2.1 m high, cut by the contour height 0.5 m
    spec, report = extract_spec(building(boxes=[(0, 4.0, 5.0, 0.0, 2.1, -0.23)]), at(L0=0.5))
    assert close(spec.expanded_floors()[0].contour, SQUARE10)
    assert doors(spec) == [(0, 4.0, 0.0, 1.0, 2.1, 0.23, "hole")]
    assert report["floors"]["L0"]["door_recesses"] == 1 and report["questions"] == []


@pytest.mark.parametrize("box, why", [
    ((0, 4.0, 5.0, 0.9, 2.4, -0.23), "not from the floor"),
    ((0, 4.0, 5.0, 0.0, 1.5, -0.23), "lower than 1.9 m"),
    ((0, 4.0, 4.5, 0.0, 2.1, -0.23), "narrower than 0.7 m"),
    ((0, 3.0, 6.5, 0.0, 2.1, -0.23), "wider than 3 m"),
])
def test_other_recesses_are_not_doors(box, why):
    spec, report = extract_spec(building(boxes=[box]), at(L0=1.0))
    assert doors(spec) == [], why
    assert report["floors"]["L0"]["door_recesses"] == 0


def test_depth_is_no_criterion():
    spec, _ = extract_spec(building(boxes=[(0, 4.0, 5.0, 0.0, 2.1, -1.5)]), at(L0=0.5))
    assert doors(spec) == [(0, 4.0, 0.0, 1.0, 2.1, 1.5, "hole")]


def test_outward_band_from_the_floor_is_no_door():
    # a 1 m porch block 0-2.1 m in front of the wall: lined on one side only, stays a question
    spec, report = extract_spec(building(boxes=[(0, 4.0, 5.0, 0.0, 2.1, 0.5)]), at(L0=3.0))
    assert doors(spec) == [] and [q["kind"] for q in report["questions"]] == ["projection"]


def test_frame_profile_is_relief_not_a_kink():
    # KPP1 L1: profiles 0.075 x 0.09 m out of the facade over the whole storey
    bumped = [[0, 0], [10, 0], [10, 10], [5.075, 10], [5.075, 10.09], [5, 10.09], [5, 10], [0, 10]]
    spec, report = extract_spec(building(contour=bumped), {**at(), "contour_at_m": {}})
    assert close(spec.expanded_floors()[0].contour, SQUARE10)
    assert report["floors"]["L0"]["relief_parts"] == 1


def test_thin_deep_fin_is_not_relief():
    finned = [[0, 0], [10, 0], [10, 10], [5.075, 10], [5.075, 10.5], [5, 10.5], [5, 10], [0, 10]]
    spec, report = extract_spec(building(contour=finned), {**at(), "contour_at_m": {}})
    assert len(spec.expanded_floors()[0].contour) == 8 and report["floors"]["L0"]["relief_parts"] == 0


def test_transom_over_a_window_is_one_opening_with_two_panes():
    # KPP1 L0: 0.94 m pane 1.32-2.005 and a 1.08 m transom 2.125-3.2 (gap 0.12 m) in one frame
    spec, _ = extract_spec(building(extra=[pane("glass", 2.07, 3.01, 1.32, 2.005), pane("glass2", 2.0, 3.08, 2.125, 3.2)]),
                           at())
    o = spec.expanded_floors()[0].openings
    assert [(x.x_m, x.sill_m, x.w_m, x.h_m, x.panes, x.kind) for x in o] == [(2.0, 1.32, 1.08, 1.88, 2, "window")]


def test_panes_further_than_0_15_m_apart_are_two_openings():
    spec, _ = extract_spec(building(extra=[pane("glass", 2.0, 2.785, 1.0, 2.5), pane("glass2", 2.975, 3.76, 1.0, 2.5)]), at())
    assert [(x.x_m, x.panes) for x in spec.expanded_floors()[0].openings] == [(2.0, 1), (2.975, 1)]

"""Door recesses, relief and panes of one frame (issue #31, user decisions 2026-10-08).
Synthetic data; not a real object."""
import pytest
from shapely.geometry import Polygon, box

from dt_ai.spec import extract_spec
from dt_ai.spec.mesh import _door_recesses
from dt_ai.spec.model import Spec
from test_spec_contour_shapes import SQUARE10, at
from test_spec_extract import Mesh, close
from test_spec_openings import building, pane


def doors(spec, level=0):
    return [(o.wall, o.x_m, o.sill_m, o.w_m, o.h_m, o.depth_m, o.source)
            for o in spec.expanded_floors()[level].openings if o.kind == "door"]


def test_recess_from_the_floor_is_a_door_and_leaves_the_contour():
    # KPP1: door recesses 0.23 m deep, 2.1 m high, cut by the contour height 0.5 m
    spec, report = extract_spec(building(boxes=[(0, 4.0, 5.0, 0.0, 2.1, -0.23)]), at(L0=0.5))
    assert close(spec.expanded_floors()[0].contour, SQUARE10)
    assert doors(spec) == [(0, 4.0, 0.0, 1.0, 2.1, None, "hole")]
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
    # profiles 0.075 x 0.09 m out of the facade over the whole storey
    bumped = [[0, 0], [10, 0], [10, 10], [5.075, 10], [5.075, 10.09], [5, 10.09], [5, 10], [0, 10]]
    spec, report = extract_spec(building(contour=bumped), {**at(), "contour_at_m": {}})
    assert close(spec.expanded_floors()[0].contour, SQUARE10)
    assert report["floors"]["L0"]["relief_parts"] == 1


@pytest.mark.parametrize("box, relief", [
    ((0, 2.0, 6.0, 1.125, 1.2, 0.09), True),     # frame rail 0.09 deep, 0.075 high (KPP1 cassettes)
    ((0, 2.0, 6.0, 1.125, 1.2, -0.09), True),    # groove of the same section
    ((0, 2.0, 6.0, 1.0, 1.5, 0.09), False),      # 0.5 m high band
    ((0, 2.0, 6.0, 1.125, 1.2, 0.15), False),    # 0.15 m deep
])
def test_band_with_both_section_sizes_small_is_relief_not_a_question(box, relief):
    # user decision 2026-10-09: the relief rule of #31 also holds in section (depth and height)
    _, report = extract_spec(building(boxes=[box]), at())
    assert (report["questions"] == []) == relief
    assert report["section_relief_parts"] == (1 if relief else 0)


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



# PR #33 review 1 and user decisions of 2026-10-08 (second round)

def test_block_in_the_inner_corner_of_an_l_plan_is_no_door():
    # P1: inside the convex hull and lined on two sides, but its mouth is bent: not on a facade line
    plan = Polygon([(0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10)])
    out, doors = _door_recesses([(0.0, 2.1, plan), (2.1, 3.3, plan.union(box(4, 4, 5, 5)))], plan, 0.0, 3.3)
    assert doors == [] and out.area == pytest.approx(64.0)


@pytest.mark.parametrize("width, door", [(0.70, True), (3.0, True), (0.69, False), (3.01, False)])
def test_door_width_limits_are_exact(width, door):
    # P2: the mouth is measured along the facade, not on a buffered boundary
    whole = box(0, 0, 10, 10)
    notched = whole.difference(box(4, 0, 4 + width, 0.23))
    _, doors = _door_recesses([(0.0, 2.1, notched), (2.1, 3.3, whole)], notched, 0.0, 3.3)
    assert bool(doors) is door and (not door or doors[0]["mouth_m"] == pytest.approx(width))


def test_l_shaped_panes_never_make_a_rectangle_over_solid_wall():
    # P2: two panes side by side and one over the first; the rectangle of all three covers wall
    spec, _ = extract_spec(building(extra=[pane("glass", 2, 3, 1, 2), pane("glass2", 3.1, 4.1, 1, 2),
                                           pane("glass3", 2, 3, 2.1, 3.1)]), at())
    o = spec.expanded_floors()[0].openings
    assert not any(x.x_m <= 3.5 < x.x_m + x.w_m and x.sill_m <= 2.6 < x.sill_m + x.h_m for x in o)
    assert sum(x.panes for x in o) == 3


def test_door_recess_filled_with_glass_is_a_window():
    # user: a recess filled with glass over its whole height is a window, from the floor or not
    spec, _ = extract_spec(building(boxes=[(0, 4.0, 5.0, 0.0, 2.1, -0.23)],
                                    extra=[pane("glass", 4.0, 5.0, 0.05, 2.05, y=0.2)]), at(L0=0.5))
    o = spec.expanded_floors()[0].openings
    assert [(x.kind, x.source, x.panes) for x in o] == [("window", "hole+glass", 1)]


def test_door_recess_with_glass_over_part_of_its_height_stays_a_door():
    spec, _ = extract_spec(building(boxes=[(0, 4.0, 5.0, 0.0, 2.1, -0.23)],
                                    extra=[pane("glass", 4.1, 4.9, 1.2, 1.9, y=0.2)]), at(L0=0.5))
    assert [(x.kind, x.source) for x in spec.expanded_floors()[0].openings] == [("door", "hole+glass")]


def test_one_frame_across_a_level_is_one_record():
    # user: an opening across a level is one record with level_from / level_to (spec v0.2)
    spec, report = extract_spec(building(extra=[pane("glass", 2.0, 3.0, 1.3, 3.2), pane("glass2", 2.0, 3.0, 3.32, 5.0)]), at())
    floors = spec.expanded_floors()
    assert [(x.sill_m, x.h_m, x.panes, x.level_from, x.level_to) for x in floors[0].openings] == [(1.3, 3.7, 2, "L0", "L1")]
    assert floors[1].openings == [] and spec.spec_version == "0.3"
    assert report["openings"]["openings_across_levels"] == 1


def test_windows_on_two_floors_with_wall_between_stay_two_records():
    spec, _ = extract_spec(building(extra=[pane("glass", 2.0, 3.0, 1.0, 2.4), pane("glass2", 2.0, 3.0, 4.2, 5.6)]), at())
    floors = spec.expanded_floors()
    assert [(len(f.openings), f.openings[0].level_to) for f in floors] == [(1, None), (1, None)]


@pytest.mark.parametrize("change, message", [
    ({"level_to": "L0"}, "level_to a level above"),
    ({"level_to": None}, "needs level_from and level_to"),
])
def test_opening_across_levels_is_validated(change, message):
    doc = {"id": "bench-synth-box", "profile": "npm_min",
           "frame": {"object": "bench-synth-box", "source": "x", "to_object": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]},
           "levels": [{"name": "L0", "elev_m": 0}, {"name": "L1", "elev_m": 3.3}, {"name": "roof", "elev_m": 6.6}],
           "floors": [{"level": "L0", "contour": [[0, 0], [10, 0], [10, 10], [0, 10]],
                       "openings": [{"wall": 0, "x_m": 2, "sill_m": 1, "w_m": 1, "h_m": 4, "depth_m": 0,
                                     "level_from": "L0", "level_to": "L1", **change}]},
                      {"level": "L1", "contour": [[0, 0], [10, 0], [10, 10], [0, 10]]}]}
    with pytest.raises(ValueError, match=message):
        Spec.model_validate(doc)


def test_opening_across_levels_needs_spec_0_2():
    doc = {"id": "bench-synth-box", "profile": "npm_min", "spec_version": "0.1",
           "frame": {"object": "bench-synth-box", "source": "x", "to_object": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]},
           "levels": [{"name": "L0", "elev_m": 0}, {"name": "L1", "elev_m": 3.3}, {"name": "roof", "elev_m": 6.6}],
           "floors": [{"level": "L0", "contour": [[0, 0], [10, 0], [10, 10], [0, 10]],
                       "openings": [{"wall": 0, "x_m": 2, "sill_m": 1, "w_m": 1, "h_m": 4, "depth_m": 0,
                                     "level_from": "L0", "level_to": "L1"}]},
                      {"level": "L1", "contour": [[0, 0], [10, 0], [10, 10], [0, 10]]}]}
    with pytest.raises(ValueError, match="spec_version 0.2"):
        Spec.model_validate(doc)



# PR #33 review 2

@pytest.mark.parametrize("z0, z1", [(1.8, 5.5), (1.3, 5.0)])
def test_one_pane_through_a_level_is_one_record_of_the_lower_floor(z0, z1):
    # owner and crossed levels come from the whole height, not from the pane's centre
    spec, _ = extract_spec(building(extra=[pane("glass", 2.0, 3.0, z0, z1)]), at())
    floors = spec.expanded_floors()
    assert [(x.sill_m, x.h_m, x.level_from, x.level_to) for x in floors[0].openings] == [(z0, round(z1 - z0, 3), "L0", "L1")]
    assert floors[1].openings == []


def test_through_door_with_glass_over_part_of_its_height_is_a_door():
    spec, _ = extract_spec(building(boxes=[(0, 4.0, 5.0, 0.0, 2.1, 0.0)],
                                    extra=[pane("glass", 4.1, 4.9, 1.2, 1.9, y=0.1)]), at())
    assert [(x.kind, x.source) for x in spec.expanded_floors()[0].openings] == [("door", "hole+glass")]


def test_two_ids_on_one_frame_across_a_level_give_no_id_and_a_conflict():
    lower, upper = Mesh("OpeningPlane"), Mesh("OpeningPlane2")
    lower.quad((2.0, 0.05, 1.3), (3.0, 0.05, 1.3), (3.0, 0.05, 3.2), (2.0, 0.05, 3.2))
    upper.quad((2.0, 0.05, 3.32), (3.0, 0.05, 3.32), (3.0, 0.05, 5.0), (2.0, 0.05, 5.0))
    d = building(extra=[pane("glass", 2.0, 3.0, 1.3, 3.2), pane("glass2", 2.0, 3.0, 3.32, 5.0), lower, upper])
    d["meshes"][-2]["material_ids"], d["meshes"][-1]["material_ids"] = [12, 12], [13, 13]
    spec, report = extract_spec(d, at())
    (o,) = spec.expanded_floors()[0].openings
    assert (o.level_to, o.material_id, o.plane_conflict) == ("L1", None, True)
    assert report["openings"]["openings_with_conflicting_planes"] == 1

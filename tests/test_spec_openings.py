"""Openings: a hole in the body or a glass pane at a wall (issue #7). Synthetic data; not a real object."""
import math

import pytest
from shapely.geometry import Polygon

from dt_ai.spec import extract_spec
from test_spec_contour_shapes import SQUARE10, at, dump_of, flat, walls
from test_spec_extract import OBJECT, Mesh, close


def building(contour=SQUARE10, boxes=(), extra=()):
    b = Mesh("Body")
    walls(b, contour, 0.0, 6.6, boxes)
    flat(b, Polygon(contour), 6.6, up=True)
    flat(b, Polygon(contour), 0.0, up=False)
    d = dump_of(b)
    d["meshes"] += [m.dump() for m in extra]
    return d


def pane(name, x0, x1, z0, z1, y=0.0):
    """A vertical glass pane parallel to the south wall (y = const)."""
    g = Mesh(name)
    g.quad((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))
    return g


def reveal(mesh, x0, x1, z0, z1, depth):
    """Reveal faces of a south-wall hole (jambs, sill, head) going `depth` into the building."""
    for x in (x0, x1):
        mesh.quad((x, 0, z0), (x, depth, z0), (x, depth, z1), (x, 0, z1))
    for z in (z0, z1):
        mesh.quad((x0, 0, z), (x1, 0, z), (x1, depth, z), (x0, depth, z))


def openings(spec, level=0):
    return [(o.wall, o.x_m, o.sill_m, o.w_m, o.h_m, o.depth_m, o.source) for o in spec.floors[level].openings]


def test_hole_with_glass_is_one_opening():
    spec, report = extract_spec(building(boxes=[(0, 2.0, 3.5, 0.9, 2.4, 0.0)],
                                         extra=[pane("Glass", 2.1, 3.4, 1.0, 2.3)]), OBJECT)
    assert openings(spec) == [(0, 2.0, 0.9, 1.5, 1.5, 0.0, "hole+glass")]
    assert report["questions"] == []


def test_glass_in_a_closed_wall_is_an_opening():
    # KPP1 v005: the body is closed over the window, the glass is a separate object set 0.15 m in
    spec, report = extract_spec(building(extra=[pane("SM_Main_Glass", 2.0, 3.5, 1.32, 2.7, y=0.15)]), OBJECT)
    assert openings(spec) == [(0, 2.0, 1.32, 1.5, 1.38, 0.15, "glass")]
    assert report["openings"]["glass_openings"] == 1


def test_glass_panes_split_by_a_mullion_are_one_opening():
    spec, report = extract_spec(building(extra=[pane("glass", 2.0, 2.7, 1.0, 2.0), pane("glass2", 2.8, 3.5, 1.0, 2.0)]),
                                OBJECT)
    assert openings(spec) == [(0, 2.0, 1.0, 1.5, 1.0, 0.0, "glass")]


def test_hole_with_a_reveal_is_an_opening_not_a_recess_question():
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, [(0, 2.0, 3.5, 0.9, 2.4, 0.0)])
    reveal(b, 2.0, 3.5, 0.9, 2.4, 0.25)
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert close(spec.floors[0].contour, SQUARE10)
    assert openings(spec) == [(0, 2.0, 0.9, 1.5, 1.5, 0.25, "hole")]
    assert report["questions"] == []


def test_door_from_the_floor_does_not_open_the_storey_end():
    spec, report = extract_spec(building(boxes=[(0, 4.0, 5.0, 0.0, 2.1, 0.0)]), OBJECT)
    assert close(spec.floors[0].contour, SQUARE10)
    assert openings(spec) == [(0, 4.0, 0.0, 1.0, 2.1, 0.0, "hole")]
    assert report["floors"]["L0"]["contour_rule"] == "single shape"


def test_door_with_a_reveal_from_the_floor_needs_no_contour_height():
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, [(0, 4.0, 5.0, 0.0, 2.1, 0.0)])
    reveal(b, 4.0, 5.0, 0.0, 2.1, 0.3)
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert openings(spec) == [(0, 4.0, 0.0, 1.0, 2.1, 0.3, "hole")]
    assert report["questions"] == []


def test_opening_on_a_non_90_wall_is_measured_along_that_wall():
    contour = [[0, 0], [12, 0], [12, 6], [9, 9], [0, 9]]
    diag = math.dist([12, 6], [9, 9])
    spec, _ = extract_spec(building(contour, boxes=[(2, 1.0, 2.5, 1.0, 2.2, 0.0)]), OBJECT)
    (o,) = spec.floors[0].openings
    assert (o.wall, o.x_m, o.w_m, o.h_m) == (2, 1.0, 1.5, 1.2) and diag > 4


def test_recess_with_glass_at_its_back_is_an_opening():
    # a closed recess (back face present) with glass in it: the opening clears the recess question
    spec, report = extract_spec(building(boxes=[(0, 2.0, 3.5, 0.9, 2.4, -0.2)],
                                         extra=[pane("Glass", 2.0, 3.5, 0.9, 2.4, y=0.2)]), at(L0=0.5))
    assert openings(spec) == [(0, 2.0, 0.9, 1.5, 1.5, 0.2, "glass")]
    assert report["questions"] == [] and report["openings"]["recesses_cleared_as_openings"] == 1


def test_horizontal_glass_is_not_an_opening():
    sky = Mesh("Skylight_Glass")
    sky.quad((4, 4, 6.7), (5, 4, 6.7), (5, 5, 6.7), (4, 5, 6.7))
    spec, report = extract_spec(building(extra=[sky]), OBJECT)
    assert openings(spec) == [] and report["openings"]["horizontal_glass_parts"] == 1


def test_stacked_windows_are_two_openings():
    spec, _ = extract_spec(building(boxes=[(0, 2.0, 3.5, 0.6, 1.2, 0.0), (0, 2.0, 3.5, 1.8, 2.6, 0.0)]), OBJECT)
    assert openings(spec) == [(0, 2.0, 0.6, 1.5, 0.6, 0.0, "hole"), (0, 2.0, 1.8, 1.5, 0.8, 0.0, "hole")]


@pytest.mark.parametrize("width, found", [(7.9, True), (8.1, False)])
def test_widest_bridged_gap_is_8_m(width, found):
    # a wider break is not bridged: no opening is invented, those cuts stay open and decide nothing
    contour = [[0, 0], [20, 0], [20, 10], [0, 10]]
    spec, report = extract_spec(building(contour, boxes=[(0, 1.0, 1.0 + width, 1.0, 2.0, 0.0)]), OBJECT)
    assert close(spec.floors[0].contour, contour)
    assert [o[3] for o in openings(spec)] == ([pytest.approx(width)] if found else [])
    assert (report["floors"]["L0"]["closed_sections"] < report["floors"]["L0"]["sections"]) != found

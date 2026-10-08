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


# --- regressions from Codex review 1 of PR #20 -------------------------------------------------

from dt_ai.spec import SpecError, mesh as spec_mesh  # noqa: E402
from dt_ai.spec import openings as op  # noqa: E402


def test_inner_wall_break_is_a_question_not_a_facade_opening():
    # F1: inner wall pieces at y 5 with an 8 m gap; the south facade is intact
    b = Mesh("Body")
    contour = [(0, 0), (20, 0), (20, 10), (0, 10)]
    walls(b, contour, 0, 6.6, extra_u={1: [5], 3: [5]}, extra_z=[0.9, 2.4])
    for x0, x1 in [(0, 4), (12, 20)]:
        b.quad((x0, 5, 0.9), (x1, 5, 0.9), (x1, 5, 2.4), (x0, 5, 2.4))
    flat(b, Polygon(contour), 6.6, up=True)
    flat(b, Polygon(contour), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert openings(spec) == []
    assert [q["kind"] for q in report["questions"]] == ["wall-break-off-contour"]


def test_courtyard_opening_is_not_moved_to_the_facade(monkeypatch):
    # F1: a hole in a courtyard wall cannot be a facade opening of the outer contour
    monkeypatch.setattr(spec_mesh, "_roof", lambda *a, **k: (6.6, 6.6, 1.0))
    outer, inner = [(0, 0), (20, 0), (20, 20), (0, 20)], [(5, 5), (15, 5), (15, 15), (5, 15)]
    b = Mesh("Body")
    walls(b, outer, 0, 6.6)
    walls(b, inner, 0, 6.6, [(0, 3, 5, 0.9, 2.4, 0.0)])
    ring = Polygon(outer, [inner])
    flat(b, ring, 0.0, up=False)
    flat(b, ring, 6.6, up=True)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert openings(spec) == []
    assert "wall-break-off-contour" in [q["kind"] for q in report["questions"]]


def chamfered(depth_leg):
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, [(0, 2.0, 3.5, 0.9, 2.4, 0.0)])
    for path in [[(2, 0), (2.1, 0.1), (2.1, 0.1 + depth_leg)], [(3.5, 0), (3.4, 0.1), (3.4, 0.1 + depth_leg)]]:
        for a, c in zip(path, path[1:]):
            b.quad((*a, 0.9), (*c, 0.9), (*c, 2.4), (*a, 2.4))
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    return dump_of(b)


@pytest.mark.parametrize("leg, depth", [(0.2, 0.3), (1.1, 1.2)])
def test_chamfered_and_deep_reveals_are_openings(leg, depth):
    # F2: 0.1 m 45 degree chamfer, then a straight leg; also a 1.2 m deep reveal
    spec, report = extract_spec(chamfered(leg), OBJECT)
    assert openings(spec) == [(0, 2.0, 0.9, 1.5, 1.5, depth, "hole")]
    assert report["questions"] == []


def test_stacked_holes_keep_their_own_width():
    # F3: 1.500 m below, 1.518 m above
    spec, _ = extract_spec(building(boxes=[(0, 2.0, 3.5, 0.6, 1.2, 0.0), (0, 2.0, 3.518, 1.8, 2.6, 0.0)]), OBJECT)
    assert [o[3] for o in openings(spec)] == [1.5, 1.518]


def test_pane_not_parallel_to_its_wall_is_skipped():
    # F4: an inner pane square to the south wall must not abort the extraction
    g = Mesh("Glass")
    g.quad((5, 0.1, 1.0), (5, 0.3, 1.0), (5, 0.3, 2.0), (5, 0.1, 2.0))
    spec, report = extract_spec(building(extra=[g]), OBJECT)
    assert openings(spec) == [] and report["openings"]["glass_parts_skipped"] == 1


def test_panes_with_different_sills_are_separate_openings():
    # F5: no merged rectangle over glass that is not there
    spec, _ = extract_spec(building(extra=[pane("glass", 2.0, 3.0, 1.0, 2.0), pane("glass2", 3.1, 4.1, 1.9, 2.9)]),
                           OBJECT)
    assert [(o[1], o[2], o[3], o[4]) for o in openings(spec)] == [(2.0, 1.0, 1.0, 1.0), (3.1, 1.9, 1.0, 1.0)]


def test_tall_recess_with_a_short_window_stays_a_question():
    # F6: recess 0.2-2.8 m with glass at 1.0-1.2 m only
    spec, report = extract_spec(building(boxes=[(0, 2.0, 3.5, 0.2, 2.8, -0.2)],
                                         extra=[pane("Glass", 2.0, 3.5, 1.0, 1.2, y=0.2)]), at(L0=0.1))
    assert [o[6] for o in openings(spec)] == ["glass"]
    assert [q["kind"] for q in report["questions"]] == ["recess"]


def test_opening_plane_keeps_the_hole_anchor_and_gives_its_material_id():
    # F9/F10: a plane with material id 12 (group opening) over the hole is not body
    plane = Mesh("OpeningPlane")
    plane.quad((2.0, 0, 0.9), (3.5, 0, 0.9), (3.5, 0, 2.4), (2.0, 0, 2.4))
    d = building(boxes=[(0, 2.0, 3.5, 0.9, 2.4, 0.0)], extra=[plane])
    d["meshes"][-1]["material_ids"] = [12, 12]
    spec, _ = extract_spec(d, OBJECT)
    (o,) = spec.floors[0].openings
    assert (o.source, o.material_id, o.window_type, o.w_m) == ("hole", 12, None, 1.5)


def test_one_pane_over_two_holes_marks_both():
    spec, _ = extract_spec(building(boxes=[(0, 2.0, 3.0, 1.0, 2.0, 0.0), (0, 3.1, 4.1, 1.0, 2.0, 0.0)],
                                    extra=[pane("Glass", 2.0, 4.1, 1.0, 2.0, y=0.1)]), OBJECT)
    assert [o[6] for o in openings(spec)] == ["hole+glass", "hole+glass"]


def test_breaks_that_do_not_face_each_other_are_not_bridged():
    assert op.close_section([[(-1, 0), (0, 0)], [(0, 8), (-1, 8)]])[1] == []      # parallel walls 8 m apart
    assert op.close_section([[(-1, 0), (0, 0)], [(1, 1), (1, 2)]])[1] == []       # corner ends, not collinear
    assert SpecError

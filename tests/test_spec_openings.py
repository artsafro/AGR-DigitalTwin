"""Openings: a hole in the body or a glass pane at a wall (issue #7). Synthetic data; not a real object."""
import math

import numpy as np
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
    return [(o.wall, o.x_m, o.sill_m, o.w_m, o.h_m, o.depth_m, o.source) for o in spec.expanded_floors()[level].openings]


def test_hole_with_glass_is_one_opening():
    spec, report = extract_spec(building(boxes=[(0, 2.0, 3.5, 0.9, 2.4, 0.0)],
                                         extra=[pane("Glass", 2.1, 3.4, 1.0, 2.3)]), OBJECT)
    assert openings(spec) == [(0, 2.0, 0.9, 1.5, 1.5, 0.0, "hole+glass")]
    # glass flush with the facade: depth 0, relief or a drawing? (C24 final, user decision 2026-10-10)
    assert [q["kind"] for q in report["questions"]] == ["opening-flush"]
    assert report["openings"]["openings_flush"] == 1


def test_glass_in_a_closed_wall_is_an_opening():
    # KPP1 v005: the body is closed over the window, the glass is a separate object set 0.15 m in
    spec, report = extract_spec(building(extra=[pane("SM_Main_Glass", 2.0, 3.5, 1.32, 2.7, y=0.15)]), OBJECT)
    assert openings(spec) == [(0, 2.0, 1.32, 1.5, 1.38, None, "glass")]
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
    assert close(spec.expanded_floors()[0].contour, SQUARE10)
    assert openings(spec) == [(0, 2.0, 0.9, 1.5, 1.5, None, "hole")]
    assert report["questions"] == []


def test_door_from_the_floor_does_not_open_the_storey_end():
    spec, report = extract_spec(building(boxes=[(0, 4.0, 5.0, 0.0, 2.1, 0.0)]), OBJECT)
    assert close(spec.expanded_floors()[0].contour, SQUARE10)
    assert openings(spec) == [(0, 4.0, 0.0, 1.0, 2.1, 0.0, "hole")]
    assert report["floors"]["L0"]["contour_rule"] == "single shape"


def test_door_with_a_reveal_from_the_floor_needs_no_contour_height():
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, [(0, 4.0, 5.0, 0.0, 2.1, 0.0)])
    reveal(b, 4.0, 5.0, 0.0, 2.1, 0.3)
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert openings(spec) == [(0, 4.0, 0.0, 1.0, 2.1, None, "hole")]
    assert report["questions"] == []


def test_opening_on_a_non_90_wall_is_measured_along_that_wall():
    contour = [[0, 0], [12, 0], [12, 6], [9, 9], [0, 9]]
    diag = math.dist([12, 6], [9, 9])
    spec, _ = extract_spec(building(contour, boxes=[(2, 1.0, 2.5, 1.0, 2.2, 0.0)]), OBJECT)
    (o,) = spec.expanded_floors()[0].openings
    assert (o.wall, o.x_m, o.w_m, o.h_m) == (2, 1.0, 1.5, 1.2) and diag > 4


def test_recess_with_glass_at_its_back_is_an_opening():
    # a closed recess (back face present) with glass in it: the opening clears the recess question
    spec, report = extract_spec(building(boxes=[(0, 2.0, 3.5, 0.9, 2.4, -0.2)],
                                         extra=[pane("Glass", 2.0, 3.5, 0.9, 2.4, y=0.2)]), at(L0=0.5))
    assert openings(spec) == [(0, 2.0, 0.9, 1.5, 1.5, None, "glass")]
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
    assert close(spec.expanded_floors()[0].contour, contour)
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
    monkeypatch.setattr(spec_mesh, "_roof", lambda *a, **k: (6.6, 6.6, 1.0, {"parapet": False}))
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


@pytest.mark.parametrize("leg, depth", [(0.2, None), (1.1, 1.2)])   # 0.3 m is within 0.1 m of the default (#36)
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
    # v0.3 (#36): the recess is no frame, so the opening's size is a question too
    assert sorted(q["kind"] for q in report["questions"]) == ["opening-size-unknown", "recess"]


def test_opening_plane_keeps_the_hole_anchor_and_gives_its_material_id():
    # F9/F10: a plane with material id 12 (group opening) over the hole is not body
    plane = Mesh("OpeningPlane")
    plane.quad((2.0, 0, 0.9), (3.5, 0, 0.9), (3.5, 0, 2.4), (2.0, 0, 2.4))
    d = building(boxes=[(0, 2.0, 3.5, 0.9, 2.4, 0.0)], extra=[plane])
    d["meshes"][-1]["material_ids"] = [12, 12]
    spec, _ = extract_spec(d, OBJECT)
    (o,) = spec.expanded_floors()[0].openings
    assert (o.source, o.material_id, o.window_type, o.w_m) == ("hole", 12, None, 1.5)


def test_one_pane_over_two_holes_marks_both():
    spec, _ = extract_spec(building(boxes=[(0, 2.0, 3.0, 1.0, 2.0, 0.0), (0, 3.1, 4.1, 1.0, 2.0, 0.0)],
                                    extra=[pane("Glass", 2.0, 4.1, 1.0, 2.0, y=0.1)]), OBJECT)
    assert [o[6] for o in openings(spec)] == ["hole+glass", "hole+glass"]


def test_breaks_that_do_not_face_each_other_are_not_bridged():
    assert op.close_section([[(-1, 0), (0, 0)], [(0, 8), (-1, 8)]])[1] == []      # parallel walls 8 m apart
    assert op.close_section([[(-1, 0), (0, 0)], [(1, 1), (1, 2)]])[1] == []       # corner ends, not collinear
    assert SpecError


# --- regressions from Codex review 2 of PR #20 -------------------------------------------------

@pytest.mark.parametrize("width", [4.0, 5.0, 6.0, 7.9])
def test_wide_hole_in_a_small_building_is_not_a_pier(width):
    # N1: 10 x 2 m body; the way round the building is not a pier
    contour = [(0, 0), (10, 0), (10, 2), (0, 2)]
    spec, report = extract_spec(building(contour, boxes=[(0, 1.0, 1.0 + width, 0.9, 2.4, 0.0)]), OBJECT)
    assert [(o[1], o[3]) for o in openings(spec)] == [(1.0, pytest.approx(width))]


def test_pier_between_two_windows_is_not_bridged():
    spec, _ = extract_spec(building(boxes=[(0, 2.0, 3.5, 0.9, 2.4, 0.0), (0, 3.8, 5.3, 0.9, 2.4, 0.0)]), OBJECT)
    assert [(o[1], o[3]) for o in openings(spec)] == [(2.0, 1.5), (3.8, 1.5)]


@pytest.mark.parametrize("n", [12, 24])
def test_hole_on_a_rounded_corner_is_an_opening(n):
    # N2: one facet of an r 1.5 arc removed between 0.9 and 2.4 m
    r = 1.5
    arc = [[10 - r + r * math.cos(a), 10 - r + r * math.sin(a)] for a in np.linspace(0, math.pi / 2, n + 1)]
    contour = [[0, 0], [10, 0], *arc, [0, 10]]
    facet = 2 + n // 2                                  # a facet in the middle of the arc
    chord = math.dist(contour[facet], contour[facet + 1])
    spec, report = extract_spec(building(contour, boxes=[(facet, 0.0, chord, 0.9, 2.4, 0.0)]), OBJECT)
    (o,) = spec.expanded_floors()[0].openings
    assert (o.w_m, o.h_m, o.source) == (pytest.approx(chord, abs=0.01), 1.5, "hole")
    assert report["questions"] == []


def test_plane_ids_follow_their_own_part():
    # N3: a horizontal opening-group part (id 11) must not shift the vertical plane's id (12)
    plane, flat_part = Mesh("OpeningPlane"), Mesh("Shelf")
    plane.quad((2.0, 0, 0.9), (3.5, 0, 0.9), (3.5, 0, 2.4), (2.0, 0, 2.4))
    flat_part.quad((2, 2, 3.0), (8, 2, 3.0), (8, 8, 3.0), (2, 8, 3.0))
    d = building(boxes=[(0, 2.0, 3.5, 0.9, 2.4, 0.0)], extra=[flat_part, plane])
    d["meshes"][-2]["material_ids"], d["meshes"][-1]["material_ids"] = [11, 11], [12, 12]
    (o,) = extract_spec(d, OBJECT)[0].floors[0].openings
    assert o.material_id == 12


def test_plane_with_mixed_ids_gets_no_id():
    plane = Mesh("OpeningPlane")
    plane.quad((2.0, 0, 0.9), (3.5, 0, 0.9), (3.5, 0, 2.4), (2.0, 0, 2.4))
    d = building(boxes=[(0, 2.0, 3.5, 0.9, 2.4, 0.0)], extra=[plane])
    d["meshes"][-1]["material_ids"] = [12, 13]
    spec, report = extract_spec(d, OBJECT)
    assert spec.expanded_floors()[0].openings[0].material_id is None and report["openings"]["opening_planes_mixed_ids"] == 1


def test_plane_without_material_ids_is_a_question():
    # N8: shape alone cannot tell an opening plane from a wall piece: ask, do not certify
    plane = Mesh("OpeningPlane")
    plane.quad((2.0, 0, 0.9), (3.5, 0, 0.9), (3.5, 0, 2.4), (2.0, 0, 2.4))
    spec, report = extract_spec(building(boxes=[(0, 2.0, 3.5, 0.9, 2.4, 0.0)], extra=[plane]), OBJECT)
    assert [q["kind"] for q in report["questions"]] == ["flat-object-in-wall"]
    assert report["openings"]["planes_without_material_id"] == 1


def test_partial_material_ids_are_an_error():
    # N10
    plane = Mesh("OpeningPlane")
    plane.quad((2.0, 0, 0.9), (3.5, 0, 0.9), (3.5, 0, 2.4), (2.0, 0, 2.4))
    d = building(extra=[plane])
    d["meshes"][-1]["material_ids"] = [12]
    with pytest.raises(SpecError, match="1 material ids for 2 triangles"):
        extract_spec(d, OBJECT)


def test_pier_check_stays_cheap_on_a_comb():
    # N9: many short teeth; the pier search is bounded by the gap plus two reveals
    import time
    segs = [[(0, 0), (100, 0)]] + [[(x, 0), (x, 0.3)] for x in np.arange(0.5, 100, 0.5)]
    t = time.perf_counter()
    op.close_section(segs)
    assert time.perf_counter() - t < 5.0


# --- regressions from Codex review 3 of PR #20 -------------------------------------------------

def test_unused_vertices_do_not_hide_a_flat_object_in_the_wall():
    # R5: an unused vertex far away must not make the plane look non-flat
    plane = Mesh("OpeningPlane")
    plane.quad((2.0, 0, 0.9), (3.5, 0, 0.9), (3.5, 0, 2.4), (2.0, 0, 2.4))
    d = building(boxes=[(0, 2.0, 3.5, 0.9, 2.4, 0.0)], extra=[plane])
    d["meshes"][-1]["vertices"].append([8.0, 8.0, 3.0])
    _, report = extract_spec(d, OBJECT)
    assert [q["kind"] for q in report["questions"]] == ["flat-object-in-wall"]


def test_conflicting_opening_planes_give_no_material_id():
    # R6: planes 12 and 13 over one hole, in either order
    for ids in ((12, 13), (13, 12)):
        planes = []
        for y, mid in zip((0.1, 0.2), ids):
            pl = Mesh(f"Plane{mid}")
            pl.quad((2.0, y, 0.9), (3.5, y, 0.9), (3.5, y, 2.4), (2.0, y, 2.4))
            planes.append(pl)
        d = building(boxes=[(0, 2.0, 3.5, 0.9, 2.4, 0.0)], extra=planes)
        d["meshes"][-2]["material_ids"], d["meshes"][-1]["material_ids"] = [ids[0]] * 2, [ids[1]] * 2
        spec, report = extract_spec(d, OBJECT)
        (o,) = spec.expanded_floors()[0].openings
        assert (o.material_id, o.plane_conflict) == (None, True)
        assert report["openings"]["openings_with_conflicting_planes"] == 1


def test_remote_or_high_flat_objects_are_not_questions():
    # R8: a sign 40 m away and a plane above the roof are attachments, not wall planes
    sign, high = Mesh("Sign"), Mesh("High")
    sign.quad((40.0, 40, 1.0), (41.0, 40, 1.0), (41.0, 40, 2.0), (40.0, 40, 2.0))
    high.quad((2.0, 0, 9.0), (3.0, 0, 9.0), (3.0, 0, 10.0), (2.0, 0, 10.0))
    _, report = extract_spec(building(extra=[sign, high]), OBJECT)
    assert report["questions"] == []



def test_plane_at_the_back_of_its_reveal_gives_the_opening_depth():
    # C24 final (user 2026-10-10): the depth is facade -> back polygon; the plane is that polygon in npm_min
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, [(0, 2.0, 3.5, 0.9, 2.4, 0.0)])
    reveal(b, 2.0, 3.5, 0.9, 2.4, 0.4)
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    plane = Mesh("OpeningPlane")
    plane.quad((2.0, 0.4, 0.9), (3.5, 0.4, 0.9), (3.5, 0.4, 2.4), (2.0, 0.4, 2.4))
    d = dump_of(b)
    d["meshes"].append({**plane.dump(), "material_ids": [11, 11]})
    spec, report = extract_spec(d, OBJECT)
    (o,) = spec.expanded_floors()[0].openings
    assert (o.depth_m, o.material_id) == (0.4, 11) and report["questions"] == []



def planed(reveal_depth, plane_at):
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, [(0, 2.0, 3.5, 0.9, 2.4, 0.0)])
    if reveal_depth:
        reveal(b, 2.0, 3.5, 0.9, 2.4, reveal_depth)
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    plane = Mesh("OpeningPlane")
    plane.quad((2.0, plane_at, 0.9), (3.5, plane_at, 0.9), (3.5, plane_at, 2.4), (2.0, plane_at, 2.4))
    d = dump_of(b)
    d["meshes"].append({**plane.dump(), "material_ids": [11, 11]})
    spec, report = extract_spec(d, {**OBJECT, "opening_depth_default_m": 0.4})
    (o,) = spec.expanded_floors()[0].openings
    return o, [q["kind"] for q in report["questions"]]


@pytest.mark.parametrize("reveal_depth, plane_at, depth_m, flush", [
    (0.0, 0.2, 0.2, False),      # Codex review 1 of PR #52: a recessed plane without reveal is not flush
    (0.4, 0.0, 0.0, True),       # a plane flush with the facade over a 0.4 m reveal is flush
    (0.4, 0.4, None, False),     # the plane at the back of the reveal: depth 0.4 = the default
])
def test_depth_is_the_back_polygon_position(reveal_depth, plane_at, depth_m, flush):
    o, kinds = planed(reveal_depth, plane_at)
    assert o.depth_m == depth_m and ("opening-flush" in kinds) == flush



@pytest.mark.parametrize("glass_y", [0.0, 0.6])
def test_glass_position_never_sets_the_depth(glass_y):
    # Codex review 2 of PR #52: a 0.2 m reveal without a plane gives 0.2 m wherever the glass sits
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, [(0, 2.0, 3.5, 0.9, 2.4, 0.0)])
    reveal(b, 2.0, 3.5, 0.9, 2.4, 0.2)
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    d = dump_of(b)
    d["meshes"].append(pane("glass", 2.1, 3.4, 1.0, 2.3, y=glass_y).dump())
    spec, _ = extract_spec(d, {**OBJECT, "opening_depth_default_m": 0.6})
    (o,) = spec.expanded_floors()[0].openings
    assert o.depth_m == 0.2

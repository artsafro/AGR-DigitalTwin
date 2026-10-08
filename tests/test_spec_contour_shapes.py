"""Level contour shapes and not-full-height deviations (issue #6). Synthetic data; not a real object."""
import json
import math

import numpy as np
import pytest
import shapely
from shapely.geometry import Polygon

from dt_ai.cli.main import main
from dt_ai.spec import SpecError, extract_spec
from test_spec_extract import OBJECT, Mesh, close

LEVELS = (("L0", 0.0), ("L1", 3.3), ("roof", 6.6))


def flat(mesh, poly, z, up=True):
    """Triangulate a (possibly concave or holed) polygon at height z, facing up or down."""
    for tri in shapely.get_parts(shapely.constrained_delaunay_triangles(poly)):
        a, b, c = list(tri.exterior.coords)[:3]
        (ux, uy), (vx, vy) = np.subtract(b, a), np.subtract(c, a)
        if (ux * vy - uy * vx > 0) != up:
            b, c = c, b
        mesh.vertices += [[*a, z], [*b, z], [*c, z]]
        n = len(mesh.vertices)
        mesh.triangles.append([n - 3, n - 2, n - 1])


def walls(mesh, contour, z0, z1, boxes=(), extra_u=None, extra_z=()):
    """Vertical walls of a CCW contour from z0 to z1, split so box corners are shared vertices.
    boxes: (wall, u0, u1, bz0, bz1, depth) projections outward from that wall."""
    pts = np.asarray(contour, dtype=float)
    for w in range(len(pts)):
        a, b = pts[w], pts[(w + 1) % len(pts)]
        length = float(np.linalg.norm(b - a))
        us = {0.0, length, *[u for bx in boxes if bx[0] == w for u in bx[1:3]], *(extra_u or {}).get(w, [])}
        zs = {z0, z1, *[z for bx in boxes if bx[0] == w for z in bx[3:5] if z0 < z < z1], *extra_z}
        us, zs = sorted(us), sorted(zs)
        t = (b - a) / length
        cuts = [bx for bx in boxes if bx[0] == w and bx[5] <= 0]  # recesses and holes (depth 0): no wall there
        for u0, u1 in zip(us, us[1:]):
            for za, zb in zip(zs, zs[1:]):
                if any(c[1] <= u0 and u1 <= c[2] and c[3] <= za and zb <= c[4] for c in cuts):
                    continue
                p, q = a + u0 * t, a + u1 * t
                mesh.quad((*p, za), (*q, za), (*q, zb), (*p, zb))
    for w, u0, u1, bz0, bz1, depth in boxes:
        if depth == 0:
            continue
        a, b = pts[w], pts[(w + 1) % len(pts)]
        t = (b - a) / np.linalg.norm(b - a)
        n = np.array([t[1], -t[0]])                      # outward for a CCW contour
        p0, p1 = a + u0 * t, a + u1 * t
        o0, o1 = p0 + depth * n, p1 + depth * n
        mesh.quad((*o0, bz0), (*o1, bz0), (*o1, bz1), (*o0, bz1))   # front
        mesh.quad((*p0, bz1), (*o0, bz1), (*o1, bz1), (*p1, bz1))   # top
        mesh.quad((*p0, bz0), (*p1, bz0), (*o1, bz0), (*o0, bz0))   # bottom
        mesh.quad((*p0, bz0), (*o0, bz0), (*o0, bz1), (*p0, bz1))   # side at u0
        mesh.quad((*o1, bz0), (*p1, bz0), (*p1, bz1), (*o1, bz1))   # side at u1


def prism(contour, boxes=(), height=6.6):
    """One block from 0 to `height` with a flat roof and no parapet."""
    b = Mesh("Body")
    walls(b, contour, 0.0, height, boxes)
    flat(b, Polygon(contour), height, up=True)
    flat(b, Polygon(contour), 0.0, up=False)
    return dump_of(b)


def dump_of(mesh):
    return {"source": "synthetic-shapes", "meshes": [mesh.dump()],
            "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]} for n, z in LEVELS]}


SQUARE10 = [[0, 0], [10, 0], [10, 10], [0, 10]]


def test_b02_like_non_90_corner_niche_and_two_roof_levels():
    lower = [[0, 0], [4, 0], [4, 0.5], [6, 0.5], [6, 0], [12, 0], [12, 6], [9, 9], [0, 9]]
    upper = [[6, 0], [12, 0], [12, 6], [9, 9], [6, 9]]
    b = Mesh("Body")
    walls(b, lower, 0.0, 3.3, extra_u={8: [3.0]})          # vertex at (6, 9) shared with the upper block
    walls(b, upper, 3.3, 6.6)
    flat(b, Polygon(lower).difference(Polygon(upper)), 3.3, up=True)   # lower roof (terrace)
    flat(b, Polygon(upper), 6.6, up=True)
    flat(b, Polygon(lower), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert close(spec.floors[0].contour, lower)
    assert close(spec.floors[1].contour, upper)
    assert (report["roof"]["plane_m"], spec.roof.parapet_h_m) == (6.6, 0.0)
    assert report["questions"] == []


def test_rounded_corner_is_one_point_with_radius():
    r, n = 1.5, 12
    arc = [[10 - r + r * math.cos(a), 10 - r + r * math.sin(a)] for a in np.linspace(0, math.pi / 2, n + 1)]
    contour = [[0, 0], [10, 0], *arc, [0, 10]]
    spec, _ = extract_spec(prism(contour), OBJECT)
    pts = spec.floors[0].contour
    assert len(pts) == 4
    corner = [p for p in pts if len(p) == 3]
    assert len(corner) == 1 and math.dist(corner[0][:2], [10, 10]) <= 0.02
    assert corner[0][2]["r"] == pytest.approx(1.5, abs=0.02)


@pytest.mark.parametrize("deg, kept", [(3.0, False), (7.0, True)])
def test_kinks_over_5_degrees_are_kept(deg, kept):
    y = 10 * math.tan(math.radians(deg))
    contour = [[0, 0], [10, 0], [20, y], [20, 10], [0, 10]]
    spec, _ = extract_spec(prism(contour), OBJECT)
    pts = spec.floors[0].contour
    assert (any(math.dist(p[:2], [10, 0]) < 0.01 for p in pts)) == kept
    assert len(pts) == (5 if kept else 4)


def at(**heights):
    """object.json with contour_at_m: the user names a height of the wall shape per level."""
    return {**OBJECT, "contour_at_m": heights}


def only_question(dump, obj=OBJECT):
    spec, report = extract_spec(dump, obj)
    assert close(spec.floors[0].contour, SQUARE10) and close(spec.floors[1].contour, SQUARE10)
    assert len(report["questions"]) == 1, report["questions"]
    return report["questions"][0]


def test_plinth_never_changes_the_contour_and_is_a_high_priority_question():
    dump = prism(SQUARE10, boxes=[(0, 0.0, 10.0, 0.0, 0.6, 0.1)])
    # the storey ends differ (plinth at the bottom): the extractor asks, it does not pick
    with pytest.raises(SpecError, match=r"level L0: no section shape .* shape 1: 101.00 m2 at 0.000-0.600 m"):
        extract_spec(dump, OBJECT)
    q = only_question(dump, at(L0=2.0))
    assert (q["kind"], q["levels"], q["wall"], q["priority"]) == ("projection", ["L0"], 0, "high")
    assert q["depth_m"] == pytest.approx(0.1, abs=0.01) and q["length_m"] == pytest.approx(10, abs=0.01)


@pytest.mark.parametrize("u1, priority", [(2.9, "normal"), (3.1, "high")])
def test_facade_share_threshold_sets_priority_not_route(u1, priority):
    q = only_question(prism(SQUARE10, boxes=[(0, 2.0, u1, 1.0, 1.5, 0.2)]))
    assert q["facade_share"] == pytest.approx((u1 - 2.0) / 10, abs=0.002)
    assert (q["priority"], q["levels"]) == (priority, ["L0"])
    assert q["depth_m"] == pytest.approx(0.2, abs=0.01)


@pytest.mark.parametrize("z1, levels, priority", [(3.2, ["L0"], "normal"), (3.8, ["L0", "L1"], "high")])
def test_two_levels_threshold_sets_priority_not_route(z1, levels, priority):
    q = only_question(prism(SQUARE10, boxes=[(0, 2.0, 2.5, 2.8, z1, 0.2)]), at(L0=1.0, L1=5.0))
    assert (q["levels"], q["priority"]) == (levels, priority)


def test_full_height_pilaster_is_in_the_contour_without_a_question():
    spec, report = extract_spec(prism(SQUARE10, boxes=[(0, 2.0, 2.5, 0.0, 3.3, 0.2)]), OBJECT)
    assert close(spec.floors[0].contour, [[0, 0], [2, 0], [2, -0.2], [2.5, -0.2], [2.5, 0], [10, 0], [10, 10], [0, 10]],
                 tol=0.01) or close(spec.floors[0].contour,
                                    [[2, -0.2], [2.5, -0.2], [2.5, 0], [10, 0], [10, 10], [0, 10], [0, 0], [2, 0]])
    assert close(spec.floors[1].contour, SQUARE10)
    assert report["questions"] == []


# --- regressions from Codex review 1 of PR #19 -------------------------------------------------

@pytest.mark.parametrize("bz0, bz1", [(0.2, 3.1), (0.1, 3.2)])
def test_partial_projection_over_most_of_the_storey_never_changes_the_contour(bz0, bz1):
    # F1: absent only near the storey ends; frequency must not put it into the contour. The shape at
    # both ends is not the tallest, so the extractor asks; with the wall height named it answers
    dump = prism(SQUARE10, boxes=[(0, 2.0, 3.0, bz0, bz1, 0.2)])
    with pytest.raises(SpecError, match="no section shape is both at the two storey ends and the tallest"):
        extract_spec(dump, OBJECT)
    q = only_question(dump, at(L0=bz0 / 2))
    assert (q["kind"], q["levels"], q["priority"]) == ("projection", ["L0"], "normal")
    assert (q["depth_m"], q["length_m"], q["facade_share"], q["heights_m"]) == (0.2, 1.0, 0.1, [bz0, bz1])


def test_partial_recess_over_most_of_the_storey_never_changes_the_contour():
    dump = prism(SQUARE10, boxes=[(0, 2.0, 3.0, 0.2, 3.1, -0.2)])
    with pytest.raises(SpecError, match="no section shape"):
        extract_spec(dump, OBJECT)
    q = only_question(dump, at(L0=0.1))
    assert (q["kind"], q["wall"], q["depth_m"], q["length_m"], q["heights_m"]) == ("recess", 0, 0.2, 1.0, [0.2, 3.1])


def test_faceted_corner_is_not_turned_into_an_arc():
    # F2: five real kinks (11-25 degrees) are facets, not a fillet
    contour = [[0, 0], [10, 0], [10, 8], [9.9, 8.5], [9.5, 9.2], [8.8, 9.7], [8, 10], [0, 10]]
    spec, _ = extract_spec(prism(contour), OBJECT)
    assert close(spec.floors[0].contour, contour) and all(len(p) == 2 for p in spec.floors[0].contour)


def test_seven_degree_kink_next_to_a_small_one_is_kept():
    # F3: directions 0, 4.5, -2.5 degrees: the -7 degree kink stays, the 4.5 degree one goes
    p1 = [10 + 10 * math.cos(math.radians(4.5)), 10 * math.sin(math.radians(4.5))]
    p2 = [p1[0] + 10 * math.cos(math.radians(-2.5)), p1[1] + 10 * math.sin(math.radians(-2.5))]
    contour = [[0, 0], [10, 0], p1, p2, [p2[0], 10], [0, 10]]
    spec, _ = extract_spec(prism(contour), OBJECT)
    pts = spec.floors[0].contour
    assert any(math.dist(p[:2], p1) < 0.01 for p in pts)
    assert not any(math.dist(p[:2], [10, 0]) < 0.01 for p in pts)


@pytest.mark.parametrize("n", [12, 24])
def test_large_radius_does_not_depend_on_tessellation(n):
    # F4: r = 10 m quarter circle with 1.31 m or 0.65 m chords
    r = 10.0
    arc = [[30 - r + r * math.cos(a), 30 - r + r * math.sin(a)] for a in np.linspace(0, math.pi / 2, n + 1)]
    spec, _ = extract_spec(prism([[0, 0], [30, 0], *arc, [0, 30]]), OBJECT)
    pts = spec.floors[0].contour
    assert len(pts) == 4
    corner = [p for p in pts if len(p) == 3][0]
    assert math.dist(corner[:2], [30, 30]) <= 0.05 and corner[2]["r"] == pytest.approx(10, abs=0.05)


def test_thin_element_between_old_sample_heights_is_seen():
    # F5: 5 cm high, 2 cm wide elements: exact height intervals, no area cut-off
    q = only_question(prism(SQUARE10, boxes=[(0, 2.0, 3.0, 1.15, 1.20, 0.2)]))
    assert q["heights_m"] == [1.15, 1.2] and q["depth_m"] == 0.2
    q = only_question(prism(SQUARE10, boxes=[(0, 2.0, 2.02, 1.0, 1.5, 0.2)]))
    assert q["length_m"] == pytest.approx(0.02, abs=0.001) and q["depth_m"] == 0.2


def test_element_crossing_a_level_line_is_on_both_levels():
    # F5: 2.8-3.4 m crosses the 3.3 m level, although no old sample height fell in L1 below 3.437
    q = only_question(prism(SQUARE10, boxes=[(0, 2.0, 2.5, 2.8, 3.4, 0.2)]), at(L0=1.0, L1=5.0))
    assert (q["levels"], q["priority"], q["heights_m"]) == (["L0", "L1"], "high", [2.8, 3.4])


def test_recess_near_a_corner_is_measured_on_its_own_wall():
    # F6: recess 0.1 m wide, 1.2 m deep, 2 cm from the west wall
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, boxes=[(0, 0.02, 0.12, 1.0, 1.5, -1.2)])
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    q = only_question(dump_of(b))
    assert (q["kind"], q["wall"], q["priority"]) == ("recess", 0, "normal")
    assert (q["length_m"], q["depth_m"], q["facade_share"]) == (0.1, 1.2, 0.01)


def test_pieces_overlapping_in_plan_but_not_in_height_are_separate_elements():
    # F7 (review 1) and R2-F1 (review 2): an element is connected in plan AND height. L0 pieces x 1-2
    # and 3-4 at 1.0-1.5, L1 piece x 1.5-3.5 at 4.0-4.5: three elements, no partial merge
    spec, report = extract_spec(prism(SQUARE10, boxes=[(0, 1.0, 2.0, 1.0, 1.5, 0.2), (0, 3.0, 4.0, 1.0, 1.5, 0.2),
                                                       (0, 1.5, 3.5, 4.0, 4.5, 0.2)]), OBJECT)
    got = sorted((q["levels"], q["length_m"], q["heights_m"]) for q in report["questions"])
    assert got == [(["L0"], 1.0, [1.0, 1.5]), (["L0"], 1.0, [1.0, 1.5]), (["L1"], 2.0, [4.0, 4.5])]


@pytest.mark.parametrize("u1, share, priority, shown", [(3.0, 0.1, "normal", "10.0%"), (3.01, 0.101, "high", "10.1%")])
def test_share_threshold_is_visible_in_the_questions_file(u1, share, priority, shown):
    # F8: the file shows which side of 10 % the element is on
    from dt_ai.spec.mesh import questions_markdown
    spec, report = extract_spec(prism(SQUARE10, boxes=[(0, 2.0, u1, 1.0, 1.5, 0.2)]), OBJECT)
    q = report["questions"][0]
    assert (q["facade_share"], q["priority"]) == (share, priority)
    assert f"| {shown} |" in questions_markdown(spec.id, report["questions"])


def test_cli_writes_the_questions_file(tmp_path):
    dump, obj, out = tmp_path / "dump.json", tmp_path / "object.json", tmp_path / "spec-v001.json"
    dump.write_text(json.dumps(prism(SQUARE10, boxes=[(0, 0.0, 10.0, 0.0, 0.6, 0.1)])), encoding="utf-8")
    obj.write_text(json.dumps(at(L0=2.0)), encoding="utf-8")
    assert main(["spec", "extract", "--dump", str(dump), "--object", str(obj), "--output", str(out)]) == 0
    text = out.with_suffix(".questions.md").read_text(encoding="utf-8")
    assert "| 1 | high | projection | L0 | 0 | 0.1 | 10.0 | 100.0% | 0.0–0.6 |" in text


# --- regressions from Codex review 2 of PR #19 -------------------------------------------------

@pytest.mark.parametrize("cornice_depth", [0.1, 0.2])
def test_plinth_and_cornice_at_both_ends_are_not_the_wall(cornice_depth):
    # R2-F1: plinth 0-0.6 and cornice 3.0-3.3 on the whole south wall; the wall is visible in between only
    dump = prism(SQUARE10, boxes=[(0, 0.0, 10.0, 0.0, 0.6, 0.1), (0, 0.0, 10.0, 3.0, 3.3, cornice_depth)])
    with pytest.raises(SpecError, match="no section shape is both at the two storey ends and the tallest"):
        extract_spec(dump, OBJECT)
    spec, report = extract_spec(dump, at(L0=1.5))
    assert close(spec.floors[0].contour, SQUARE10)
    kinds = sorted((q["kind"], q["depth_m"], q["heights_m"][0]) for q in report["questions"])
    assert kinds == [("projection", 0.1, 0.0), ("projection", cornice_depth, 3.0)]


def test_majority_plinth_is_a_question_not_the_contour():
    # R2-F1: plinth 0-2.0 m (61 % of the storey) is the taller end shape, still not the wall
    dump = prism(SQUARE10, boxes=[(0, 0.0, 10.0, 0.0, 2.0, 0.1)])
    with pytest.raises(SpecError, match="no section shape"):
        extract_spec(dump, OBJECT)
    q = only_question(dump, at(L0=3.0))
    assert (q["kind"], q["depth_m"], q["heights_m"]) == ("projection", 0.1, [0.0, 2.0])


def test_holes_at_the_storey_ends_are_openings_and_the_contour_stays_strict():
    # R2-F1 / #7: wall missing at x 5-6 near both storey ends: two openings, the ends close by the
    # bridges; the projection between (70 % of the storey) still makes the extractor ask
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, boxes=[(0, 5.0, 6.0, 0.0, 0.5, 0.0), (0, 5.0, 6.0, 2.8, 3.3, 0.0),
                                        (0, 2.0, 3.0, 0.5, 2.8, 0.2)])
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    with pytest.raises(SpecError, match="no section shape is both at the two storey ends"):
        extract_spec(dump_of(b), OBJECT)
    spec, report = extract_spec(dump_of(b), at(L0=0.2))
    got = [(o.x_m, o.sill_m, o.w_m, o.h_m) for o in spec.floors[0].openings]
    assert got == [(5.0, 0.0, 1.0, 0.5), (5.0, 2.8, 1.0, 0.5)]


def test_contour_at_a_height_off_the_closed_sections_is_an_error():
    with pytest.raises(SpecError, match="contour_at_m 5.0 m is not on a closed section"):
        extract_spec(prism(SQUARE10), at(L0=5.0))


def test_dense_wall_rows_keep_the_contour():
    # R2-F2: 8000 rows of vertices 0.825 mm apart must not delete every interval
    b = Mesh("Body")
    rows = np.linspace(0.0, 6.6, 8001)
    pts = np.asarray(SQUARE10, dtype=float)
    for w in range(4):
        a, c = pts[w], pts[(w + 1) % 4]
        for za, zb in zip(rows, rows[1:]):
            b.quad((*a, za), (*c, za), (*c, zb), (*a, zb))
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert close(spec.floors[0].contour, SQUARE10) and close(spec.floors[1].contour, SQUARE10)
    assert report["questions"] == []


def test_projection_on_a_rounded_corner_is_measured_on_its_facet():
    # R2-F3: 0.1 m long, 0.2 m deep projection on a tessellated r 1.5 arc
    r, n = 1.5, 12
    arc = [[10 - r + r * math.cos(a), 10 - r + r * math.sin(a)] for a in np.linspace(0, math.pi / 2, n + 1)]
    contour = [[0, 0], [10, 0], *arc, [0, 10]]
    facet = 2 + 6                                  # wall index of the 7th chord in `contour`
    chord = math.dist(contour[facet], contour[facet + 1])
    u0 = (chord - 0.1) / 2
    q = only_question(prism(contour, boxes=[(facet, u0, u0 + 0.1, 1.0, 1.5, 0.2)]))
    assert q["depth_m"] == pytest.approx(0.2, abs=0.005) and q["length_m"] == pytest.approx(0.1, abs=0.005)


def test_projection_on_a_dropped_small_kink_is_measured_on_its_facet():
    # R2-F3: the 4.5 degree kink is not in the contour, the projection is still 0.2 m deep, 1 m long
    y = 10 * math.tan(math.radians(4.5))
    contour = [[0, 0], [10, 0], [20, y], [20, 10], [0, 10]]
    spec, report = extract_spec(prism(contour, boxes=[(0, 2.0, 3.0, 1.0, 1.5, 0.2)]), OBJECT)
    assert len(spec.floors[0].contour) == 4                     # the 4.5 degree kink is not in the contour
    (q,) = report["questions"]
    assert (q["wall"], q["depth_m"], q["length_m"]) == (0, 0.2, 1.0)


@pytest.mark.parametrize("n", [5, 6, 7])
def test_coarse_true_arcs_are_rounded_corners(n):
    # R2-F4: a quarter circle in 5, 6 or 7 chords is still an r 1.5 corner
    r = 1.5
    arc = [[10 - r + r * math.cos(a), 10 - r + r * math.sin(a)] for a in np.linspace(0, math.pi / 2, n + 1)]
    spec, _ = extract_spec(prism([[0, 0], [10, 0], *arc, [0, 10]]), OBJECT)
    pts = spec.floors[0].contour
    assert len(pts) == 4 and [p for p in pts if len(p) == 3][0][2]["r"] == pytest.approx(1.5, abs=0.02)


def test_close_vertex_rows_do_not_hide_an_element():
    # R3-F1 (review 3 of PR #19): a wall row 0.1 mm below a 0.5 m projection must not hide it
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, boxes=[(0, 2.0, 3.0, 1.0002, 1.5, 0.2)], extra_z=[1.0001])
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    q = only_question(dump_of(b))
    assert (q["wall"], q["depth_m"], q["length_m"], q["facade_share"]) == (0, 0.2, 1.0, 0.1)

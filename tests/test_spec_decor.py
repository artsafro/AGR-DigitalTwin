"""Facade decor in the spec (pattern facade-decor-inset, spec v0.5). Synthetic data; not a real object."""
import copy

import pytest
from pydantic import ValidationError

from dt_ai.spec import Spec, extract_spec
from test_spec_extract import OBJECT, Mesh, box_building


def with_meshes(*boxes):
    """B01-like box plus decor meshes: (name, lo, hi[, material id]) each, one mesh per entry."""
    dump = box_building(canopy=False)
    for name, lo, hi, *mid in boxes:
        m = Mesh(name)
        m.box(lo, hi)
        d = m.dump()
        if mid:
            d["material_ids"] = [mid[0]] * len(d["triangles"])
        dump["meshes"].append(d)
    return dump


def decor_of(dump):
    spec, report = extract_spec(dump, OBJECT)
    return spec, report, [d.model_dump(exclude_none=True) for d in spec.decor]


def test_belt_embedded_on_the_south_wall():
    spec, report, (belt,) = decor_of(with_meshes(("Belt", (0.0, -0.15, 2.405), (10.0, 0.02, 2.705), 26)))
    assert spec.spec_version == "0.5"
    assert belt["kind"] == "band" and belt["level"] == "L0" and belt["wall"] == 0
    assert (belt["x_m"], belt["w_m"], belt["z_m"], belt["h_m"]) == (0.0, 10.0, 2.405, 0.3)
    assert belt["projection_m"] == 0.15 and belt["texture"] is False and belt["material_id"] == 26
    assert report["decor"]["elements"] == 1 and report["attachment_parts_ignored"] == 1


@pytest.mark.parametrize("gap, elements, pieces", [(0.0, 1, 1), (0.02, 1, 2), (0.06, 1, 2), (0.07, 2, 1)])
def test_split_pilaster_merges_up_to_the_seam(gap, elements, pieces):
    """User 2026-10-12: seams up to plate_gap_m x 12 (0.06 m) join pieces of one cross-section on one axis.
    Touching pieces (gap 0) share vertices and are one part already."""
    _, report, decor = decor_of(with_meshes(("P1", (10.0, 4.5, 0.0), (10.12, 5.0, 3.3 - gap)),
                                            ("P2", (10.0, 4.5, 3.3), (10.12, 5.0, 6.6))))
    assert len(decor) == elements and all(d["pieces"] == pieces for d in decor)
    if elements == 1:
        (p,) = decor
        assert p["kind"] == "strip" and p["wall"] == 1
        assert (p["x_m"], p["w_m"], p["z_m"], p["h_m"], p["projection_m"]) == (4.5, 0.5, 0.0, 6.6, 0.12)


def test_pieces_of_another_section_or_axis_stay_apart():
    _, _, decor = decor_of(with_meshes(("P1", (10.0, 4.5, 0.0), (10.12, 5.0, 3.28)),
                                       ("P2", (10.0, 4.5, 3.3), (10.12, 5.1, 6.6)),       # wider
                                       ("P3", (10.0, 6.0, 0.0), (10.18, 6.5, 3.28)),      # deeper
                                       ("P4", (10.0, 6.0, 3.3), (10.12, 6.5, 6.6))))
    assert len(decor) == 4 and all(d["pieces"] == 1 for d in decor)


def test_band_in_a_row_of_pieces():
    tiles = [(f"T{i}", (-0.12, 0.5 + 0.9 * i, 1.0), (0.0, 0.5 + 0.9 * i + 0.88, 1.3)) for i in range(10)]   # 2 cm seams
    _, _, (band,) = decor_of(with_meshes(*tiles))
    assert band["kind"] == "band" and band["pieces"] == 10 and band["w_m"] == 8.98 and band["wall"] == 3


@pytest.mark.parametrize("out, texture", [(0.05, True), (0.10, True), (0.11, False)])
def test_threshold_is_inclusive_and_asks_nothing(out, texture):
    _, report, (band,) = decor_of(with_meshes(("Band", (-out, 0.5, 1.0), (0.0, 9.5, 1.3))))
    assert band["texture"] is texture and band["projection_m"] == out
    assert not [q for q in report["questions"] if q["kind"].startswith("decor")]


def test_free_standing_column():
    _, _, (col,) = decor_of(with_meshes(("Column", (5.8, -1.6, 0.0), (6.2, -1.2, 3.3), 28)))
    assert col["kind"] == "column" and col["footprint"] == [5.8, -1.6, 6.2, -1.2]
    assert (col["z_m"], col["h_m"], col["material_id"]) == (0.0, 3.3, 28) and "wall" not in col


def test_a_vertical_sheet_is_no_column():
    """Found on the real K01 source: a flat vertical plate standing free (no thickness) is an attachment."""
    dump = box_building(canopy=False)
    m = Mesh("Sheet")
    m.quad((5.0, -1.6, 0.0), (5.0, -1.2, 0.0), (5.0, -1.2, 3.0), (5.0, -1.6, 3.0))
    dump["meshes"].append(m.dump())
    spec, report = extract_spec(dump, OBJECT)
    assert spec.decor == [] and report["decor"]["not_decor_parts"] == 1


def test_deep_wall_pieces_are_a_question():
    """Found on the real K01 source: canopies and porches 1.06-1.4 m deep on a wall; the rules do not say."""
    spec, report, _ = decor_of(with_meshes(("Porch", (4.0, -1.4, 0.05), (6.0, 0.0, 2.95))))
    assert spec.decor == []
    (q,) = [q for q in report["questions"] if q["kind"] == "decor-deep"]
    assert q["depth_m"] == 1.4


def test_a_column_off_the_levels_is_no_column():
    """Found on the real K01 source: a ladder cage hanging between levels is an attachment."""
    spec, report, _ = decor_of(with_meshes(("Cage", (5.8, -1.6, 1.0), (6.6, -0.8, 3.5))))
    assert spec.decor == [] and report["decor"]["not_decor_parts"] == 1


def test_canopy_and_off_wall_parts_stay_attachments():
    spec, report = extract_spec(box_building(canopy=True), OBJECT)
    assert spec.decor == [] and spec.spec_version == "0.3" and report["decor"]["not_decor_parts"] == 1


def test_material_id_outside_the_attachment_group_is_not_taken():
    _, _, (belt,) = decor_of(with_meshes(("Belt", (0.0, -0.15, 2.405), (10.0, 0.0, 2.705), 3)))
    assert "material_id" not in belt


def test_a_wall_piece_that_is_no_box_is_a_question():
    dump = box_building(canopy=False)
    m = Mesh("Wedge")                                       # a sloped top face: not axis-aligned
    m.quad((4.0, 0.0, 3.0), (5.0, 0.0, 3.0), (5.0, -0.3, 3.2), (4.0, -0.3, 3.2))
    m.quad((4.0, -0.3, 3.2), (5.0, -0.3, 3.2), (5.0, -0.3, 2.8), (4.0, -0.3, 2.8))
    m.quad((4.0, -0.3, 2.8), (5.0, -0.3, 2.8), (5.0, 0.0, 2.8), (4.0, 0.0, 2.8))
    dump["meshes"].append(m.dump())
    spec, report = extract_spec(dump, OBJECT)
    assert spec.decor == []
    (q,) = [q for q in report["questions"] if q["kind"] == "decor-shape"]
    assert q["levels"] == ["L0"] and q["heights_m"] == [2.8, 3.2]


def test_a_piece_sharing_a_body_vertex_is_welded_into_the_body():
    """Known limit (pattern trap): positions are welded globally, so such a piece is body, not decor."""
    _, _, decor = decor_of(with_meshes(("Band", (-0.12, 0.0, 0.9), (0.0, 10.0, 1.2))))   # corners on body vertices
    assert decor == []


def test_decor_does_not_change_the_body():
    plain, _ = extract_spec(box_building(canopy=False), OBJECT)
    spec, _, _ = decor_of(with_meshes(("Belt", (0.0, -0.15, 2.405), (10.0, 0.02, 2.705)),
                                      ("P1", (10.0, 4.5, 0.0), (10.12, 5.0, 6.6)),
                                      ("Column", (5.8, -1.6, 0.0), (6.2, -1.2, 3.3))))
    assert spec.floors == plain.floors and spec.levels == plain.levels and spec.roof == plain.roof


def spec_doc():
    spec, _, _ = decor_of(with_meshes(("Belt", (0.0, -0.15, 2.405), (10.0, 0.02, 2.705))))
    return spec.model_dump(exclude_none=True)


@pytest.mark.parametrize("change, message", [
    (lambda d: d["decor"][0].update(texture=True), "texture is projection"),
    (lambda d: d["decor"][0].update(footprint=[0, 0, 1, 1]), "no footprint"),
    (lambda d: d["decor"][0].update(wall=9), "the contour has"),
    (lambda d: d["decor"][0].update(level="roof"), "stands on a floor level"),
    (lambda d: d.update(spec_version="0.4"), "decor needs spec_version 0.5"),
    (lambda d: d["decor"].append({"kind": "column", "level": "L0", "w_m": 0.4, "z_m": 0, "h_m": 3,
                                  "footprint": [1, 1, 0, 2]}), "x0 < x1"),
])
def test_model_rules(change, message):
    doc = copy.deepcopy(spec_doc())
    change(doc)
    with pytest.raises(ValidationError, match=message):
        Spec.model_validate(doc)


def test_version_0_5_keeps_glass_and_terraces():
    """Found on the real K01 source: a 0.5 spec keeps glass_w / glass_h (0.3) and terraces (0.4)."""
    doc = spec_doc()
    doc["floors"][0]["openings"][0].update(glass_w=1.0, glass_h=1.0)
    doc["terraces"] = [{"level": "L1", "parapet_h_m": 1.0}]
    assert Spec.model_validate(doc).spec_version == "0.5"


# --- review 1 of PR #74: the detector on synthetic parts, run directly ---------------------------------

import itertools

import numpy as np
from shapely.geometry import Polygon

from dt_ai.spec import decor as dc

LEVELS = [{"name": "L0", "elev_m": 0.0}, {"name": "L1", "elev_m": 3.3}, {"name": "roof", "elev_m": 6.6}]
U_CONTOUR = [[0, 0], [3, 0], [3, 2], [5, 2], [5, 0], [8, 0], [8, 8], [0, 8]]


def parts_of(*meshes):
    """(v, tris, mats, parts) of separate meshes given as Mesh objects."""
    v, tris, parts = [], [], []
    for m in meshes:
        base, first = len(v), len(tris)
        v += m.vertices
        tris += [[a + base, b + base, c + base] for a, b, c in m.triangles]
        parts.append(np.arange(first, len(tris)))
    return np.array(v, float), np.array(tris), np.zeros(len(tris), int), parts


def run(meshes, contours=None):
    contours = contours or [U_CONTOUR, U_CONTOUR]
    v, tris, mats, parts = parts_of(*meshes)
    return dc.extract(v, tris, mats, parts, LEVELS, contours, [Polygon(c) for c in contours], 0.005,
                      frozenset(range(26, 31)))


def box(lo, hi, name="B"):
    m = Mesh(name)
    m.box(lo, hi)
    return m


def test_concave_contour_takes_the_wall_holding_the_piece():
    decor, questions, _ = run([box((1, -0.15, 1), (2, 0, 1.3))])
    (d,) = decor
    assert (d["wall"], d["x_m"]) == (0, 1.0) and not questions


def test_an_l_shaped_solid_is_a_question():
    m = Mesh("L")                                         # front: 1 x 1 minus the upper right quarter
    for (s0, z0, s1, z1) in ((1.0, 1.0, 2.0, 1.5), (1.0, 1.5, 1.5, 2.0)):
        m.box((s0, -0.15, z0), (s1, 0.0, z1))
    decor, questions, _ = run([m])
    assert decor == [] and [q["kind"] for q in questions] == ["decor-shape"]


def test_a_flat_horizontal_sheet_on_a_wall_is_a_question():
    m = Mesh("Sheet")
    m.quad((1, 0, 1), (2, 0, 1), (2, -0.3, 1), (1, -0.3, 1))
    decor, questions, _ = run([m])
    assert decor == [] and [q["kind"] for q in questions] == ["decor-shape"]


def test_a_diagonal_sheet_is_no_column():
    m = Mesh("Diag")
    m.quad((5, -2, 0), (5.4, -1.6, 0), (5.4, -1.6, 3), (5, -2, 3))
    decor, questions, report = run([m])
    assert decor == [] and not questions and report["not_decor_parts"] == 1


def test_a_rotated_or_hollow_column_is_no_column():
    m = Mesh("Hollow")                                    # two opposite sides only
    m.quad((5, -2, 0), (5.4, -2, 0), (5.4, -2, 3), (5, -2, 3))
    m.quad((5.4, -1.6, 0), (5, -1.6, 0), (5, -1.6, 3), (5.4, -1.6, 3))
    decor, _, _ = run([m])
    assert decor == []


def test_l_of_three_tiles_is_asked_whatever_the_order():
    tiles = [box((1.0, -0.15, 1.0), (1.5, 0, 1.5)), box((1.52, -0.15, 1.0), (2.02, 0, 1.5)),
             box((1.0, -0.15, 1.52), (1.5, 0, 2.02))]
    results = set()
    for order in itertools.permutations(tiles):
        decor, questions, _ = run(list(order))
        results.add((tuple(sorted((d["x_m"], d["z_m"], d["w_m"], d["h_m"]) for d in decor)),
                     tuple(q["kind"] for q in questions)))
    assert len(results) == 1
    (decor, kinds), = results
    assert len(decor) == 3 and kinds == ("decor-merge",)


def test_a_full_grid_of_tiles_is_one_element():
    tiles = [box((1 + 0.32 * i, -0.05, 1 + 0.32 * k), (1.3 + 0.32 * i, 0, 1.3 + 0.32 * k)) for i in range(3)
             for k in range(2)]
    decor, questions, _ = run(tiles)
    (d,) = decor
    assert d["pieces"] == 6 and d["texture"] is True and not questions


def test_pieces_across_the_texture_boundary_stay_apart():
    decor, _, _ = run([box((1, -0.100, 1.0), (1.5, 0, 2.0)), box((1, -0.104, 2.02), (1.5, 0, 3.0))])
    assert sorted((d["projection_m"], d["texture"]) for d in decor) == [(0.1, True), (0.104, False)]


def test_a_projection_just_over_the_boundary_is_geometry():
    (d,), _, _ = run([box((1, -0.100049, 1.0), (1.5, 0, 2.0))])
    assert d["projection_m"] == 0.100049 and d["texture"] is False


@pytest.mark.parametrize("upper_y", [1.0, -1.0])
def test_a_strip_crossing_a_storey_must_stay_on_a_wall(upper_y):
    upper = [[0, upper_y], [8, upper_y], [8, 8], [0, 8]]
    lower = [[0, 0], [8, 0], [8, 8], [0, 8]]
    decor, questions, _ = run([box((1, -0.15, 1), (1.5, 0, 5))], contours=[lower, upper])
    assert decor == [] and [q["kind"] for q in questions] == ["decor-shape"]


# --- review 2 of PR #74 ------------------------------------------------------------------------------

def prism(name, xy, z0, z1):
    """A closed vertical prism over the polygon xy (counter-clockwise), quads for sides, fans for caps."""
    m = Mesh(name)
    k = len(xy)
    for i in range(k):
        (ax, ay), (bx, by) = xy[i], xy[(i + 1) % k]
        m.quad((ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1))
    base = len(m.vertices)
    m.vertices += [[float(x), float(y), float(z0)] for x, y in xy] + [[float(x), float(y), float(z1)] for x, y in xy]
    for i in range(1, k - 1):
        m.triangles += [[base, base + i + 1, base + i], [base + k, base + k + i, base + k + i + 1]]
    return m


def test_a_stepped_depth_profile_is_a_question():
    m = prism("Step", [(1, -0.15), (2, -0.15), (2, 0), (1.5, 0), (1.5, -0.05), (1, -0.05)], 1, 2)
    decor, questions, _ = run([m])
    assert decor == [] and [q["kind"] for q in questions] == ["decor-shape"]


def test_an_l_shaped_column_is_no_column():
    m = prism("LCol", [(5, -2), (5.4, -2), (5.4, -1.8), (5.2, -1.8), (5.2, -1.6), (5, -1.6)], 0, 3)
    decor, _, report = run([m])
    assert decor == [] and report["not_decor_parts"] == 1


def test_a_column_inside_an_upper_storey_is_no_column():
    lower = [[0, 0], [8, 0], [8, 8], [0, 8]]
    upper = [[0, -3], [8, -3], [8, 8], [0, 8]]
    decor, _, _ = run([box((5, -2, 0), (5.4, -1.6, 5))], contours=[lower, upper])
    assert decor == []


def test_a_group_over_the_cross_section_tolerance_is_asked():
    pieces = [box((1, -out, 1 + 0.52 * k), (1.5, 0, 1.5 + 0.52 * k)) for k, out in enumerate((0.150, 0.154, 0.158))]
    for order in itertools.permutations(pieces):
        decor, questions, _ = run(list(order))
        assert len(decor) == 3 and [q["kind"] for q in questions] == ["decor-merge"]


def test_merge_questions_are_told_apart_by_place():
    def l_at(x):
        return [box((x, -0.15, 1.0), (x + 0.5, 0, 1.5)), box((x + 0.52, -0.15, 1.0), (x + 1.02, 0, 1.5)),
                box((x, -0.15, 1.52), (x + 0.5, 0, 2.02))]
    flat = [[0, 0], [8, 0], [8, 8], [0, 8]]
    _, questions, _ = run(l_at(1) + l_at(6), contours=[flat, flat])
    assert [q["kind"] for q in questions] == ["decor-merge"] * 2
    assert questions[0]["at"] != questions[1]["at"] and {q["wall"] for q in questions} == {0}


@pytest.mark.parametrize("out", [0.1000001, 0.10000049])
def test_a_submicron_excess_is_still_geometry(out):
    (d,), _, _ = run([box((1, -out, 1.0), (1.5, 0, 2.0))])
    assert d["texture"] is False and d["projection_m"] > 0.1

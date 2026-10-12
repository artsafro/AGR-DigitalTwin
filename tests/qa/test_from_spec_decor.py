"""Engine: facade decor (pattern facade-decor-inset, spec v0.5). Synthetic data; not a real object."""
import json
from pathlib import Path

import numpy as np
import pytest

from dt_ai.geometry.from_spec import BuildError, BuildInputs, build
from dt_ai.spec import extract_spec
from dt_ai.spec.model import Spec
from test_spec_extract import Mesh
from test_geometry_checks import FACADE, PLANE, REVEAL, ROOF

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / "tests/fixtures/spec-b01-v0.3.json").read_text(encoding="utf-8"))
INPUTS = BuildInputs(parapet_thickness_m=0.3, facade_id=FACADE, reveal_id=REVEAL, roof_id=ROOF, opening_id=PLANE)
BELT = {"kind": "band", "level": "L0", "wall": 0, "x_m": 0.0, "w_m": 10.0, "z_m": 2.4, "h_m": 0.3,
        "projection_m": 0.15, "texture": False, "material_id": 26}
PILASTER = {"kind": "strip", "level": "L0", "wall": 1, "x_m": 4.5, "w_m": 0.5, "z_m": 0.0, "h_m": 6.6,
            "projection_m": 0.12, "texture": False, "material_id": 27}
COLUMN = {"kind": "column", "level": "L0", "w_m": 0.4, "z_m": 0.0, "h_m": 3.3, "footprint": [5.8, -1.6, 6.2, -1.2],
          "material_id": 28}
BAND = {"kind": "band", "level": "L0", "wall": 3, "x_m": 0.5, "w_m": 9.0, "z_m": 1.0, "h_m": 0.3,
        "projection_m": 0.05, "texture": True}


def spec(*decor):
    data = json.loads(json.dumps(FIXTURE))
    data["spec_version"] = "0.5"
    data["decor"] = list(decor)
    return Spec.model_validate(data)


def meshes(dump):
    return {m["name"]: m for m in dump["meshes"]}


def test_decor_is_a_separate_mesh_and_the_body_is_not_cut():
    plain = meshes(build(spec(), INPUTS))
    built = meshes(build(spec(BELT, PILASTER, COLUMN, BAND), INPUTS))
    assert set(built) == {"body", "decor"} and set(plain) == {"body"}
    assert built["body"] == plain["body"]                 # identical body: nothing cut, nothing added
    assert len(built["decor"]["polygons"]) == 5 + 5 + 5   # belt, pilaster: 5 faces (back deleted); column: 4 + top
    assert set(built["decor"]["material_ids"]) == {26, 27, 28}


def test_wall_box_is_embedded_and_kept_off_the_window_head():
    v = np.array(meshes(build(spec(BELT), INPUTS))["decor"]["vertices"])
    assert v[:, 2].min() == pytest.approx(2.405)          # window head 2.4 + plate_gap_m 5 mm (pattern)
    assert v[:, 2].max() == pytest.approx(2.7)
    assert v[:, 1].min() == pytest.approx(-0.15) and v[:, 1].max() == pytest.approx(0.02)   # 0.02 m into the wall


def test_texture_elements_build_nothing():
    assert set(meshes(build(spec(BAND), INPUTS))) == {"body"}


def test_column_has_its_top_and_no_bottom():
    m = meshes(build(spec(COLUMN), INPUTS))["decor"]
    v = np.array(m["vertices"])
    tris = np.array(m["triangles"])
    normals = np.cross(v[tris[:, 1]] - v[tris[:, 0]], v[tris[:, 2]] - v[tris[:, 0]])
    assert (normals[:, 2] > 0).sum() == 2 and (normals[:, 2] < 0).sum() == 0


def test_the_extractor_reads_the_built_decor_back():
    dump = build(spec(BELT, PILASTER, COLUMN), INPUTS)
    obj = {"id": "bench-synth-box", "frame": {"to_object": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}}
    back, _ = extract_spec(dump, obj)
    got = sorted((d.kind, d.wall, d.x_m, round(d.z_m, 4), round(d.h_m, 4), d.projection_m, d.material_id)
                 for d in back.decor)
    assert got == sorted([("band", 0, 0.0, 2.405, 0.295, 0.15, 26), ("strip", 1, 4.5, 0.0, 6.6, 0.12, 27),
                          ("column", None, None, 0.0, 3.3, None, 28)])


@pytest.mark.parametrize("decor, message", [
    ([dict(BELT, z_m=2.0)], "covers the opening"),
    ([dict(BELT, material_id=None)], "no material_id"),
    ([dict(COLUMN, footprint=[5.8, -0.4, 6.2, 0.0])], "within 0.005 m of the body"),
    ([BELT, dict(PILASTER, wall=0, x_m=6.0, h_m=2.6)], "side by side or cross"),
    ([dict(PILASTER, wall=0, x_m=3.5, w_m=0.0005, z_m=1.0, h_m=1.0)], "nothing left"),
])
def test_what_the_pattern_does_not_decide_is_an_error(decor, message):
    with pytest.raises(BuildError, match=message):
        build(spec(*decor), INPUTS)


def test_default_decor_id_from_the_build_inputs():
    inputs = BuildInputs(**{**INPUTS.__dict__, "decor_id": 29})
    m = meshes(build(spec(dict(BELT, material_id=None)), inputs))["decor"]
    assert set(m["material_ids"]) == {29}


def test_decor_id_from_object_json():
    obj = {"id": "x", "build": {"parapet_thickness_m": 0.3,
                                "ids": {"facade": 1, "reveal": 6, "roof": 21, "opening": 11, "decor": 26}}}
    assert BuildInputs.from_object(obj).decor_id == 26


# --- checker (twinqa.geometry.checks.check_decor) -----------------------------------------------------

from twinqa.geometry import checks
from twinqa.geometry.mesh import from_dump

DECOR_TOL = {"decor_tol_m": 0.01, "decor_cover_min": 0.95, "weld_m": 0.0001}


def decor_check(dump, sp):
    return checks.check_decor(from_dump(dump), sp, DECOR_TOL, checks.load_ranges())


def problems(report):
    return [p for el in report["details"]["elements"] for p in el["problems"]]


def test_built_decor_passes():
    sp = spec(BELT, PILASTER, COLUMN, BAND)
    report = decor_check(build(sp, INPUTS), sp)
    assert report["status"] == "pass", problems(report)
    assert report["details"]["elements"][0]["opening_gap_m"] == pytest.approx(0.005, abs=1e-4)


def test_no_decor_in_the_spec_passes_and_needs_no_thresholds():
    assert checks.check_decor(from_dump(build(spec(), INPUTS)), spec(), {}, checks.load_ranges())["status"] == "pass"


def test_missing_decor_fails():
    assert "not built" in problems(decor_check(build(spec(), INPUTS), spec(BELT, COLUMN)))


def test_texture_built_as_geometry_fails():
    built = build(spec(dict(BAND, projection_m=0.15, texture=False, material_id=26)), INPUTS)
    assert "texture built as geometry" in problems(decor_check(built, spec(BAND)))


def test_wrong_ids_fail():
    built = build(spec(dict(BELT, material_id=3)), INPUTS)
    assert any(p.startswith("ids [3]") for p in problems(decor_check(built, spec(BELT))))


def test_decor_closer_than_the_gap_to_an_opening_fails():
    dump = build(spec(BELT), INPUTS)
    for p in meshes(dump)["decor"]["vertices"]:
        if abs(p[2] - 2.405) < 1e-9:
            p[2] = 2.401
    assert any("from an opening" in p for p in problems(decor_check(dump, spec(BELT))))


def test_a_body_cut_along_the_outline_fails():
    dump = build(spec(BELT), INPUTS)
    body = meshes(dump)["body"]
    n = len(body["vertices"])
    body["vertices"] += [[5.0, 0.0, 2.405], [5.1, 0.0, 2.405], [5.1, 0.0, 2.5], [5.0, 0.0, 2.5]]
    body["triangles"] += [[n, n + 1, n + 2], [n, n + 2, n + 3]]
    body["material_ids"] += [FACADE, FACADE]
    body["polygon_sizes"] += [4]
    assert any(p.startswith("body cut") for p in problems(decor_check(dump, spec(BELT))))


def test_a_column_missing_a_side_fails():
    dump = build(spec(COLUMN), INPUTS)
    m = meshes(dump)["decor"]
    m["triangles"], m["material_ids"], m["polygon_sizes"] = m["triangles"][2:], m["material_ids"][2:], m["polygon_sizes"][1:]
    assert "not built" in problems(decor_check(dump, spec(COLUMN)))


def test_run_includes_decor():
    sp = spec(BELT)
    model = from_dump(build(sp, INPUTS))
    tol = {**json.loads((ROOT / "benchmark/bench-b01-box/tolerances.json").read_text(encoding="utf-8"))["geometry"],
           **DECOR_TOL, "open_part_groups": ["attachment"]}
    report = checks.run(model, model, sp, tol)
    assert "decor" in {c["id"] for c in report["checks"]}
    assert next(c for c in report["checks"] if c["id"] == "decor")["status"] == "pass"


# --- review 1 of PR #75 ------------------------------------------------------------------------------

@pytest.mark.parametrize("decor, message", [
    ([dict(BELT, x_m=3.5, w_m=1.0, z_m=2.4)], "from the corner of"),          # touches the window's corner
    ([dict(BELT, x_m=3.501, w_m=1.0, z_m=2.401)], "from the corner of"),
    ([dict(COLUMN, z_m=1.0)], "a column stands on its level"),
    ([dict(COLUMN, h_m=1.0)], "a column stands on its level"),
    ([dict(BELT, z_m=8.0)], "runs off the walls"),
    ([dict(BELT, z_m=-1.0)], "runs off the walls"),
])
def test_review_1_build_errors(decor, message):
    with pytest.raises(BuildError, match=message):
        build(spec(*decor), INPUTS)


@pytest.mark.parametrize("element", [dict(PILASTER, x_m=0.0, h_m=3.3), dict(BELT, z_m=3.3, h_m=0.3)])
def test_body_lines_under_decor_are_no_cut(element):
    sp = spec(element)
    report = decor_check(build(sp, INPUTS), sp)
    assert report["status"] == "pass", problems(report)


def test_geometry_over_a_texture_rectangle_fails():
    big = dict(BAND, x_m=0.25, w_m=9.5, z_m=0.5, h_m=1.5, projection_m=0.15, texture=False, material_id=26)
    assert "texture built as geometry" in problems(decor_check(build(spec(big), INPUTS), spec(BAND)))


def test_decor_the_spec_does_not_list_fails():
    strip = dict(PILASTER, z_m=1.0, h_m=2.0)
    built = build(spec(strip, dict(strip, wall=3)), INPUTS)
    assert any("the spec does not list" in p for p in problems(decor_check(built, spec(strip))))


def test_a_full_width_belt_passes_every_check():
    """The inset end faces at the building corners start at the wall face: no overlap with the next wall."""
    sp = spec(BELT)
    model = from_dump(build(sp, INPUTS))
    tol = {**json.loads((ROOT / "benchmark/bench-b01-box/tolerances.json").read_text(encoding="utf-8"))["geometry"],
           **DECOR_TOL, "open_part_groups": ["attachment"]}
    report = checks.run(model, model, sp, tol)
    assert report["passed"], [(c["id"], c["value"]) for c in report["checks"] if c["status"] != "pass"]


def test_a_concave_corner_end_is_an_error():
    data = json.loads(json.dumps(FIXTURE))
    data["spec_version"] = "0.5"
    l_shape = [[0, 0], [10, 0], [10, 10], [5, 10], [5, 5], [0, 5]]
    for f in data["floors"]:
        if f.get("contour"):
            f["contour"] = l_shape
    data["decor"] = [dict(BELT, wall=4, x_m=0.0, w_m=5.0, z_m=1.0, material_id=26)]   # wall 4 ends at the concave (5, 5)
    with pytest.raises(BuildError, match="concave corner"):
        build(Spec.model_validate(data), INPUTS)


# --- meeting of two decor elements (user 2026-10-12): the subordinate runs 0.02 m into the main one ------

def decor_faces(dump, mid=None):
    m = meshes(dump)["decor"]
    v = np.array(m["vertices"])
    return [v[q] for k, q in enumerate(m["polygons"]) if mid is None or m["material_ids"][2 * k] == mid]


@pytest.mark.parametrize("strip, z_end, hidden", [
    (dict(PILASTER, wall=0, x_m=6.0, z_m=0.0, h_m=2.4), ("top", 2.425), 2),       # under the belt (moved to 2.405)
    (dict(PILASTER, wall=0, x_m=6.0, z_m=2.7, h_m=0.6), ("bottom", 2.68), 1),     # on top of the belt
])
def test_a_strip_runs_into_the_belt(strip, z_end, hidden):
    plain = meshes(build(spec(), INPUTS))["body"]
    dump = build(spec(BELT, strip), INPUTS)
    assert meshes(dump)["body"] == plain                              # the body is not cut
    faces = decor_faces(dump)
    assert len(faces) == 5 + 4                                         # belt whole, the strip without its hidden end
    zs = np.concatenate([q[:, 2] for q in decor_faces(dump, 27)])
    end, z = z_end
    assert (zs.max() if end == "top" else zs.min()) == pytest.approx(z)
    assert len(decor_faces(dump, 26)) == 5                             # the main element is not cut


def test_the_longer_of_one_rank_is_main():
    short = dict(BELT, x_m=6.0, w_m=2.0, z_m=2.45, h_m=0.2, projection_m=0.1 + 0.02, material_id=27)
    long_ = dict(BELT, x_m=0.5, w_m=5.5, z_m=2.4, h_m=0.3)
    faces = decor_faces(build(spec(long_, short), INPUTS))
    xs = np.concatenate([q[:, 0] for q in faces])
    assert xs.min() == pytest.approx(0.5) and len(faces) == 5 + 4
    short_faces = [q for q in faces if q[:, 0].max() <= 8.0 + 1e-9 and q[:, 0].min() >= 5.98 - 1e-9]
    assert min(q[:, 0].min() for q in short_faces) == pytest.approx(5.98)   # 0.02 m into the long one


@pytest.mark.parametrize("decor, message", [
    ([BELT, dict(PILASTER, wall=0, x_m=6.0, z_m=0.0, h_m=2.4, projection_m=0.2)], "stands out"),
    ([dict(BELT, x_m=0.5, w_m=2.0), dict(BELT, x_m=2.5, w_m=2.0, z_m=2.45, h_m=0.2, material_id=27)], "one length"),
    ([dict(BELT, x_m=8.0, w_m=2.0, z_m=1.0), dict(PILASTER, x_m=0.0, w_m=2.0, z_m=1.0, h_m=0.3, kind="band",
                                                    projection_m=0.15)], "one rank and one length"),
])
def test_meetings_the_rule_does_not_cover(decor, message):
    with pytest.raises(BuildError, match=message):
        build(spec(*decor), INPUTS)


UNDER = dict(PILASTER, wall=0, x_m=6.0, z_m=0.0, h_m=2.4)


def test_a_run_in_meeting_reads_back_and_passes_the_checker():
    sp = spec(BELT, UNDER)
    dump = build(sp, INPUTS)
    report = decor_check(dump, sp)
    assert report["status"] == "pass", problems(report)
    obj = {"id": "bench-synth-box", "frame": {"to_object": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}}
    back, rep = extract_spec(dump, obj)
    strip = next(d for d in back.decor if d.kind == "strip")
    assert (strip.z_m, round(strip.h_m, 4)) == (0.0, 2.405)        # clipped at the belt's bottom, not run-in
    assert not [q for q in rep["questions"] if q["kind"].startswith("decor")]


def test_a_butt_joint_fails():
    """A closed strip whose top lies in the plane of the belt's bottom: a butt joint, not a run-in."""
    dump = build(spec(BELT, dict(UNDER, h_m=2.3)), INPUTS)
    for p in meshes(dump)["decor"]["vertices"]:
        if abs(p[2] - 2.3) < 1e-9:
            p[2] = 2.405
    assert any(p.startswith("butt joint") for p in problems(decor_check(dump, spec(BELT, UNDER))))


def test_a_run_in_over_the_inset_fails():
    sp = spec(BELT, UNDER)
    dump = build(sp, INPUTS)
    for p in meshes(dump)["decor"]["vertices"]:
        if abs(p[2] - 2.425) < 1e-9:
            p[2] = 2.46                                                 # 0.055 m into the belt
    assert any("over decor_inset_m" in p for p in problems(decor_check(dump, sp)))


def test_two_belts_at_a_corner_the_longer_runs_on():
    """User 2026-10-12: of one rank at a corner the longer continues, the other runs into it."""
    long_ = dict(BELT, x_m=6.0, w_m=4.0, z_m=1.0, h_m=0.3, projection_m=0.15)                 # wall 0, ends at (10, 0)
    short = dict(BELT, wall=1, x_m=0.0, w_m=2.0, z_m=1.0, h_m=0.3, projection_m=0.12, material_id=27)   # wall 1
    sp = spec(long_, short)
    dump = build(sp, INPUTS)
    main = np.concatenate(decor_faces(dump, 26))
    other = np.concatenate(decor_faces(dump, 27))
    assert main[:, 0].max() == pytest.approx(10.12)                    # past the corner by the other's projection
    assert other[:, 1].min() == pytest.approx(0.02)                    # from the main one's back plane
    assert len(decor_faces(dump, 26)) == 5 and len(decor_faces(dump, 27)) == 4   # equal height: the other closes the back
    report = decor_check(dump, sp)
    assert report["status"] == "pass", problems(report)
    model = from_dump(dump)
    tol = {**json.loads((ROOT / "benchmark/bench-b01-box/tolerances.json").read_text(encoding="utf-8"))["geometry"],
           **DECOR_TOL, "open_part_groups": ["attachment"]}
    full = checks.run(model, model, sp, tol)
    assert full["passed"], [(c["id"], c["value"]) for c in full["checks"] if c["status"] != "pass"]


def test_a_corner_meeting_reads_back_as_the_source():
    long_ = dict(BELT, x_m=6.0, w_m=4.0, z_m=1.0, h_m=0.3, projection_m=0.15)
    short = dict(BELT, wall=1, x_m=0.0, w_m=2.0, z_m=1.0, h_m=0.3, projection_m=0.12, material_id=27)
    obj = {"id": "bench-synth-box", "frame": {"to_object": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}}
    back, rep = extract_spec(build(spec(long_, short), INPUTS), obj)
    got = sorted((d.wall, round(d.x_m, 4), round(d.w_m, 4), d.projection_m, d.material_id) for d in back.decor)
    assert got == [(0, 6.0, 4.0, 0.15, 26), (1, 0.0, 2.0, 0.12, 27)]
    assert not [q for q in rep["questions"] if q["kind"].startswith("decor")]


# --- review 2 of PR #75 ------------------------------------------------------------------------------

FULL_TOL = {**json.loads((ROOT / "benchmark/bench-b01-box/tolerances.json").read_text(encoding="utf-8"))["geometry"],
            **DECOR_TOL, "open_part_groups": ["attachment"]}
CORNER_MAIN = dict(BELT, x_m=6.0, w_m=4.0, z_m=1.0, h_m=0.3, projection_m=0.15)
CORNER_SUB = dict(BELT, wall=1, x_m=0.0, w_m=2.0, z_m=1.0, h_m=0.3, projection_m=0.12, material_id=27)


def test_an_unlisted_box_next_to_an_element_fails():
    strip = dict(PILASTER, z_m=1.0, h_m=2.0)
    built = build(spec(strip, dict(strip, x_m=5.02, w_m=0.02, projection_m=0.11)), INPUTS)
    assert any("the spec does not list" in p for p in problems(decor_check(built, spec(strip))))


def test_a_corner_run_in_over_the_inset_fails():
    sp = spec(CORNER_MAIN, CORNER_SUB)
    dump = build(sp, INPUTS)
    m = meshes(dump)["decor"]
    for k, q in enumerate(m["polygons"]):
        if m["material_ids"][2 * k] == 27:
            for i in q:
                if abs(m["vertices"][i][1] - 0.02) < 1e-9:
                    m["vertices"][i][1] = -0.04            # 60 mm past the main element's back plane
    assert decor_check(dump, sp)["status"] == "fail"


def test_three_belts_round_two_corners_read_back():
    walls = [dict(BELT, x_m=0.0, w_m=10.0, z_m=3.0, h_m=0.2, projection_m=0.15),
             dict(BELT, wall=1, x_m=0.0, w_m=2.0, z_m=3.0, h_m=0.2, projection_m=0.12, material_id=27),
             dict(BELT, wall=3, x_m=8.0, w_m=2.0, z_m=3.0, h_m=0.2, projection_m=0.12, material_id=28)]
    sp = spec(*walls)
    dump = build(sp, INPUTS)
    assert decor_check(dump, sp)["status"] == "pass", problems(decor_check(dump, sp))
    obj = {"id": "bench-synth-box", "frame": {"to_object": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}}
    back, _ = extract_spec(dump, obj)
    assert sorted((d.wall, round(d.x_m, 4), round(d.w_m, 4)) for d in back.decor) == [(0, 0.0, 10.0), (1, 0.0, 2.0),
                                                                                     (3, 8.0, 2.0)]


def test_a_corner_pilaster_passes_every_check():
    sp = spec(dict(PILASTER, x_m=0.0, h_m=3.3))
    model = from_dump(build(sp, INPUTS))
    report = checks.run(model, model, sp, FULL_TOL)
    assert report["passed"], [(c["id"], c["value"]) for c in report["checks"] if c["status"] != "pass"]


def test_a_full_width_band_on_a_propagated_body_line_is_no_cut():
    sp = spec(dict(BELT, wall=2, x_m=0.0, w_m=10.0, z_m=2.4, h_m=0.3))
    report = decor_check(build(sp, INPUTS), sp)
    assert report["status"] == "pass", problems(report)


def test_a_texture_element_alone_passes():
    report = decor_check(build(spec(BAND), INPUTS), spec(BAND))
    assert report["status"] == "pass", problems(report)


@pytest.mark.parametrize("decor, message", [
    ([dict(COLUMN, footprint=[5.8, -0.401, 6.2, -0.001])], "within 0.005 m of the body"),
    ([dict(COLUMN, footprint=[5.8, -0.404, 6.2, -0.004])], "within 0.005 m of the body"),
    ([dict(BELT, wall=3, x_m=1.0, w_m=5.0, z_m=1.0, h_m=0.01), dict(PILASTER, wall=3, x_m=3.0, w_m=0.2, z_m=0.0, h_m=1.0)],
     "no deeper than the run-in"),
])
def test_review_2_build_errors(decor, message):
    with pytest.raises(BuildError, match=message):
        build(spec(*decor), INPUTS)


def test_an_oblique_corner_meeting_is_an_error():
    data = json.loads(json.dumps(FIXTURE))
    data["spec_version"] = "0.5"
    data["roof"] = None
    shape = [[0, 0], [10, 0], [10, 5], [8, 10], [0, 10]]
    for f in data["floors"]:
        if f.get("contour"):
            f["contour"] = shape
            f["openings"] = []
    data["decor"] = [dict(BELT, wall=1, x_m=1.0, w_m=4.0, z_m=1.0), dict(BELT, wall=2, x_m=0.0, w_m=2.0, z_m=1.0,
                                                                          projection_m=0.12, material_id=27)]
    with pytest.raises(BuildError, match="oblique corner"):
        build(Spec.model_validate(data), INPUTS)


# --- corner of different heights (user 2026-10-12): the back is deleted only where it is set into the wall --

@pytest.mark.parametrize("z_m, h_m", [(1.0, 0.3), (1.05, 0.2)])        # equal height, the other lower
def test_a_corner_with_the_other_of_equal_or_lower_height(z_m, h_m):
    other = dict(CORNER_SUB, z_m=z_m, h_m=h_m)
    sp = spec(CORNER_MAIN, other)
    dump = build(sp, INPUTS)
    back = [q for q in decor_faces(dump, 26) if np.allclose(q[:, 1], 0.02)]   # the main one's back past the corner
    assert len(back) == (0 if h_m == 0.3 else 2)                              # above and below a lower other one
    assert all(q[:, 0].min() == pytest.approx(10.0) and q[:, 0].max() == pytest.approx(10.12) for q in back)
    assert decor_check(dump, sp)["status"] == "pass", problems(decor_check(dump, sp))
    model = from_dump(dump)
    full = checks.run(model, model, sp, FULL_TOL)
    assert full["passed"], [(c["id"], c["value"]) for c in full["checks"] if c["status"] != "pass"]
    obj = {"id": "bench-synth-box", "frame": {"to_object": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}}
    got, rep = extract_spec(dump, obj)
    assert sorted((d.wall, round(d.x_m, 4), round(d.w_m, 4), round(d.z_m, 4), round(d.h_m, 4)) for d in got.decor) ==         [(0, 6.0, 4.0, 1.0, 0.3), (1, 0.0, 2.0, z_m, h_m)]
    assert not [q for q in rep["questions"] if q["kind"].startswith("decor")]


def test_a_corner_with_the_other_higher_is_the_decor_corner_question():
    with pytest.raises(BuildError, match="decor-corner"):
        build(spec(CORNER_MAIN, dict(CORNER_SUB, z_m=0.9, h_m=0.5)), INPUTS)


def test_a_source_corner_with_the_other_higher_is_asked():
    """An L part whose shorter arm is higher than the longer one: the decor-corner question, nothing guessed."""
    dump = build(spec(), INPUTS)
    m = Mesh("Corner")
    m.box((6.0, -0.15, 1.0), (10.12, 0.02, 1.3))           # the longer arm, run on past the corner
    m.box((9.98, 0.02, 0.9), (10.12, 2.0, 1.4))            # the shorter arm, higher
    dump["meshes"].append(m.dump())
    obj = {"id": "bench-synth-box", "frame": {"to_object": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}}
    got, rep = extract_spec(dump, obj)
    assert [(d.wall, d.x_m, d.w_m) for d in got.decor] == [(0, 6.0, 4.0)]          # the main one is read
    assert [q["kind"] for q in rep["questions"] if q["kind"].startswith("decor")] == ["decor-corner"]


# --- review 3 of PR #75 ------------------------------------------------------------------------------

def moved(dump, mid, axis, old, new):
    m = meshes(dump)["decor"]
    for k, q in enumerate(m["polygons"]):
        if m["material_ids"][2 * k] == mid:
            for i in q:
                if abs(m["vertices"][i][axis] - old) < 1e-9:
                    m["vertices"][i][axis] = new
    return dump


def test_shallow_geometry_over_a_texture_element_fails():
    dump = moved(build(spec(dict(BAND, projection_m=0.15, texture=False, material_id=29)), INPUTS), 29, 0, -0.15, -0.05)
    assert "texture built as geometry" in problems(decor_check(dump, spec(BAND)))


def test_an_unreadable_extra_box_fails():
    strip = dict(PILASTER, z_m=1.0, h_m=2.0)
    extra = dict(BELT, wall=3, x_m=1.0, w_m=3.0, z_m=1.0, h_m=0.3, projection_m=0.15)
    dump = moved(build(spec(strip, extra), INPUTS), 26, 0, 0.02, 0.06)     # its back 60 mm into the body
    assert decor_check(dump, spec(strip))["status"] == "fail"


def test_a_body_line_on_another_wall_does_not_excuse_a_cut():
    dump = build(spec(BELT), INPUTS)
    body = meshes(dump)["body"]
    for quad in ([[5.0, 0.0, 2.405], [5.1, 0.0, 2.405], [5.1, 0.0, 2.5], [5.0, 0.0, 2.5]],      # on the belt's outline
                 [[5.0, 10.0, 2.405], [4.9, 10.0, 2.405], [4.9, 10.0, 2.5], [5.0, 10.0, 2.5]]):  # the opposite wall
        n = len(body["vertices"])
        body["vertices"] += quad
        body["triangles"] += [[n, n + 1, n + 2], [n, n + 2, n + 3]]
        body["material_ids"] += [FACADE, FACADE]
        body["polygon_sizes"] += [4]
    assert any(p.startswith("body cut") for p in problems(decor_check(dump, spec(BELT))))


def test_a_horizontal_run_in_into_a_thin_but_long_band_builds():
    sp = spec(dict(BELT, wall=3, x_m=1.0, w_m=5.0, z_m=1.0, h_m=0.015), dict(BELT, wall=3, x_m=6.0, w_m=1.0,
                                                                             z_m=1.0025, h_m=0.01, projection_m=0.12,
                                                                             material_id=27))
    report = decor_check(build(sp, INPUTS), sp)
    assert report["status"] == "pass", problems(report)


def wide_spec(*decor):
    data = json.loads(json.dumps(FIXTURE))
    data["spec_version"] = "0.5"
    for f in data["floors"]:
        if f.get("contour"):
            f["contour"] = [[0, 0], [20, 0], [20, 10], [0, 10]]
            f["openings"] = []
    data["decor"] = list(decor)
    return Spec.model_validate(data)


def test_priority_uses_the_original_lengths():
    sp = wide_spec(dict(BELT, x_m=1.0, w_m=5.0, z_m=1.0), dict(BELT, x_m=6.0, w_m=4.99, z_m=1.0, projection_m=0.12,
                                                               material_id=27),
                   dict(BELT, x_m=10.99, w_m=5.0, z_m=1.0, material_id=28))
    report = decor_check(build(sp, INPUTS), sp)
    assert report["status"] == "pass", problems(report)


@pytest.mark.parametrize("decor, message", [
    ([dict(PILASTER, wall=0, x_m=9.5, w_m=0.5, z_m=0.0, h_m=3.0), dict(PILASTER, wall=1, x_m=0.0, w_m=0.3, z_m=0.0,
                                                                       h_m=3.0, material_id=28)], "one rank and one length"),
    ([dict(PILASTER, wall=3, x_m=3.0, w_m=0.004, z_m=0.5, h_m=2.0)], "would not read it back"),
    ([dict(BELT, wall=3, x_m=1.0, w_m=5.0, z_m=1.0, projection_m=0.800001)], "would not read it back"),
])
def test_review_3_build_errors(decor, message):
    with pytest.raises(BuildError, match=message):
        build(spec(*decor), INPUTS)


# --- PR #76: attachments are no decor ------------------------------------------------------------------

def test_attachments_beside_decor_are_not_flagged():
    """K01 (PR #76): an attachment candidate over 0.8 m and a flat rung set into the wall are no decor."""
    sp = spec(BELT)
    dump = build(sp, INPUTS)
    porch = Mesh("Porch")
    porch.box((5.0, -1.4, 0.05), (7.0, 0.0, 2.3))
    rung = Mesh("Rung")
    rung.quad((9.0, -0.3, 4.0), (9.0, 0.2, 4.0), (9.0, 0.2, 4.03), (9.0, -0.3, 4.03))
    dump["meshes"] += [porch.dump(), rung.dump()]
    report = decor_check(dump, sp)
    assert report["status"] == "pass", problems(report)


# --- decor ids by material (user 2026-10-12): metal 16-20 or 26-30, one group per element -----------------

@pytest.mark.parametrize("mid, ok", [(17, True), (26, True), (3, False)])
def test_decor_id_group_by_material(mid, ok):
    sp = spec(dict(BELT, material_id=mid))
    report = decor_check(build(sp, INPUTS), sp)
    assert (report["status"] == "pass") == ok, problems(report)


def test_unlisted_decor_running_past_a_corner_fails():
    """Review 2 of PR #76: a box set 0.06 m in and running 11 mm past the wall end is unlisted decor."""
    strip = dict(PILASTER, z_m=1.0, h_m=2.0)
    dump = build(spec(strip), INPUTS)
    extra = Mesh("Extra")
    extra.box((8.0, -0.15, 1.0), (10.011, 0.06, 1.3))
    dump["meshes"].append(extra.dump())
    assert decor_check(dump, spec(strip))["status"] == "fail"


def test_unlisted_decor_running_far_past_a_corner_fails():
    """Review 3 of PR #76: the same box 0.801 m past the wall end is still unlisted decor."""
    strip = dict(PILASTER, z_m=1.0, h_m=2.0)
    dump = build(spec(strip), INPUTS)
    extra = Mesh("Extra")
    extra.box((8.0, -0.15, 1.0), (10.801, 0.06, 1.3))
    dump["meshes"].append(extra.dump())
    assert decor_check(dump, spec(strip))["status"] == "fail"


def test_unlisted_box_set_deep_into_the_body_fails():
    """User 2026-10-12 (follow-up to #76): no depth bound by number; a box 0.7 m into the body on one wall
    still lies inside the storey contour behind that wall, so it is unlisted decor."""
    strip = dict(PILASTER, z_m=1.0, h_m=2.0)
    dump = build(spec(strip), INPUTS)
    extra = Mesh("Extra")
    extra.box((2.0, -0.15, 1.0), (3.0, 0.7, 1.3))
    dump["meshes"].append(extra.dump())
    assert decor_check(dump, spec(strip))["status"] == "fail"


def test_box_reaching_across_the_body_is_no_decor():
    """A box through the whole body (like a coping ring round the roof) leaves the storey contour behind the
    wall: an attachment, not unlisted decor."""
    strip = dict(PILASTER, z_m=1.0, h_m=2.0)
    dump = build(spec(strip), INPUTS)
    extra = Mesh("Through")
    extra.box((2.0, -0.15, 1.0), (3.0, 10.15, 1.3))
    dump["meshes"].append(extra.dump())
    report = decor_check(dump, spec(strip))
    assert report["status"] == "pass", problems(report)


L_SHAPE = [[0, 0], [10, 0], [10, 4], [6, 4], [6, 10], [0, 10]]   # concave corner at (6, 4), walls 2 and 3


def l_spec(*decor):
    data = json.loads(json.dumps(FIXTURE))
    data["spec_version"] = "0.5"
    for f in data["floors"]:
        if "contour" in f:
            f["contour"], f["openings"] = L_SHAPE, []
    data["decor"] = list(decor)
    return Spec.model_validate(data)


L_STRIP = dict(PILASTER, wall=1, x_m=1.5, z_m=1.0, h_m=2.0)


@pytest.mark.parametrize("lo, hi", [
    ((5.0, 3.94, 1.0), (8.0, 4.15, 1.3)),      # on wall 2, run into the concave corner and on into the wing
    ((5.94, 3.0, 1.0), (6.15, 5.0, 1.3)),      # on wall 3, run back past the concave corner into the body
    ((6.5, 3.3, 1.0), (8.0, 4.15, 1.3)),       # on wall 2 by the concave corner, 0.7 m into the body
])
def test_unlisted_decor_at_a_concave_corner_fails(lo, hi):
    """User 2026-10-12 (#78): the embedded part is judged against the body, not one wall's span."""
    sp = l_spec(L_STRIP)
    dump = build(sp, INPUTS)
    extra = Mesh("Extra")
    extra.box(lo, hi)
    dump["meshes"].append(extra.dump())
    assert decor_check(dump, sp)["status"] == "fail"


def test_box_through_the_body_at_a_concave_corner_is_no_decor():
    sp = l_spec(L_STRIP)
    dump = build(sp, INPUTS)
    extra = Mesh("Through")
    extra.box((7.0, -0.15, 1.0), (8.0, 4.15, 1.3))
    dump["meshes"].append(extra.dump())
    report = decor_check(dump, sp)
    assert report["status"] == "pass", problems(report)

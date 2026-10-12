"""Engine: facade decor (pattern facade-decor-inset, spec v0.5). Synthetic data; not a real object."""
import json
from pathlib import Path

import numpy as np
import pytest

from dt_ai.geometry.from_spec import BuildError, BuildInputs, build
from dt_ai.spec import extract_spec
from dt_ai.spec.model import Spec
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
    ([dict(COLUMN, footprint=[5.8, -0.4, 6.2, 0.0])], "touches the body"),
    ([BELT, dict(PILASTER, wall=0, x_m=6.0, h_m=2.6)], "touch or overlap"),
    ([BELT, dict(PILASTER, wall=0, x_m=6.0, z_m=2.7, h_m=0.5)], "touch or overlap"),
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

DECOR_TOL = {"decor_tol_m": 0.01, "decor_cover_min": 0.95}


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

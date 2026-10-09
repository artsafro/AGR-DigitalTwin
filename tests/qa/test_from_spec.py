"""Engine from_spec (HARNESS_PLAN §9): spec -> model -> benchmark checkers, before the real B01 etalon.

The etalon here is the SYNTHETIC box of test_geometry_checks (not the user's etalon, issue #12);
the spec is tests/fixtures/spec-b01-v0.3.json. Build inputs the spec does not carry (parapet
thickness, material IDs) are given explicitly, as `jobs/<object>/materials.json` will.
"""
import json
from pathlib import Path

import numpy as np
import pytest

from dt_ai.geometry.from_spec import BuildError, BuildInputs, build
from dt_ai.spec.model import Spec
from test_geometry_checks import FACADE, PLANE, REVEAL, ROOF, TOL, box_dump
from twinqa.geometry import checks
from twinqa.geometry.mesh import edge_uses, from_dump, weld

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / "tests/fixtures/spec-b01-v0.3.json").read_text(encoding="utf-8"))
INPUTS = BuildInputs(parapet_thickness_m=0.3, facade_id=FACADE, reveal_id=REVEAL, roof_id=ROOF, opening_id=PLANE)


def spec(**changes):
    data = json.loads(json.dumps(FIXTURE))
    for key, value in changes.items():
        data[key] = value
    return Spec.model_validate(data)


def by_id(report):
    return {c["id"]: c for c in report["checks"]}


def test_b01_spec_builds_a_model_that_passes_every_check_against_the_synthetic_etalon():
    model = from_dump(build(spec(), INPUTS))
    report = checks.run(model, from_dump(box_dump()), spec(), TOL)
    assert report["passed"], [(c["id"], c["value"]) for c in report["checks"] if c["status"] != "pass"]
    assert [o["cover"] for o in by_id(report)["opening_planes"]["details"]["openings"]] == [1.0, 1.0]
    assert by_id(report)["silhouettes"]["value"] == 1.0


def test_model_is_all_quads_welded_and_open_only_at_the_bottom():
    dump = build(spec(), INPUTS)
    body = dump["meshes"][0]
    assert set(body["polygon_sizes"]) == {4} and len(body["triangles"]) == 2 * len(body["polygon_sizes"])
    soup = from_dump(dump)
    ids = weld(soup.vertices, 1e-4)
    edges, counts, _ = edge_uses(soup.triangles, ids)
    assert counts.max() <= 2                                   # no T-junction or fin
    open_z = soup.vertices[np.unique(ids, return_index=True)[1]][edges[counts == 1].ravel(), 2]
    assert np.allclose(open_z, 0.0)                            # only the bottom ring is open
    assert {lv["name"] for lv in dump["helpers"]} == {"LEVEL_L0", "LEVEL_L1", "LEVEL_roof"}


def test_faces_point_out_and_up():
    soup = from_dump(build(spec(), INPUTS))
    c = soup.corners()
    n = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
    centre = c.mean(1)
    walls = (soup.material_ids == FACADE)
    out = centre[walls, :2] - [5, 5]
    assert np.all(np.einsum("ij,ij->i", n[walls, :2], out) > 0)
    flat = soup.material_ids == ROOF
    horizontal = flat & (np.abs(n[:, 2]) > 0)
    assert np.all(n[horizontal, 2] > 0)


def test_windows_on_other_walls_match_the_etalon_built_the_same_way():
    # wall 2 runs from (10, 10) to (0, 10): x_m is measured from its start point
    data = json.loads(json.dumps(FIXTURE))
    data["floors"][0]["openings"].append({**data["floors"][0]["openings"][0], "wall": 2, "x_m": 6.0, "w_m": 1.0})
    data["floors"][0]["openings"].append({**data["floors"][0]["openings"][0], "wall": 1, "x_m": 4.0, "sill_m": 0.0,
                                          "h_m": 2.1, "kind": "door"})
    s = Spec.model_validate(data)
    windows = [(0, 2.0, 3.5, 0.9, 2.4), (2, 6.0, 7.0, 0.9, 2.4), (1, 4.0, 5.5, 0.0, 2.1),
               (0, 2.0, 3.5, 4.2, 5.7), (2, 6.0, 7.0, 4.2, 5.7), (1, 4.0, 5.5, 3.3, 5.4)]
    report = checks.run(from_dump(build(s, INPUTS)), from_dump(box_dump(windows=windows)), s, TOL)
    assert report["passed"], report["failed"] + report["not_measured"]
    assert len(by_id(report)["opening_planes"]["details"]["openings"]) == 6


def test_plane_id_from_the_opening_then_its_type_then_the_default():
    data = json.loads(json.dumps(FIXTURE))
    data["floors"][0]["openings"][0]["material_id"] = 12
    soup = from_dump(build(Spec.model_validate(data), INPUTS))
    assert 12 in set(soup.material_ids.tolist()) and PLANE not in set(soup.material_ids.tolist())
    by_type = BuildInputs(**{**INPUTS.__dict__, "opening_ids_by_type": {5: 13}})
    assert 13 in set(from_dump(build(spec(), by_type)).material_ids.tolist())


def test_grille_gets_no_hole():
    data = json.loads(json.dumps(FIXTURE))
    data["floors"][0]["openings"][0]["kind"] = "grille"
    soup = from_dump(build(Spec.model_validate(data), INPUTS))
    assert REVEAL not in set(soup.material_ids.tolist()) and PLANE not in set(soup.material_ids.tolist())


@pytest.mark.parametrize("change, message", [
    ({"contour": [[0, 0], [10, 0], [10, 10, {"r": 1.0}], [0, 10]]}, "rounded corners"),
    ({"contour": [[0, 0], [10, 0], [12, 10], [0, 10]]}, "not axis-parallel"),
])
def test_what_this_step_cannot_build_is_an_error_not_a_guess(change, message):
    data = json.loads(json.dumps(FIXTURE))
    data["floors"][0].update(change)
    with pytest.raises(BuildError, match=message):
        build(Spec.model_validate(data), INPUTS)


def test_different_floor_contours_are_an_error():
    data = json.loads(json.dumps(FIXTURE))
    data["floors"][1] = {"level": "L1", "contour": [[0, 0], [8, 0], [8, 10], [0, 10]], "openings": []}
    with pytest.raises(BuildError, match="different contours"):
        build(Spec.model_validate(data), INPUTS)

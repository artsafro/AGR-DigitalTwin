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


def t_junctions(dump):
    """Vertices lying strictly inside an edge of another face (a geometric T-junction)."""
    soup = from_dump(dump)
    v = soup.vertices
    edges = {tuple(sorted((int(a), int(b)))) for t in soup.triangles for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))}
    hits = 0
    for a, b in edges:
        p, q = v[a], v[b]
        d = q - p
        length2 = float(d @ d)
        s = (v - p) @ d / length2
        off = np.linalg.norm(v - p - np.outer(s, d), axis=1)
        hits += int(np.sum((s > 1e-6) & (s < 1 - 1e-6) & (off < 1e-6)))
    return hits


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
    assert counts.max() <= 2                                   # no fin
    assert t_junctions(dump) == 0
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


# Codex review 1 of PR #50


def edited(edit):
    data = json.loads(json.dumps(FIXTURE))
    edit(data)
    return Spec.model_validate(data)


@pytest.mark.parametrize("edit, message", [
    (lambda d: d["floors"][0]["openings"][0].update({"plane_conflict": True}), "plane_conflict"),
    (lambda d: d["floors"][0]["openings"][0].update({"x_m": 0.0}), "wall end"),
    (lambda d: d["floors"][0]["openings"][0].update({"x_m": 8.5}), "wall end"),
    (lambda d: d["floors"][0]["openings"][0].update({"depth_m": 0.0}), "depth 0"),
    (lambda d: d["floors"][0]["openings"].append({**d["floors"][0]["openings"][0], "x_m": 3.5}), "touch or overlap"),
    (lambda d: d["floors"][0]["openings"].append({**d["floors"][0]["openings"][0], "x_m": 3.0}), "touch or overlap"),
    (lambda d: d["attachments"].append({"kind": "balcony"}), "attachments"),
])
def test_unsupported_or_unresolved_openings_are_errors(edit, message):
    with pytest.raises(BuildError, match=message):
        build(edited(edit), INPUTS)


def test_opening_reaching_the_roof_level_is_an_error():
    def edit(d):
        d["floors"][1] = {"level": "L1", "contour": d["floors"][0]["contour"], "openings": [
            {"wall": 0, "x_m": 2.0, "sill_m": 3.1, "w_m": 1.5, "h_m": 0.5, "kind": "window", "depth_m": 0.4}]}
    with pytest.raises(BuildError, match="below the roof level"):
        build(edited(edit), INPUTS)


def test_floors_must_cover_every_level():
    def edit(d):
        d["floors"] = [{"level": "L1", "contour": d["floors"][0]["contour"], "openings": []}]
    with pytest.raises(BuildError, match="cover every level"):
        build(edited(edit), INPUTS)


def test_cross_level_opening_in_a_typical_template_is_asked_not_copied():
    def edit(d):
        d["levels"] = [{"name": "L0", "elev_m": 0.0}, {"name": "L1", "elev_m": 3.3}, {"name": "L2", "elev_m": 6.6},
                       {"name": "roof", "elev_m": 9.9}]
        d["floors"] = [{"level": "L0", "contour": d["floors"][0]["contour"], "openings": [
                           {"wall": 0, "x_m": 2.0, "sill_m": 0.0, "w_m": 1.5, "h_m": 3.5, "kind": "window",
                            "level_from": "L0", "level_to": "L1"}]},
                       {"level": "L1", "typical_of": "L0", "repeat_to": "L2"}]
    with pytest.raises(BuildError, match="ask the user"):
        build(edited(edit), INPUTS)


@pytest.mark.parametrize("profile, seat", [("npm_min", 0.1), ("mid", 0.2)])
def test_plane_seat_follows_the_profile(profile, seat):
    # C24, user decision 2026-10-10: npm_min at half of the opening depth (0.2 m), mid at the full depth
    soup = from_dump(build(edited(lambda d: d.update({"profile": profile})), INPUTS))
    c = soup.corners()
    planes, reveals = c[soup.material_ids == PLANE], c[soup.material_ids == REVEAL]
    assert np.allclose(planes[:, :, 1], seat)                  # wall 0 at y = 0
    assert np.isclose(reveals[:, :, 1].max(), seat)            # no reveal behind the plane


def test_planes_face_out_and_reversed_planes_fail_the_checker():
    dump = build(spec(), INPUTS)
    soup = from_dump(dump)
    c = soup.corners()[soup.material_ids == PLANE]
    n = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
    assert np.all(n[:, 1] < 0)                                 # wall 0 faces -y
    body = dump["meshes"][0]
    body["triangles"] = [t[::-1] if m == PLANE else t for t, m in zip(body["triangles"], body["material_ids"])]
    report = checks.run(from_dump(dump), from_dump(box_dump()), spec(), TOL)
    assert "opening_planes" in report["failed"]


@pytest.mark.parametrize("contour", [
    [[0, 0], [10, 0], [10, 4], [6, 4], [6, 10], [0, 10]],                              # L
    [[0, 0], [10, 0], [10, 10], [7, 10], [7, 6], [3, 6], [3, 10], [0, 10]],            # U
])
def test_rectilinear_contours_build_without_t_junctions(contour):
    def edit(d):
        d["floors"][0]["contour"] = contour
    dump = build(edited(edit), INPUTS)
    soup = from_dump(dump)
    _, counts, _ = edge_uses(soup.triangles, weld(soup.vertices, 1e-4))
    assert counts.max() <= 2 and t_junctions(dump) == 0


def test_floor_records_in_any_order_build_the_same_model():
    # Codex review 2 of PR #50
    reversed_floors = edited(lambda d: d.update({"floors": d["floors"][::-1]}))
    assert build(reversed_floors, INPUTS) == build(spec(), INPUTS)

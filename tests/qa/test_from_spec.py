"""Engine from_spec (HARNESS_PLAN §9): spec -> model -> benchmark checkers, before the real B01 etalon.

The etalon here is the SYNTHETIC box of test_geometry_checks (not the user's etalon, issue #12);
the spec is tests/fixtures/spec-b01-v0.3.json. Build inputs the spec does not carry (parapet
thickness, material IDs) are given explicitly, as `jobs/<object>/materials.json` will.
"""
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from dt_ai.geometry.from_spec import BuildError, BuildInputs, build
from dt_ai.spec.model import Spec
from test_geometry_checks import FACADE, PLANE, REVEAL, ROOF, TOL, box_dump
from twinqa.geometry import checks
import run_benchmark
from twinqa.geometry.mesh import edge_uses, from_dump, weld
from twinqa.scene import find_blender

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
    ({"contour": [[0, 0], [10, 0], [12, 10], [0, 10]]}, "triangle is not built yet"),   # an x-extreme sharp corner
])
def test_what_this_step_cannot_build_is_an_error_not_a_guess(change, message):
    data = json.loads(json.dumps(FIXTURE))
    data["floors"][0].update(change)
    with pytest.raises(BuildError, match=message):
        build(Spec.model_validate(data), INPUTS)


# pattern floor-step: a contour per floor; at each step a ledge (up, roof ID) or a soffit (down, facade ID)


def stepped(lower, upper, openings_l1=()):
    def edit(d):
        d["floors"] = [{"level": "L0", "contour": lower, "openings": [d["floors"][0]["openings"][0]]},
                       {"level": "L1", "contour": upper, "openings": list(openings_l1)}]
    return edited(edit)


def horizontal(soup, z, mid, up):
    c = soup.corners()
    n = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
    sel = (soup.material_ids == mid) & np.all(np.abs(c[:, :, 2] - z) < 1e-9, axis=1) & ((n[:, 2] > 0) == up)
    return float(np.linalg.norm(n[sel], axis=1).sum() / 2)


def topology_ok(dump):
    soup = from_dump(dump)
    _, counts, _ = edge_uses(soup.triangles, weld(soup.vertices, 1e-4))
    loops = checks.check_mesh(soup, TOL, checks.load_ranges())["details"]["open_loops"]
    return counts.max() <= 2 and t_junctions(dump) == 0 and [lp["kind"] for lp in loops] == ["bottom"]


def test_ledge_where_the_floor_below_reaches_out():
    s = stepped([[0, 0], [10, 0], [10, 10], [0, 10]], [[4, 0], [10, 0], [10, 10], [4, 10]])
    dump = build(s, INPUTS)
    soup = from_dump(dump)
    assert horizontal(soup, 3.3, ROOF, True) == pytest.approx(40.0)      # ledge 4 x 10 m at L1
    assert horizontal(soup, 3.3, FACADE, False) == 0.0
    assert topology_ok(dump)


def test_soffit_where_the_floor_above_overhangs():
    # user 2026-10-10: the soffit under an overhang takes the facade ID
    s = stepped([[4, 0], [10, 0], [10, 10], [4, 10]], [[0, 0], [10, 0], [10, 10], [0, 10]])
    dump = build(s, INPUTS)
    soup = from_dump(dump)
    assert horizontal(soup, 3.3, FACADE, False) == pytest.approx(40.0)
    assert horizontal(soup, 3.3, ROOF, True) == 0.0
    assert topology_ok(dump)


def test_window_on_the_wall_above_the_ledge():
    window = {"wall": 3, "x_m": 4.0, "sill_m": 0.9, "w_m": 1.5, "h_m": 1.5, "kind": "window"}   # wall 3: (4,10)->(4,0)
    s = stepped([[0, 0], [10, 0], [10, 10], [0, 10]], [[4, 0], [10, 0], [10, 10], [4, 10]], [window])
    dump = build(s, INPUTS)
    soup = from_dump(dump)
    planes = soup.corners()[soup.material_ids == PLANE]
    assert np.allclose(planes[planes[:, :, 2].min(1) > 3.3][:, :, 0], 4.2)   # npm_min: full 0.2 m depth, inward +x
    assert topology_ok(dump)


def test_l_shaped_upper_floor_over_a_rectangle():
    s = stepped([[0, 0], [10, 0], [10, 10], [0, 10]], [[0, 0], [10, 0], [10, 4], [4, 4], [4, 10], [0, 10]])
    dump = build(s, INPUTS)
    assert horizontal(from_dump(dump), 3.3, ROOF, True) == pytest.approx(36.0)
    assert topology_ok(dump)


def test_step_model_passes_the_checks_against_itself():
    s = stepped([[0, 0], [10, 0], [10, 10], [0, 10]], [[4, 0], [10, 0], [10, 10], [4, 10]])
    soup = from_dump(build(s, INPUTS))
    report = checks.run(soup, soup, s, TOL)
    assert report["passed"], report["failed"] + report["not_measured"]


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


@pytest.mark.parametrize("profile, seat", [("npm_min", 0.2), ("mid", 0.1)])
def test_plane_seat_follows_the_profile(profile, seat):
    # C24 final, user decision 2026-10-10: npm_min at the full opening depth (0.2 m), mid at half of it
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



def test_checker_wants_the_plane_at_the_profiles_seat():
    # C24 final: npm_min plane at the full depth (0.2 m) +- opening_plane_offset_m; a plane at half fails
    half = box_dump(depth=0.1)
    report = checks.run(from_dump(half), from_dump(box_dump()), spec(), TOL)
    assert "opening_planes" in report["failed"]
    mid = edited(lambda d: d.update({"profile": "mid"}))
    assert by_id(checks.run(from_dump(half), from_dump(half), mid, TOL))["opening_planes"]["status"] == "pass"
# The chain from an etalon FBX to the checker report (tools/qa/run_benchmark.py), synthetic etalon


@pytest.mark.blender
@pytest.mark.skipif(find_blender() is None, reason="Blender not installed")
def test_chain_from_a_synthetic_etalon_fbx_to_a_green_report(tmp_path):
    src = tmp_path / "etalon-src.json"
    src.write_text(json.dumps({**box_dump(), "source": "etalon.fbx"}), encoding="utf-8")
    base = [find_blender(), "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1"]
    subprocess.run(base + ["--python", str(ROOT / "tools/export/export_mesh_blender.py"), "--", str(src),
                           str(tmp_path / "etalon.blend"), str(tmp_path / "etalon.fbx")], check=True, capture_output=True)
    bench = ROOT / "benchmark/bench-b01-box"
    argv = ["--etalon", str(tmp_path / "etalon.fbx"), "--object", str(bench / "object.json"),
            "--tolerances", str(bench / "tolerances.json"), "--output", str(tmp_path / "run")]
    assert run_benchmark.main(argv) == 0
    summary = json.loads((tmp_path / "run/summary.json").read_text(encoding="utf-8"))
    assert summary["steps"]["spec"] == {"status": "done", "questions": 0}
    assert summary["steps"]["etalon_self"]["passed"] and summary["steps"]["model_check"]["passed"]
    spec = json.loads((tmp_path / "run/spec.json").read_text(encoding="utf-8"))
    assert [lv["elev_m"] for lv in spec["levels"]] == pytest.approx([0.0, 3.3, 6.6], abs=1e-3)
    assert run_benchmark.main(argv) == 2                       # the run folder is never reused


def test_build_inputs_come_from_object_json_and_are_never_defaulted():
    obj = json.loads((ROOT / "benchmark/bench-b01-box/object.json").read_text(encoding="utf-8"))
    assert BuildInputs.from_object(obj) == INPUTS
    with pytest.raises(BuildError, match="no build block"):
        BuildInputs.from_object({"id": "x"})
    with pytest.raises(BuildError, match="build block"):
        BuildInputs.from_object({"id": "x", "build": {"parapet_thickness_m": 0.3, "ids": {"facade": 1}}})


# Codex review 1 of PR #51


def export(tmp_path, mesh, name="x"):
    src = tmp_path / f"{name}.json"
    src.write_text(json.dumps({"meshes": [mesh], "helpers": []}), encoding="utf-8")
    base = [find_blender(), "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1"]
    done = subprocess.run(base + ["--python", str(ROOT / "tools/export/export_mesh_blender.py"), "--", str(src),
                                  str(tmp_path / f"{name}.blend"), str(tmp_path / f"{name}.fbx")],
                          capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


CONCAVE = {"name": "q", "vertices": [[0, 0, 0], [2, 0, 0], [2, 2, 0], [1.5, 0.5, 0]]}


@pytest.mark.blender
@pytest.mark.skipif(find_blender() is None, reason="Blender not installed")
@pytest.mark.parametrize("mesh, ok, message", [
    ({**CONCAVE, "triangles": [[0, 1, 3], [1, 2, 3]], "material_ids": [1, 1], "polygon_sizes": [4]}, True, ""),
    ({**CONCAVE, "triangles": [[0, 1, 2], [0, 2, 3]], "material_ids": [1, 0], "polygon_sizes": [4]}, False, "id 0"),
    ({**CONCAVE, "triangles": [[0, 1, 2], [0, 2, 3]], "material_ids": [6]}, False, "material ids for 2 triangles"),
    ({**CONCAVE, "triangles": [[0, 1, 2], [0, 2, 3]], "material_ids": [1, 6], "polygon_sizes": [4]}, False, "has ids"),
])
def test_exporter_rebuilds_polygons_exactly_or_refuses(tmp_path, mesh, ok, message):
    code, log = export(tmp_path, mesh)
    assert (code == 0) == ok, log[-400:]
    assert message in log
    if ok:                                                     # a non-fan quad stays two triangles, none lost
        dump = tmp_path / "x-dump.json"
        subprocess.run([find_blender(), "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code",
                        "1", "--python", str(ROOT / "tools/source/measure_spec_blender.py"), "--",
                        str(tmp_path / "x.fbx"), str(dump)], check=True, capture_output=True)
        assert sum(len(m["triangles"]) for m in json.loads(dump.read_text(encoding="utf-8"))["meshes"]) == 2


@pytest.mark.parametrize("bad", ["object", "tolerances", "object-list"])
def test_runner_input_errors_stop_with_a_summary_and_exit_2(tmp_path, bad, monkeypatch):
    monkeypatch.setattr(run_benchmark, "blender_run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no run")))
    etalon = tmp_path / "etalon.fbx"
    etalon.write_bytes(b"x")
    bench = ROOT / "benchmark/bench-b01-box"
    broken = tmp_path / "broken.json"
    broken.write_text({"object": "{", "object-list": "[]"}.get(bad, json.dumps({"profile": "npm_min"})), encoding="utf-8")
    argv = ["--etalon", str(etalon), "--object", str(broken if bad.startswith("object") else bench / "object.json"),
            "--tolerances", str(broken if bad == "tolerances" else bench / "tolerances.json"),
            "--output", str(tmp_path / "run"), "--blender", "blender"]
    assert run_benchmark.main(argv) == 2
    assert "stopped" in json.loads((tmp_path / "run/summary.json").read_text(encoding="utf-8"))


def test_runner_refuses_a_step_that_left_no_file(tmp_path):
    with pytest.raises(RuntimeError, match="model.blend"):
        run_benchmark.produced(tmp_path / "model.blend")


def test_etalon_self_check_runs_even_when_the_engine_cannot_build(tmp_path, monkeypatch):
    # B02 (2026-10-10): the etalon is checked against itself before the engine is asked to build it
    def fake_blender(blender, script, *args, **kw):
        Path(args[-1]).write_text(json.dumps({**box_dump(), "source": "etalon.fbx"}), encoding="utf-8")
    monkeypatch.setattr(run_benchmark, "blender_run", fake_blender)
    monkeypatch.setattr(run_benchmark, "build", lambda *a, **k: (_ for _ in ()).throw(BuildError("not built yet")))
    etalon = tmp_path / "etalon.fbx"
    etalon.write_bytes(b"x")
    bench = ROOT / "benchmark/bench-b01-box"
    argv = ["--etalon", str(etalon), "--object", str(bench / "object.json"), "--tolerances", str(bench / "tolerances.json"),
            "--output", str(tmp_path / "run"), "--blender", "blender"]
    assert run_benchmark.main(argv) == 2
    summary = json.loads((tmp_path / "run/summary.json").read_text(encoding="utf-8"))
    assert summary["steps"]["etalon_self"]["passed"] and "not built yet" in summary["stopped"]
    assert (tmp_path / "run/etalon-self.json").is_file() and "model_check" not in summary["steps"]



@pytest.mark.parametrize("tol_change, code", [
    ({"triangles_max": 0}, 1),                                     # a failure
    ({"opening_plane_kinds": []}, 2),                              # not measured only
    ({"triangles_max": 0, "opening_plane_kinds": []}, 1),          # Codex review 1 of PR #53: a failure wins
])
def test_runner_exit_code_precedence(tmp_path, monkeypatch, tol_change, code):
    def fake_blender(blender, script, *args, **kw):
        if script == run_benchmark.EXPORT:
            for out in args[1:]:
                Path(out).write_bytes(b"x")
        else:
            src = box_dump() if "etalon" in Path(args[-1]).name else build(spec(), INPUTS)
            Path(args[-1]).write_text(json.dumps({**src, "source": "etalon.fbx"}), encoding="utf-8")
    monkeypatch.setattr(run_benchmark, "blender_run", fake_blender)
    bench = ROOT / "benchmark/bench-b01-box"
    tol = json.loads((bench / "tolerances.json").read_text(encoding="utf-8"))
    tol["geometry"].update(tol_change)
    (tmp_path / "t.json").write_text(json.dumps(tol), encoding="utf-8")
    etalon = tmp_path / "etalon.fbx"
    etalon.write_bytes(b"x")
    argv = ["--etalon", str(etalon), "--object", str(bench / "object.json"), "--tolerances", str(tmp_path / "t.json"),
            "--output", str(tmp_path / "run"), "--blender", "blender"]
    assert run_benchmark.main(argv) == code


# Codex review 1 of PR #55: unsupported floor-step inputs are errors, not broken geometry

SQ = [[0, 0], [10, 0], [10, 10], [0, 10]]


def test_openings_of_two_floors_overlapping_on_one_wall_line_are_an_error():
    o0 = {"wall": 0, "x_m": 2.0, "sill_m": 2.5, "w_m": 1.5, "h_m": 2.0, "kind": "window",
          "level_from": "L0", "level_to": "L1"}
    o1 = {"wall": 0, "x_m": 2.0, "sill_m": 0.2, "w_m": 1.5, "h_m": 1.0, "kind": "window"}
    def edit(d):
        d["floors"] = [{"level": "L0", "contour": SQ, "openings": [o0]},
                       {"level": "L1", "contour": SQ, "openings": [o1]}]
    with pytest.raises(BuildError, match="touch or overlap"):
        build(edited(edit), INPUTS)


def test_frame_across_a_level_onto_a_shorter_upper_wall_is_an_error():
    o0 = {"wall": 0, "x_m": 2.0, "sill_m": 2.8, "w_m": 1.5, "h_m": 1.2, "kind": "window",
          "level_from": "L0", "level_to": "L1"}
    def edit(d):
        d["floors"] = [{"level": "L0", "contour": SQ, "openings": [o0]},
                       {"level": "L1", "contour": [[3, 0], [10, 0], [10, 10], [3, 10]], "openings": []}]
    with pytest.raises(BuildError, match="no wall of floor 1 holds"):
        build(edited(edit), INPUTS)


@pytest.mark.parametrize("upper", [[[10, 3], [20, 3], [20, 7], [10, 7]], [[10, 10], [20, 10], [20, 20], [10, 20]]])
def test_floors_meeting_only_along_an_edge_or_at_a_corner_are_an_error(upper):
    def edit(d):
        d["floors"] = [{"level": "L0", "contour": SQ, "openings": []},
                       {"level": "L1", "contour": upper, "openings": []}]
    with pytest.raises(BuildError, match="do not meet over area only"):
        build(edited(edit), INPUTS)


def test_upper_floor_overhanging_past_one_wall_is_built():
    s = stepped(SQ, [[0, 0], [10, 0], [10, 10], [6, 10], [6, 14], [0, 14]])
    dump = build(s, INPUTS)
    assert horizontal(from_dump(dump), 3.3, FACADE, False) == pytest.approx(24.0) and topology_ok(dump)



def test_shifted_wall_origins_still_catch_overlapping_openings():
    # Codex review 2 of PR #55: lower wall 0 starts at x=3, upper at x=0; physical spans overlap
    o0 = {"wall": 0, "x_m": 1.0, "sill_m": 2.5, "w_m": 1.5, "h_m": 2.0, "kind": "window", "level_from": "L0", "level_to": "L1"}
    o1 = {"wall": 0, "x_m": 4.0, "sill_m": 0.2, "w_m": 1.5, "h_m": 1.0, "kind": "window"}
    def edit(d):
        d["floors"] = [{"level": "L0", "contour": [[3, 0], [10, 0], [10, 10], [3, 10]], "openings": [o0]},
                       {"level": "L1", "contour": SQ, "openings": [o1]}]
    with pytest.raises(BuildError, match="touch or overlap"):
        build(edited(edit), INPUTS)


def test_opposite_u_shapes_meeting_in_two_areas_are_built():
    # Codex review 2 of PR #55: the floors overlap in two separate rails (60 m2)
    lower = [[0, 0], [10, 0], [10, 10], [7, 10], [7, 3], [3, 3], [3, 10], [0, 10]]
    upper = [[0, 0], [3, 0], [3, 7], [7, 7], [7, 0], [10, 0], [10, 10], [0, 10]]
    dump = build(stepped(lower, upper), INPUTS)
    assert topology_ok(dump)



def test_overlap_areas_touching_at_a_corner_are_an_error():
    # Codex review 3 of PR #55: two 4 m2 overlaps touching at (2, 2) would leave a non-manifold vertex
    def edit(d):
        d["floors"] = [{"level": "L0", "contour": [[0, 0], [4, 0], [4, 2], [2, 2], [2, 4], [0, 4]], "openings": []},
                       {"level": "L1", "contour": [[2, 0], [4, 0], [4, 4], [0, 4], [0, 2], [2, 2]], "openings": []}]
    with pytest.raises(BuildError, match="do not meet over area only"):
        build(edited(edit), INPUTS)


# pattern non-90-corner: oblique walls; horizontal faces cut into trapezoids by vertical strips


def b02_spec():
    data = json.loads((ROOT / "benchmark/bench-b02-corner-niche/spec.json").read_text(encoding="utf-8"))
    return Spec.model_validate(data)


def test_b02_spec_builds_with_its_oblique_wall_niche_and_step():
    dump = build(b02_spec(), INPUTS)
    assert topology_ok(dump)
    soup = from_dump(dump)
    planes = soup.corners()[soup.material_ids == PLANE]
    oblique = planes[planes[:, :, 2].min(1) > 3.3]
    n = np.cross(oblique[:, 1] - oblique[:, 0], oblique[:, 2] - oblique[:, 0])
    assert np.allclose(n[:, :2] / np.linalg.norm(n[:, :2], axis=1)[:, None], [0.7071068, 0.7071068], atol=1e-6)


def test_b02_model_passes_the_checks_against_itself():
    s = b02_spec()
    soup = from_dump(build(s, INPUTS))
    report = checks.run(soup, soup, s, TOL)
    assert report["passed"], report["failed"] + report["not_measured"]


@pytest.mark.parametrize("contour", [
    [[0, 0], [10, 0], [10, 6], [7, 9], [0, 9]],                      # one 45° corner cut
    [[0, 0], [10, 0], [12, 6], [12, 9], [0, 9]],                     # a wall leaning out, obtuse corners
    [[0, 0], [10, 0], [10, 10], [5, 7], [0, 10]],                    # a V notch in the north wall
])
def test_oblique_contours_build_without_t_junctions(contour):
    def edit(d):
        d["floors"][0]["contour"] = contour
    dump = build(edited(edit), INPUTS)
    assert topology_ok(dump)



# Codex review 1 of PR #58: inputs that would weld into collapsed quads are errors


@pytest.mark.parametrize("contour, window", [
    ([[0, 0], [10, 0], [10, 6], [7.878679656440357, 8.121320343559642], [0, 8.121320343559642]], None),
    ([[0, 0], [10, 0], [10, 3], [10.000002, 6], [10.000002, 9], [0, 9]],
     {"wall": 2, "x_m": 0.5, "sill_m": 0.9, "w_m": 1.0, "h_m": 1.5, "kind": "window"}),
    ([[0, 0], [10, 0], [10, 0.00001], [0, 10]],
     {"wall": 3, "x_m": 1.0, "sill_m": 0.9, "w_m": 0.2, "h_m": 1.5, "kind": "window"}),
])
def test_near_degenerate_inputs_build_clean_or_stop(contour, window):
    def edit(d):
        d["floors"][0]["contour"] = contour
        d["floors"][0]["openings"] = [window] if window else []
        d["roof"] = {"parapet_h_m": 0.0}
    try:
        dump = build(edited(edit), INPUTS)
    except BuildError:
        return
    soup = from_dump(dump)
    c = soup.corners()
    area = np.linalg.norm(np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0]), axis=1) / 2
    assert area.min() > 1e-9 and topology_ok(dump)
    if window:
        assert PLANE in set(soup.material_ids.tolist())     # never a window silently turned into facade



@pytest.mark.parametrize("contour, wall, x_m", [
    ([[0, 0], [10, 0], [10, 10], [0, 10]], 0, 0.0001),               # exactly 0.1 mm from the start (review 2 of #58)
    ([[0, 0], [10, 0], [10, 10], [0, 10]], 0, 8.9999),               # exactly 0.1 mm from the end
])
def test_windows_at_the_0_1_mm_limit_are_built(contour, wall, x_m):
    def edit(d):
        d["floors"][0]["contour"] = contour
        d["floors"][0]["openings"] = [{"wall": wall, "x_m": x_m, "sill_m": 0.9, "w_m": 1.0, "h_m": 1.5, "kind": "window"}]
        d["roof"] = {"parapet_h_m": 0.0}
    dump = build(edited(edit), INPUTS)
    assert topology_ok(dump) and PLANE in set(from_dump(dump).material_ids.tolist())


def test_window_closer_than_0_1_mm_to_a_wall_end_is_an_error():
    def edit(d):
        d["floors"][0]["openings"] = [{"wall": 0, "x_m": 0.00005, "sill_m": 0.9, "w_m": 1.0, "h_m": 1.5, "kind": "window"}]
    with pytest.raises(BuildError, match="closer than 0.1 mm to the wall end"):
        build(edited(edit), INPUTS)



def test_window_close_to_a_steep_oblique_corner_is_a_clear_error():
    # Codex review 2 of PR #58: 1 mm along a steep oblique wall is 0.03 mm in x; the strips would put
    # vertices closer than the checkers' 0.1 mm weld, so this is a BuildError, not merged geometry
    def edit(d):
        d["floors"][0]["contour"] = [[0, 0], [10, 0], [10, 6], [9.9, 9], [0, 9]]
        d["floors"][0]["openings"] = [{"wall": 2, "x_m": 0.001, "sill_m": 0.9, "w_m": 1.0, "h_m": 1.5, "kind": "window"}]
    with pytest.raises(BuildError, match="strip lines closer than 0.1 mm"):
        build(edited(edit), INPUTS)



def test_inputs_at_the_limit_that_would_break_under_the_weld_are_errors():
    # Codex review 3 of PR #58: both built "valid" raw quads that collapse or leave a hole at 0.1 mm
    def window_case(d):
        d["floors"][0]["contour"] = [[.00005, 0], [10.00005, 0], [10.00005, 6], [9.00005, 7], [.00005, 7]]
        d["floors"][0]["openings"] = [{"wall": 2, "x_m": .0001414213562373095, "sill_m": 0.9, "w_m": 0.5,
                                       "h_m": 1.5, "kind": "window"}]
        d["roof"] = {"parapet_h_m": 0.0}

    def step_case(d):
        d["floors"] = [{"level": "L0", "contour": [[0, 0], [10, 0], [10, 6], [9.9999, 9], [0, 9]], "openings": []},
                       {"level": "L1", "contour": [[0, 0], [10, 0], [10, 5.9999], [9.9999, 8.9999], [0, 8.9999]],
                        "openings": []}]
        d["roof"] = {"parapet_h_m": 0.0}
    for edit in (window_case, step_case):
        with pytest.raises(BuildError):
            build(edited(edit), INPUTS)


# pattern terrace (spec v0.4, user decisions 2026-10-10): a parapet along a ledge's outer edges


def terraced(spec_data_edit, h=0.6):
    def edit(d):
        spec_data_edit(d)
        d["spec_version"] = "0.4"
        d["terraces"] = [{"level": "L1", "parapet_h_m": h}]
    return edited(edit)


def west_ledge(d):
    d["floors"] = [{"level": "L0", "contour": SQ, "openings": [d["floors"][0]["openings"][0]]},
                   {"level": "L1", "contour": [[4, 0], [10, 0], [10, 10], [4, 10]], "openings": []}]


def test_terrace_parapet_on_a_ledge():
    s = terraced(west_ledge)
    dump = build(s, INPUTS)
    soup = from_dump(dump)
    assert topology_ok(dump)
    assert horizontal(soup, 3.3, ROOF, True) == pytest.approx(40 - 5.22)        # walkable part
    assert horizontal(soup, 3.9, ROOF, True) == pytest.approx(5.22)             # cap: 0.3 x 10 + 2 x 0.3 x 3.7
    c = soup.corners()
    hidden = (soup.material_ids == FACADE) & np.all(np.abs(c[:, :, 0] - 4) < 1e-9, axis=1) \
        & (c[:, :, 2].mean(1) > 3.3) & (c[:, :, 2].mean(1) < 3.9) \
        & ((c[:, :, 1].mean(1) < 0.3) | (c[:, :, 1].mean(1) > 9.7))
    assert not hidden.any()                                                      # upper wall behind the parapet ends
    report = checks.run(soup, soup, s, TOL)
    assert report["passed"], report["failed"] + report["not_measured"]


def test_b02_with_a_terrace_parapet_builds_and_closes():
    data = json.loads((ROOT / "benchmark/bench-b02-corner-niche/spec.json").read_text(encoding="utf-8"))
    data.update({"spec_version": "0.4", "terraces": [{"level": "L1", "parapet_h_m": 0.6}]})
    dump = build(Spec.model_validate(data), INPUTS)
    soup = from_dump(dump)
    assert topology_ok(dump)
    ledge = 6 * 9 - 3.5 * 0.6
    assert horizontal(soup, 3.3, ROOF, True) + horizontal(soup, 3.9, ROOF, True) == pytest.approx(ledge)


def test_terrace_errors():
    with pytest.raises(BuildError, match="does not reach out"):
        build(terraced(lambda d: None), INPUTS)                                  # no step under the terrace
    with pytest.raises(BuildError, match="parapet_thickness_m"):
        build(terraced(west_ledge), BuildInputs(**{**INPUTS.__dict__, "parapet_thickness_m": 0.0}))
    data = json.loads(json.dumps(FIXTURE))
    data["terraces"] = [{"level": "L1", "parapet_h_m": 0.6}]
    with pytest.raises(ValueError, match="spec_version 0.4"):
        Spec.model_validate(data)
    data["spec_version"] = "0.4"
    data["terraces"] = [{"level": "roof", "parapet_h_m": 0.6}]
    with pytest.raises(ValueError, match="between the first and the roof"):
        Spec.model_validate(data)


# Codex review 1 of PR #59: a ledge in several parts (the floor above splits it) carries a parapet on each


def test_terrace_on_a_ledge_in_two_parts():
    def split(d):
        d["floors"] = [{"level": "L0", "contour": SQ, "openings": []},
                       {"level": "L1", "contour": [[2, 0], [8, 0], [8, 10], [2, 10]], "openings": []}]
    dump = build(terraced(split), INPUTS)
    soup = from_dump(dump)
    assert topology_ok(dump)
    assert horizontal(soup, 3.9, ROOF, True) == pytest.approx(2 * (0.3 * 10 + 2 * 0.3 * 1.7))   # two caps
    assert horizontal(soup, 3.3, ROOF, True) == pytest.approx(2 * 1.7 * 9.4)                    # two walkable parts


# Terrace PR B: the extractor reads the terrace parapet back (engine model -> spec, round trip)

SYNTH_OBJECT = {"id": "bench-synth-terrace", "frame": {"to_object": np.eye(4).tolist()}}


def split_ledge(d):
    d["floors"] = [{"level": "L0", "contour": SQ, "openings": []},
                   {"level": "L1", "contour": [[2, 0], [8, 0], [8, 10], [2, 10]], "openings": []}]


@pytest.mark.parametrize("edit, h", [(west_ledge, 0.3), (west_ledge, 0.6), (west_ledge, 1.2), (split_ledge, 0.6)])
def test_extractor_reads_the_terrace_parapet_back(edit, h):
    from dt_ai.spec import extract_spec
    s = terraced(edit, h)
    spec, report = extract_spec(build(s, INPUTS), SYNTH_OBJECT)
    assert spec.spec_version == "0.4" and [t.model_dump() for t in spec.terraces] == [{"level": "L1", "parapet_h_m": h}]
    assert [f.contour for f in spec.expanded_floors()] == [f.contour for f in s.expanded_floors()]
    assert report["questions"] == []
    t = report["floors"]["L1"]["terrace"]
    assert t["walkable_m2"] + t["cap_m2"] == pytest.approx(t["ledge_m2"])


def test_extractor_reads_no_terrace_on_a_plain_step():
    from dt_ai.spec import extract_spec
    spec, report = extract_spec(build(edited(west_ledge), INPUTS), SYNTH_OBJECT)
    assert spec.terraces == [] and spec.spec_version == "0.3" and "terrace" not in report["floors"]["L1"]


def test_b02_terrace_spec_round_trip():
    from dt_ai.spec import extract_spec
    data = json.loads((ROOT / "benchmark/bench-b02t-terrace/spec.json").read_text(encoding="utf-8"))
    s = Spec.model_validate(data)
    spec, report = extract_spec(build(s, INPUTS), {**SYNTH_OBJECT, "id": s.id})
    keep = lambda x: {k: v for k, v in x.model_dump().items() if k != "frame"}   # noqa: E731
    assert keep(spec) == keep(s) and report["questions"] == []


def _west_terrace_dump():
    d = build(terraced(west_ledge), INPUTS)
    m = d["meshes"][0]
    m.pop("polygons", None)
    m.pop("polygon_sizes", None)
    return d, m, np.asarray(m["vertices"], float)


def _drop(m, v, where):
    keep = [i for i, t in enumerate(m["triangles"]) if not where(v[t])]
    m["triangles"] = [m["triangles"][i] for i in keep]
    m["material_ids"] = [m["material_ids"][i] for i in keep]


def test_extractor_wants_the_whole_parapet_inner_face_not_its_area():
    # Codex review 2 of PR #61: the west inner face is missing; copies of the south one make up its area
    from dt_ai.spec import SpecError, extract_spec
    d, m, v = _west_terrace_dump()
    west = lambda t: np.all(np.abs(t[:, 0] - 0.3) < 1e-6) and t[:, 2].max() <= 3.9 + 1e-6   # noqa: E731
    _drop(m, v, west)                                       # 9.4 x 0.6 = 5.64 m2 gone
    for xa, xb in ((0.3, 4.0), (0.3, 4.0), (0.3, 2.3)):    # 2.22 + 2.22 + 1.2 = 5.64 m2 more on the south face
        n = len(m["vertices"])
        m["vertices"] += [[xa, 0.3, 3.3], [xb, 0.3, 3.3], [xb, 0.3, 3.9], [xa, 0.3, 3.9]]
        m["triangles"] += [[n, n + 2, n + 1], [n, n + 3, n + 2]]
        m["material_ids"] += [ROOF, ROOF]
    with pytest.raises(SpecError, match="no section shape is both at the two storey ends"):
        extract_spec(d, SYNTH_OBJECT)


def test_extractor_asks_about_anything_else_standing_on_a_terrace():
    # Codex review 2 of PR #61: a block on the walkable part is no parapet and never disappears silently
    from dt_ai.spec import extract_spec
    d, m, v = _west_terrace_dump()
    n = len(m["vertices"])
    x0, y0, x1, y1, z0, z1 = 0.3, 0.3, 0.8, 0.8, 3.3, 4.3          # welded at the walkable corner
    m["vertices"] += [[x, y, z] for z in (z0, z1) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    quads = [(4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for a, b, c, e in quads:
        m["triangles"] += [[n + a, n + b, n + c], [n + a, n + c, n + e]]
        m["material_ids"] += [FACADE, FACADE]
    spec, report = extract_spec(d, SYNTH_OBJECT)
    assert [t.level for t in spec.terraces] == ["L1"]
    assert [(q["kind"], q["levels"]) for q in report["questions"]] == [("ledge-structure", ["L1"])]


def test_inner_face_cover_does_not_depend_on_extra_points_on_its_line():
    # Codex review 3 of PR #61: a collinear point on the inner line (a walkable part split in two) must not
    # drop the faces that cross it
    from shapely.geometry import LineString
    from dt_ai.spec.mesh import _wall_cover
    v = np.array([[0.3, 0.3, 3.3], [0.3, 9.7, 3.3], [0.3, 9.7, 3.9], [0.3, 0.3, 3.9]])
    tris = np.array([[0, 1, 2], [0, 2, 3]])
    whole = _wall_cover(v, tris, LineString([(0.3, 0.3), (0.3, 9.7)]), 3.3, 3.9)
    split = _wall_cover(v, tris, LineString([(0.3, 0.3), (0.3, 5.0), (0.3, 9.7)]), 3.3, 3.9)
    assert whole == pytest.approx(9.4 * 0.6) and split == pytest.approx(whole)


def test_a_fin_across_the_parapet_inner_face_is_a_question():
    # Codex review 3 of PR #61: a face standing across the inner line is not the parapet
    from dt_ai.spec import extract_spec
    d, m, v = _west_terrace_dump()
    west = lambda t: np.all(np.abs(t[:, 0] - 0.3) < 1e-6) and t[:, 1].min() >= 0.3 - 1e-6         and t[:, 1].max() <= 9.7 + 1e-6 and t[:, 2].min() >= 3.3 - 1e-6 and t[:, 2].max() <= 3.9 + 1e-6  # noqa: E731
    _drop(m, v, west)                                       # the west inner face, rebuilt in two at y = 5
    n = len(m["vertices"])
    m["vertices"] += [[0.3, y, z] for y in (0.3, 5.0, 9.7) for z in (3.3, 3.9)]
    for a in (0, 2):
        m["triangles"] += [[n + a, n + a + 1, n + a + 3], [n + a, n + a + 3, n + a + 2]]
        m["material_ids"] += [ROOF, ROOF]
    m["vertices"] += [[0.1, 5.0, 3.6], [0.5, 5.0, 3.6]]   # a fin welded at (0.3, 5, 3.9), across the face
    m["triangles"] += [[n + 3, n + 6, n + 7]]
    m["material_ids"] += [ROOF]
    spec, report = extract_spec(d, SYNTH_OBJECT)
    assert [(q["kind"], q["levels"]) for q in report["questions"]] == [("ledge-structure", ["L1"])]

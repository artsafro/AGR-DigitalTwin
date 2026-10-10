"""Benchmark geometry checks (twinqa.geometry, HARNESS_PLAN §5) on SYNTHETIC B01-like boxes.

The box below is synthetic test data, not the user's etalon (issue #12): 10 x 10 m, levels
0 / 3.3 / 6.6, parapet 0.6 m, one 1.5 x 1.5 m window per storey on wall 0 with reveals and an
opening plane at 0.2 m — the numbers of tests/fixtures/spec-b01-v0.3.json (opening depth 0.2 m,
npm_min plane at the full depth: C24 final, user decision 2026-10-10). The synthetic mesh is closed and welded:
global height cuts on every wall, per-wall cuts at the opening edges, fans on the bottom and roof.
"""
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

import check_geometry
from dt_ai.spec.model import Spec
from twinqa.geometry import checks
from twinqa.geometry.mesh import from_dump

ROOT = Path(__file__).resolve().parents[2]
SPEC = Spec.model_validate(json.loads((ROOT / "tests/fixtures/spec-b01-v0.3.json").read_text(encoding="utf-8")))
TOLERANCES = ROOT / "benchmark/bench-b01-box/tolerances.json"
TOL = json.loads(TOLERANCES.read_text(encoding="utf-8"))["geometry"]
WINDOWS = [(0, 2.0, 3.5, 0.9, 2.4), (0, 2.0, 3.5, 4.2, 5.7)]
FACADE, REVEAL, PLANE, ROOF = 1, 6, 11, 21


def box_dump(size=10.0, roof=6.6, top=7.2, parapet_t=0.3, windows=WINDOWS, depth=0.2, planes=True,
             levels=(("L0", 0.0), ("L1", 3.3), ("roof", 6.6)), polygon_sizes=True, extra=(), roof_inset=0.0):
    """Mesh dump of a closed box with recessed windows and a parapet (synthetic)."""
    faces = []  # (points, material id)
    corners = [np.array(p, float) for p in ((0, 0), (size, 0), (size, size), (0, size))]
    zcuts = sorted({0.0, top, *(w[3] for w in windows), *(w[4] for w in windows)})
    ring_out, ring_in = [], []
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        u = (b - a) / size
        inward = np.array([-u[1], u[0]])
        cuts = sorted({0.0, size, *(w[1] for w in windows if w[0] == i), *(w[2] for w in windows if w[0] == i)})
        p = lambda s, z: [*(a + u * s), z]  # noqa: E731
        holes = {(w[1], w[2], w[3], w[4]) for w in windows if w[0] == i}
        for s0, s1 in zip(cuts, cuts[1:]):
            for z0, z1 in zip(zcuts, zcuts[1:]):
                if (s0, s1, z0, z1) not in holes:
                    faces.append(([p(s0, z0), p(s1, z0), p(s1, z1), p(s0, z1)], FACADE))
                    continue
                q = lambda s, z: [*(a + u * s + inward * depth), z]  # noqa: E731
                ring = [(s0, z0), (s1, z0), (s1, z1), (s0, z1)]
                for (sa, za), (sb, zb) in zip(ring, ring[1:] + ring[:1]):
                    faces.append(([p(sa, za), p(sb, zb), q(sb, zb), q(sa, za)], REVEAL))
                if planes:
                    faces.append(([q(s, z) for s, z in ring], PLANE))
        inner = lambda s: a + u * parapet_t + inward * parapet_t + u * min(max(s - parapet_t, 0.0), size - 2 * parapet_t)  # noqa: E731
        for s0, s1 in zip(cuts, cuts[1:]):
            faces.append(([p(s0, top), p(s1, top), [*inner(s1), top], [*inner(s0), top]], ROOF))
            faces.append(([[*inner(s0), roof], [*inner(s1), roof], [*inner(s1), top], [*inner(s0), top]], ROOF))
        ring_out += [p(s, 0.0) for s in cuts[:-1]]
        ring_in += [[*inner(s), roof] for s in cuts[:-1]]
    if roof_inset:                       # an inset roof plane (pattern roof-inset-plane): a loose element
        ring_in = [[x, y, z + roof_inset] for x, y, z in ring_in]
    for ring, z, mid in ((ring_out, 0.0, FACADE), (ring_in, roof + roof_inset, ROOF)):
        c = [size / 2, size / 2, z]
        faces += [([c, ring[k], ring[(k + 1) % len(ring)]], mid) for k in range(len(ring))]
    faces += list(extra)
    meshes = [_mesh("body", [f for f in faces if f[1] != PLANE or not planes]),
              _mesh("planes", [f for f in faces if f[1] == PLANE])]
    if not polygon_sizes:
        for m in meshes:
            del m["polygon_sizes"]
    return {"source": "synthetic", "units": "m", "meshes": [m for m in meshes if m["triangles"]],
            "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]} for n, z in levels]}


def _mesh(name, faces):
    index, verts, tris, mids, sizes = {}, [], [], [], []
    for pts, mid in faces:
        ids = []
        for pt in pts:
            key = tuple(round(c, 6) for c in pt)
            if key not in index:
                index[key] = len(verts)
                verts.append(list(key))
            ids.append(index[key])
        tris += [[ids[0], ids[k], ids[k + 1]] for k in range(1, len(ids) - 1)]
        mids += [mid] * (len(ids) - 2)
        sizes.append(len(ids))
    return {"name": name, "vertices": verts, "triangles": tris, "material_ids": mids, "polygon_sizes": sizes}


def run(model_dump, etalon_dump=None, tol=TOL):
    etalon = from_dump(etalon_dump or box_dump())
    return checks.run(from_dump(model_dump), etalon, SPEC, tol)


def by_id(report):
    return {c["id"]: c for c in report["checks"]}


def test_synthetic_box_is_closed_and_passes_against_itself():
    report = run(box_dump())
    assert report["passed"], report["failed"] + report["not_measured"]
    mesh = by_id(report)["mesh"]["details"]
    assert mesh["boundary_edges"] == 0 and mesh["non_manifold_edges"] == 0 and mesh["overlap_pairs"] == 0
    openings = by_id(report)["opening_planes"]["details"]["openings"]
    assert [(o["level"], o["cover"]) for o in openings] == [("L0", 1.0), ("L1", 1.0)]


def test_tolerances_follow_the_plan_and_the_standard():
    npm = yaml.safe_load((ROOT / "standards/NPM_STANDARD.yaml").read_text(encoding="utf-8"))
    budget = next(v for k, v in _walk(npm) if k == "oks_triangles_per_fbx_max")
    assert TOL["triangles_max"] <= budget
    assert (TOL["bbox_m"], TOL["level_elev_m"], TOL["floor_area_rel"], TOL["silhouette_iou_min"]) == (0.05, 0.03, 0.02, 0.97)


def _walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, v
            yield from _walk(v)


def test_missing_opening_plane_fails_cover_and_leaves_a_hole():
    report = run(box_dump(planes=False, windows=WINDOWS))
    # the open window also stops the model section closing where the etalon's closes
    # an open window is no allowed open loop (pattern roof-inset-plane, user rule 2026-10-10)
    assert report["failed"] == ["floor_areas", "mesh", "opening_planes"]
    assert by_id(report)["opening_planes"]["value"] == 0.0
    loops = by_id(report)["mesh"]["details"]["open_loops"]
    assert [(lp["kind"], lp["edges"], lp["allowed"]) for lp in loops] == [("other", 4, False), ("other", 4, False)]


def test_window_on_another_wall_fails():
    moved = [(1, 2.0, 3.5, 0.9, 2.4), (0, 2.0, 3.5, 4.2, 5.7)]
    report = run(box_dump(windows=moved))
    assert report["failed"] == ["opening_planes"]
    rows = by_id(report)["opening_planes"]["details"]["openings"]
    assert [r["cover"] for r in rows] == [0.0, 1.0]


def test_low_parapet_fails_bbox_and_silhouette_not_levels():
    report = run(box_dump(top=6.9))
    assert {"bbox", "silhouettes"} <= set(report["failed"]) and "levels" not in report["failed"]
    assert by_id(report)["silhouettes"]["details"]["iou"]["x"] == pytest.approx(6.9 / 7.2, abs=1e-3)


def test_wider_box_fails_floor_area():
    report = run(box_dump(size=10.5))
    area = by_id(report)["floor_areas"]
    assert area["status"] == "fail" and area["value"] == pytest.approx(0.1, abs=0.01)


def test_level_helper_moved_or_missing_fails():
    moved = run(box_dump(levels=(("L0", 0.0), ("L1", 3.35), ("roof", 6.6))))
    assert by_id(moved)["levels"]["value"] == pytest.approx(0.05)
    missing = run(box_dump(levels=(("L0", 0.0), ("roof", 6.6))))
    assert by_id(missing)["levels"]["details"]["missing_in_model"] == ["L1"]
    assert "levels" in missing["failed"]


def test_dump_without_polygon_sizes_is_an_open_gate_not_a_pass():
    report = run(box_dump(polygon_sizes=False))
    assert not report["passed"] and report["not_measured"] == ["mesh"] and report["failed"] == []


def test_ngon_fails():
    dump = box_dump()
    sizes = dump["meshes"][0]["polygon_sizes"]
    assert sizes[:2] == [4, 4]
    sizes[:2] = [6]  # two quads read as one hexagon: same 4 triangles
    assert by_id(run(dump))["mesh"]["details"]["ngons"] == 1


def test_material_id_out_of_range_and_unassigned_fail():
    dump = box_dump()
    dump["meshes"][0]["material_ids"][0] = 99
    dump["meshes"][0]["material_ids"][1] = 0
    ids = by_id(run(dump))["material_ids"]
    assert ids["status"] == "fail" and ids["value"] == {"out_of_range": [99], "unassigned_triangles": 1}


def test_face_two_mm_in_front_of_a_wall_is_an_overlap():
    patch = ([[6, -0.002, 1], [8, -0.002, 1], [8, -0.002, 2], [6, -0.002, 2]], FACADE)
    mesh = by_id(run(box_dump(extra=[patch])))["mesh"]
    assert mesh["status"] == "fail" and mesh["details"]["overlap_pairs"] >= 1


def test_standalone_opening_plane_is_open_only_where_a_benchmark_allows_it():
    plane = ([[20, 0, 1], [21, 0, 1], [21, 0, 2], [20, 0, 2]], PLANE)
    assert by_id(run(box_dump(extra=[plane]), box_dump()))["mesh"]["status"] == "fail"     # B01: none allowed
    report = run(box_dump(extra=[plane]), box_dump(), tol={**TOL, "open_part_groups": ["opening"]})
    assert by_id(report)["mesh"]["status"] == "pass" and by_id(report)["mesh"]["details"]["open_parts_allowed"] == 1


def test_triangle_budget_from_tolerances():
    report = run(box_dump(), tol={**TOL, "triangles_max": 100})
    assert by_id(report)["triangle_budget"]["status"] == "fail"


def test_tool_writes_a_new_report_and_refuses_to_overwrite(tmp_path):
    model, etalon, out = tmp_path / "model.json", tmp_path / "etalon.json", tmp_path / "report.json"
    model.write_text(json.dumps(box_dump()), encoding="utf-8")
    etalon.write_text(json.dumps(box_dump()), encoding="utf-8")
    argv = [str(model), str(etalon), "--spec", str(ROOT / "tests/fixtures/spec-b01-v0.3.json"),
            "--tolerances", str(TOLERANCES), "--output", str(out)]
    assert check_geometry.main(argv) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["passed"] is True
    assert check_geometry.main(argv) == 2


# Codex review 1 of PR #47


def test_section_closed_on_one_side_only_fails():
    dump = box_dump()
    body = dump["meshes"][0]
    v = np.asarray(body["vertices"])
    keep = [k for k, t in enumerate(body["triangles"]) if not (np.all(v[t][:, 1] == 0) and np.all(v[t][:, 2] <= 0.9))]
    body["triangles"] = [body["triangles"][k] for k in keep]
    body["material_ids"] = [body["material_ids"][k] for k in keep]
    del body["polygon_sizes"]
    area = by_id(run(dump))["floor_areas"]
    assert area["status"] == "fail" and ["L0", 0.33] in area["details"]["closed_on_one_side"]


def test_clockwise_contour_takes_the_normal_from_its_winding():
    data = json.loads((ROOT / "tests/fixtures/spec-b01-v0.3.json").read_text(encoding="utf-8"))
    data["floors"][0]["contour"] = [[0, 0], [0, 10], [10, 10], [10, 0]]
    data["floors"][0]["openings"][0].update({"wall": 3, "x_m": 6.5})
    cw = Spec.model_validate(data)
    report = checks.run(from_dump(box_dump()), from_dump(box_dump()), cw, TOL)
    assert [o["cover"] for o in by_id(report)["opening_planes"]["details"]["openings"]] == [1.0, 1.0]


def test_collision_hulls_are_left_out():
    dump = box_dump()
    dump["meshes"].append({**_mesh("UCX_SM_Box_Main_001", [([[0, 0, 0], [10, 0, 0], [10, 0, 7.2], [0, 0, 7.2]], 0)])})
    report = run(dump)
    assert report["passed"] and by_id(report)["mesh"]["details"]["collision_meshes_left_out"] == 1


def test_polygon_sizes_that_do_not_match_the_triangles_are_not_measured():
    dump = box_dump()
    for m in dump["meshes"]:
        m["polygon_sizes"] = []
    report = run(dump)
    assert not report["passed"] and report["not_measured"] == ["mesh"]


def test_section_open_in_both_is_listed_not_judged():
    # Codex review 2 of PR #47: both dumps miss the same strip; they agree, the height is reported
    def strip(dump):
        body = dump["meshes"][0]
        v = np.asarray(body["vertices"])
        keep = [k for k, t in enumerate(body["triangles"]) if not (np.all(v[t][:, 1] == 0) and np.all(v[t][:, 2] <= 0.9))]
        body["triangles"] = [body["triangles"][k] for k in keep]
        body["material_ids"] = [body["material_ids"][k] for k in keep]
        del body["polygon_sizes"]
        return dump
    area = by_id(run(strip(box_dump()), strip(box_dump())))["floor_areas"]
    assert area["status"] == "pass" and ["L0", 0.33] in area["details"]["open_on_both_sides"]



# pattern roof-inset-plane (user rule 2026-10-10): open edges = bottom ring + the inset roof joint


def loops_of(report):
    return sorted(((lp["kind"], lp["level"] or "", lp["allowed"]) for lp in by_id(report)["mesh"]["details"]["open_loops"]))


def test_inset_roof_plane_joint_is_allowed():
    report = run(box_dump(roof_inset=0.005), box_dump(roof_inset=0.005))
    assert by_id(report)["mesh"]["status"] == "pass"
    assert loops_of(report) == [("roof-foot", "roof", True), ("roof-plane", "roof", True)]


def test_roof_plane_lifted_too_far_is_not_an_inset():
    report = run(box_dump(roof_inset=0.05), box_dump(roof_inset=0.05))
    assert by_id(report)["mesh"]["status"] == "fail" and ("other", "", False) in loops_of(report)


def test_two_inset_planes_on_one_roof_are_not_allowed():
    patch = ([[3, 3, 6.605], [4, 3, 6.605], [4, 4, 6.605], [3, 4, 6.605]], ROOF)
    report = run(box_dump(roof_inset=0.005, extra=[patch]), box_dump(roof_inset=0.005))
    assert by_id(report)["mesh"]["status"] == "fail"
    assert [k for k, _, ok in loops_of(report) if not ok] == ["other", "other", "other"]


def test_open_bottom_ring_is_allowed():
    dump = box_dump()
    body = dump["meshes"][0]
    v = np.asarray(body["vertices"])
    keep = [k for k, t in enumerate(body["triangles"]) if not np.all(v[t][:, 2] == 0)]
    body["triangles"] = [body["triangles"][k] for k in keep]
    body["material_ids"] = [body["material_ids"][k] for k in keep]
    del body["polygon_sizes"]
    report = run(dump)
    assert loops_of(report) == [("bottom", "", True)]

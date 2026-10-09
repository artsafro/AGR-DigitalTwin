"""Benchmark geometry checks (twinqa.geometry, HARNESS_PLAN §5) on SYNTHETIC B01-like boxes.

The box below is synthetic test data, not the user's etalon (issue #12): 10 x 10 m, levels
0 / 3.3 / 6.6, parapet 0.6 m, one 1.5 x 1.5 m window per storey on wall 0, recessed 0.2 m with an
opening plane — the numbers of tests/fixtures/spec-b01-v0.3.json. The synthetic mesh is closed and welded:
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
             levels=(("L0", 0.0), ("L1", 3.3), ("roof", 6.6)), polygon_sizes=True, extra=()):
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
    for ring, z, mid in ((ring_out, 0.0, FACADE), (ring_in, roof, ROOF)):
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
    assert report["failed"] == ["opening_planes"] and by_id(report)["opening_planes"]["value"] == 0.0
    assert by_id(report)["mesh"]["details"]["boundary_edges"] == 8  # reported, not judged (null)
    closed = run(box_dump(planes=False, windows=WINDOWS), tol={**TOL, "boundary_edges_max": 0})
    assert {"opening_planes", "mesh"} <= set(closed["failed"])


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
    dump["meshes"][0]["polygon_sizes"][0] = 6
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


def test_standalone_opening_plane_may_stay_open():
    plane = ([[20, 0, 1], [21, 0, 1], [21, 0, 2], [20, 0, 2]], PLANE)
    report = run(box_dump(extra=[plane]), box_dump(), tol={**TOL, "boundary_edges_max": 0})
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

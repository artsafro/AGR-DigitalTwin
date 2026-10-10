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
             levels=(("L0", 0.0), ("L1", 3.3), ("roof", 6.6)), polygon_sizes=True, extra=(), roof_inset=0.005,
             roof_embed=0.02):
    """Mesh dump of a box with recessed windows, a parapet and, by default, an inset roof plate 5 mm above
    the roof level (every slab is inset, user rule 2026-10-10); roof_inset=0 gives a solid roof (synthetic)."""
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
    if roof_inset:                       # an inset roof plane (pattern roof-inset-plane): a loose element,
        half = size / 2 - parapet_t      # embedded roof_embed into the parapet faces all round
        k = (half + roof_embed) / half
        ring_in = [[size / 2 + (x - size / 2) * k, size / 2 + (y - size / 2) * k, z + roof_inset] for x, y, z in ring_in]
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


def run(model_dump, etalon_dump=None, tol=TOL, spec=None):
    etalon = from_dump(etalon_dump or box_dump())
    return checks.run(from_dump(model_dump), etalon, spec or SPEC, tol)


def plates(gap=0.005, overlap=0.02):
    """The synthetic spec with the building's inset plate parameters (user 2026-10-10)."""
    return Spec.model_validate({**SPEC.model_dump(), "plate_gap_m": gap, "plate_overlap_m": overlap})


def by_id(report):
    return {c["id"]: c for c in report["checks"]}


def test_synthetic_box_is_closed_but_for_the_roof_inset_and_passes_against_itself():
    report = run(box_dump())
    assert report["passed"], report["failed"] + report["not_measured"]
    mesh = by_id(report)["mesh"]["details"]
    assert mesh["non_manifold_edges"] == 0 and mesh["overlap_pairs"] == 0 and mesh["slabs_not_inset"] == []
    assert sorted(lp["kind"] for lp in mesh["open_loops"]) == ["roof-foot", "roof-plane"]
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
    assert sorted((lp["kind"], lp["edges"], lp["allowed"]) for lp in loops if lp["kind"] == "other") ==         [("other", 4, False), ("other", 4, False)]


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


def test_a_solid_roof_in_a_parapet_fails():
    # user rule 2026-10-10: every slab is inset; the checker requires the joint, it does not only allow it
    report = run(box_dump(roof_inset=0.0), box_dump(roof_inset=0.0))
    mesh = by_id(report)["mesh"]
    assert mesh["status"] == "fail" and mesh["details"]["slabs_not_inset"] == ["roof"]
    assert mesh["details"]["open_loops"] == [] and mesh["value"]["open_loops_not_allowed"] == 0


@pytest.mark.parametrize("gap, ok", [(0.001, False), (0.002, True), (0.010, True), (0.012, False), (0.05, False)])
def test_inset_gap_is_2_to_10_mm(gap, ok):
    report = run(box_dump(roof_inset=gap), box_dump(roof_inset=gap), spec=plates(gap=gap))
    assert (by_id(report)["mesh"]["status"] == "pass") == ok


def test_two_inset_planes_on_one_roof_are_not_allowed():
    patch = ([[3, 3, 6.605], [4, 3, 6.605], [4, 4, 6.605], [3, 4, 6.605]], ROOF)
    report = run(box_dump(roof_inset=0.005, extra=[patch]), box_dump(roof_inset=0.005))
    assert by_id(report)["mesh"]["status"] == "fail"
    assert "other" in [k for k, _, ok in loops_of(report) if not ok]          # the extra plate: no slab joint


def test_open_bottom_ring_is_allowed():
    dump = box_dump()
    body = dump["meshes"][0]
    v = np.asarray(body["vertices"])
    keep = [k for k, t in enumerate(body["triangles"]) if not np.all(v[t][:, 2] == 0)]
    body["triangles"] = [body["triangles"][k] for k in keep]
    body["material_ids"] = [body["material_ids"][k] for k in keep]
    del body["polygon_sizes"]
    report = run(dump)
    assert loops_of(report) == [("bottom", "", True), ("roof-foot", "roof", True), ("roof-plane", "roof", True)]



def test_lone_foot_or_plane_is_not_a_joint():
    # a plane with no hole under it (welded roof + an extra plane) and a hole with no plane both fail
    patch = ([[3, 3, 6.605], [4, 3, 6.605], [4, 4, 6.605], [3, 4, 6.605]], ROOF)
    assert by_id(run(box_dump(extra=[patch]), box_dump()))["mesh"]["status"] == "fail"
    dump = box_dump(roof_inset=0.005)
    body = dump["meshes"][0]
    v = np.asarray(body["vertices"])
    keep = [k for k, t in enumerate(body["triangles"]) if not np.all(np.abs(v[t][:, 2] - 6.605) < 1e-6)]
    body["triangles"] = [body["triangles"][k] for k in keep]
    body["material_ids"] = [body["material_ids"][k] for k in keep]
    del body["polygon_sizes"]
    report = run(dump, box_dump())
    assert loops_of(report) == [("other", "roof", False)]


@pytest.mark.parametrize("embed, ok", [(-0.02, False), (0.0, False), (0.005, False), (0.01, True), (0.02, True),
                                       (0.05, True), (0.08, False)])
def test_plane_is_embedded_into_the_parapet_by_an_even_offset(embed, ok):
    # user 2026-10-10: contour B outside contour A, the plane embedded into the parapet faces (B02: 20 mm)
    report = run(box_dump(roof_inset=0.005, roof_embed=embed), box_dump(), spec=plates(overlap=max(embed, 0.001)))
    assert (by_id(report)["mesh"]["status"] == "pass") == ok


@pytest.mark.parametrize("gap, overlap, ok", [(0.005, 0.02, True), (0.0054, 0.0204, True), (0.006, 0.02, False),
                                              (0.005, 0.03, False)])
def test_plates_match_the_building_parameters_of_the_spec(gap, overlap, ok):
    # user 2026-10-10: plate_gap_m / plate_overlap_m are building parameters; the checker compares within plate_tol_m
    report = run(box_dump(), box_dump(), spec=plates(gap, overlap))
    mesh = by_id(report)["mesh"]
    assert (mesh["status"] == "pass") == ok and bool(mesh["details"]["plates_off_spec"]) != ok


def test_uneven_embed_is_no_joint():
    dump = box_dump(roof_inset=0.005)
    for v in dump["meshes"][0]["vertices"]:
        if abs(v[2] - 6.605) < 1e-6 and v[0] > 9:
            v[0] += 0.03                 # the east side embedded 50 mm, the rest 20 mm
    assert by_id(run(dump, box_dump()))["mesh"]["status"] == "fail"


def test_outlines_touching_at_one_vertex_are_not_one_loop():
    # Codex review 1 of PR #54: two roof quads sharing one vertex are not a simple closed cycle
    quads = [([[3, 3, 6.605], [4, 3, 6.605], [4, 4, 6.605], [3, 4, 6.605]], ROOF),
             ([[4, 4, 6.605], [5, 4, 6.605], [5, 5, 6.605], [4, 5, 6.605]], ROOF)]
    report = run(box_dump(extra=quads), box_dump())
    assert by_id(report)["mesh"]["status"] == "fail"


def test_foot_and_plane_must_be_one_joint_in_plan():
    # Codex review 1 of PR #54: a hole and a plane far apart are no joint
    dump = box_dump(roof_inset=0.005)
    for v in dump["meshes"][0]["vertices"]:
        if abs(v[2] - 6.605) < 1e-6:
            v[0] += 30
    assert by_id(run(dump, box_dump()))["mesh"]["status"] == "fail"



def offset_triangle(pts, d):
    """Edges of a CCW triangle moved out by d, corners where they meet (unclipped mitre)."""
    lines = []
    for i in range(3):
        p0, p1 = np.array(pts[i], float), np.array(pts[(i + 1) % 3], float)
        e = (p1 - p0) / np.linalg.norm(p1 - p0)
        lines.append((p0 + np.array([e[1], -e[0]]) * d, e))
    out = []
    for i in range(3):
        (p, e1), (q, e2) = lines[i - 1], lines[i]
        t = np.linalg.solve(np.array([e1, -e2]).T, q - p)[0]
        out.append(list(p + e1 * t))
    return out


def test_acute_corner_keeps_its_full_mitre():
    # Codex review 2 of PR #54: A = a sharp triangle hole, B = A's edges offset 20 mm with unclipped corners
    a = [[1, 1], [9, 1], [1, 2]]
    b, o = offset_triangle(a, 0.02), offset_triangle(a, 0.3)
    z, top = 6.6, 7.1
    faces = [([[*b[0], z + 0.005], [*b[1], z + 0.005], [*b[2], z + 0.005]], ROOF)]
    for i in range(3):
        j = (i + 1) % 3
        faces.append(([[*a[i], z], [*a[j], z], [*a[j], top], [*a[i], top]], ROOF))          # parapet inner face
        faces.append(([[*a[i], top], [*a[j], top], [*o[j], top], [*o[i], top]], ROOF))      # cap
        faces.append(([[*o[i], 0], [*o[j], 0], [*o[j], top], [*o[i], top]], FACADE))        # outer wall
    soup = from_dump({"meshes": [_mesh("m", faces)],
                      "helpers": [{"name": "LEVEL_roof", "location": [0, 0, z]}, {"name": "LEVEL_L0", "location": [0, 0, 0]}]})
    loops = checks.check_mesh(soup, TOL, checks.load_ranges())["details"]["open_loops"]
    assert sorted(lp["kind"] for lp in loops) == ["bottom", "roof-foot", "roof-plane"], loops


def test_evenness_tolerance_is_the_weld_tolerance():
    # Codex review 2 of PR #54: one side embedded 0.9 mm more is uneven
    dump = box_dump(roof_inset=0.005)
    for v in dump["meshes"][0]["vertices"]:
        if abs(v[2] - 6.605) < 1e-6 and v[0] > 9:
            v[0] += 0.0009
    assert by_id(run(dump, box_dump()))["mesh"]["status"] == "fail"


# issue #57: a vertex where two face fans meet (no shared edge through it) is non-manifold


def cube_faces(lo, hi, mid=FACADE):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    P = lambda x, y, z: [x, y, z]  # noqa: E731
    return [([P(x0, y0, z0), P(x0, y1, z0), P(x1, y1, z0), P(x1, y0, z0)], mid),
            ([P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], mid),
            ([P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)], mid),
            ([P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)], mid),
            ([P(x1, y1, z0), P(x0, y1, z0), P(x0, y1, z1), P(x1, y1, z1)], mid),
            ([P(x0, y1, z0), P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1)], mid)]


def test_two_fans_meeting_at_one_vertex_fail_the_mesh_check():
    # a closed cube touching the parapet top only at its corner (10, 10, 7.2): every edge has two faces
    report = run(box_dump(extra=cube_faces((10, 10, 7.2), (11, 11, 8.2))))
    mesh = by_id(report)["mesh"]
    assert mesh["status"] == "fail" and mesh["details"]["non_manifold_edges"] == 0
    assert mesh["value"]["non_manifold_vertices"] == 1
    assert mesh["details"]["non_manifold_vertex_points"] == [[10.0, 10.0, 7.2]]


def test_open_fans_and_the_inset_roof_are_one_fan_each():
    for dump in (box_dump(),):
        mesh = by_id(run(dump))["mesh"]
        assert mesh["status"] == "pass" and mesh["value"]["non_manifold_vertices"] == 0


@pytest.mark.parametrize("spec_gap, gap, spec_overlap, overlap, ok", [
    (0.006, 0.00654, 0.02, 0.02, False), (0.005, 0.00549, 0.02, 0.02, True), (0.005, 0.005, 0.02, 0.02049, True)])
def test_plates_are_compared_unrounded(spec_gap, gap, spec_overlap, overlap, ok):
    # Codex review 1 of PR #64: the raw gap / overlap against plate_tol_m, rounding only in the report
    report = run(box_dump(roof_inset=gap, roof_embed=overlap), box_dump(), spec=plates(spec_gap, spec_overlap))
    assert (by_id(report)["mesh"]["status"] == "pass") == ok


@pytest.mark.parametrize("gap, overlap", [(0.0055, 0.02), (0.0045, 0.02), (0.005, 0.0195), (0.005, 0.0205)])
def test_plates_exactly_at_the_tolerance_pass(gap, overlap):
    # Codex review 2 of PR #64: plate_tol_m itself passes despite floating-point roundoff
    report = run(box_dump(roof_inset=gap, roof_embed=overlap), box_dump(), spec=plates(0.005, 0.02))
    assert by_id(report)["mesh"]["status"] == "pass"


def shaft_roof(inner_overlap=0.02):
    """box_dump with a vent shaft 2 x 2 m through the inset roof: shaft walls from the roof level up to
    7.5 m (their foot = an inner outline of the hole), the plate with a hole around the shaft, shrunk by
    inner_overlap (synthetic)."""
    import shapely
    dump = box_dump(roof_inset=0.005)
    body = dump["meshes"][0]
    v = np.asarray(body["vertices"], float)
    keep = [k for k, t in enumerate(body["triangles"]) if not np.all(np.abs(v[t][:, 2] - 6.605) < 1e-9)]
    body["triangles"] = [body["triangles"][k] for k in keep]
    body["material_ids"] = [body["material_ids"][k] for k in keep]
    body.pop("polygon_sizes", None)
    tris = []
    plate = shapely.Polygon([(0.28, 0.28), (9.72, 0.28), (9.72, 9.72), (0.28, 9.72)],
                            [[(4 + inner_overlap, 4 + inner_overlap), (6 - inner_overlap, 4 + inner_overlap),
                              (6 - inner_overlap, 6 - inner_overlap), (4 + inner_overlap, 6 - inner_overlap)]])
    for tri in shapely.get_parts(shapely.constrained_delaunay_triangles(plate)):
        a, b, c = list(tri.exterior.coords)[:3]
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
            b, c = c, b
        tris.append(([[*a, 6.605], [*b, 6.605], [*c, 6.605]], ROOF))
    sq = [(4, 4), (6, 4), (6, 6), (4, 6)]
    for (x0, y0), (x1, y1) in zip(sq, sq[1:] + sq[:1]):     # shaft walls facing out of the shaft, into the roof
        tris += [([[x1, y1, 6.6], [x0, y0, 6.6], [x0, y0, 7.5]], ROOF), ([[x1, y1, 6.6], [x0, y0, 7.5], [x1, y1, 7.5]], ROOF)]
    tris += [([[4, 4, 7.5], [6, 4, 7.5], [6, 6, 7.5]], ROOF), ([[4, 4, 7.5], [6, 6, 7.5], [4, 6, 7.5]], ROOF)]
    pts = [p for t, _ in tris for p in t]
    n = len(body["vertices"])
    body["vertices"] += pts
    body["triangles"] += [[n + 3 * i, n + 3 * i + 1, n + 3 * i + 2] for i in range(len(tris))]
    body["material_ids"] += [m for _, m in tris]
    body["polygon_sizes"] = [3] * len(body["triangles"])
    return dump


@pytest.mark.parametrize("inner, ok", [(0.02, True), (0.03, False)])
def test_a_shaft_through_an_inset_roof_is_an_inner_outline_of_its_joint(inner, ok):
    # KPP1 (user 2026-10-10, flat inset roof around its vent shaft): the shaft's foot is an inner outline
    # of the hole, the plate's hole around the shaft an inner outline of the plate, the same overlap
    report = run(shaft_roof(inner), shaft_roof(0.02))
    mesh = by_id(report)["mesh"]
    assert (mesh["status"] == "pass") == ok, loops_of(report)
    if ok:
        assert sorted(k for k, *_ in loops_of(report)) == ["roof-foot", "roof-foot", "roof-plane", "roof-plane"]


@pytest.mark.parametrize("width", [0.03, 0.039])
def test_a_plate_over_a_narrow_shaft_is_no_joint(width):
    # Codex review 1 of PR #65: a shaft narrower than twice the overlap would vanish from the grown hole;
    # a plate without a hole over it is not accepted
    import shapely
    dump = shaft_roof(0.02)
    body = dump["meshes"][0]
    v = np.asarray(body["vertices"], float)
    keep = [k for k, t in enumerate(body["triangles"]) if v[t][:, 2].min() < 6.6 - 1e-9 or not (
        np.all(v[t][:, 0] >= 4 - 1e-9) and np.all(v[t][:, 0] <= 6 + 1e-9) and np.all(v[t][:, 1] >= 4 - 1e-9)
        and np.all(v[t][:, 1] <= 6 + 1e-9) and v[t][:, 2].max() > 6.61)]
    keep = [k for k in keep if not np.all(np.abs(v[body["triangles"][k]][:, 2] - 6.605) < 1e-9)]
    body["triangles"] = [body["triangles"][k] for k in keep]
    body["material_ids"] = [body["material_ids"][k] for k in keep]
    tris = []
    plate = shapely.Polygon([(0.28, 0.28), (9.72, 0.28), (9.72, 9.72), (0.28, 9.72)])
    for tri in shapely.get_parts(shapely.constrained_delaunay_triangles(plate)):
        a, b, c = list(tri.exterior.coords)[:3]
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
            b, c = c, b
        tris.append([[*a, 6.605], [*b, 6.605], [*c, 6.605]])
    sq = [(4, 4), (4 + width, 4), (4 + width, 6), (4, 6)]
    for (x0, y0), (x1, y1) in zip(sq, sq[1:] + sq[:1]):
        tris += [[[x1, y1, 6.6], [x0, y0, 6.6], [x0, y0, 7.5]], [[x1, y1, 6.6], [x0, y0, 7.5], [x1, y1, 7.5]]]
    tris += [[[4, 4, 7.5], [4 + width, 4, 7.5], [4 + width, 6, 7.5]], [[4, 4, 7.5], [4 + width, 6, 7.5], [4, 6, 7.5]]]
    n = len(body["vertices"])
    body["vertices"] += [p for t in tris for p in t]
    body["triangles"] += [[n + 3 * i, n + 3 * i + 1, n + 3 * i + 2] for i in range(len(tris))]
    body["material_ids"] += [ROOF] * len(tris)
    body["polygon_sizes"] = [3] * len(body["triangles"])
    assert by_id(run(dump, shaft_roof(0.02)))["mesh"]["status"] == "fail"
    from dt_ai.spec import extract_spec
    _, report = extract_spec(dump, {"id": "bench-synth-box", "frame": {"to_object": np.eye(4).tolist()}})
    assert [q["kind"] for q in report["questions"]] == ["plate-params"]

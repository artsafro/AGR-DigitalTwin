"""Build path by source modules (dt_ai.geometry.from_source, user 2026-10-13/14) and the checker rules it needs:
seated loops, the decor mesh left out of the topology checks, slab boxes, overlaps past the weld, spec-based storey
areas for a panelised source."""
import json

import numpy as np
import pytest
import shapely
from shapely.geometry import Polygon

from dt_ai.geometry import from_source as fs
from dt_ai.geometry.from_spec import _Mesh
from dt_ai.spec.model import Spec
from test_geometry_checks import TOL
from twinqa.geometry import checks
from twinqa.geometry.mesh import edge_uses, from_dump, weld

LEVELS = [("L0", 0.0), ("L1", 3.3), ("roof", 6.6)]
INPUTS = fs.Inputs(levels=LEVELS)


def _soup_counts(mesh: _Mesh, w=1e-6):
    d = mesh.mesh("m")
    v, t = np.asarray(d["vertices"], float), np.asarray(d["triangles"], int)
    _, counts, _ = edge_uses(t, weld(v, w))
    return d, counts


def _quad_box(name, lo, hi, mid=0):
    """A closed axis box as a dump mesh."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    m = _Mesh()
    fs._box(m, (np.zeros(2), np.array([1.0, 0.0]), np.array([0.0, -1.0])), (x0, -y1, z0), (x1, -y0, z1), mid)
    d = m.mesh(name)
    d.pop("polygons", None)
    return d


# ---------------------------------------------------------------------------------------------- builders

def test_a_slab_box_is_closed_and_filled_with_quads():
    m = _Mesh()
    poly = Polygon([[0, 0], [10, 0], [10, 6], [4, 6], [4, 10], [0, 10]])
    # the L-shaped cell at the notch has no quad without a new vertex: CDT on its own outline, counted
    assert fs.slab_box(m, poly, 3.3, 3.0, 21, 21, 21, step=3.0) == 1
    d, counts = _soup_counts(m)
    assert counts.max() == 2 and counts.min() == 2                            # closed, manifold
    assert d["polygon_sizes"].count(4) > d["polygon_sizes"].count(3)


def test_an_oblique_slab_edge_falls_back_to_triangles_counted():
    m = _Mesh()
    fb = fs.slab_box(m, Polygon([[0, 0], [10, 0], [10, 6], [7, 10], [0, 10]]), 3.3, 3.0, 21, 21, 21, step=3.0)
    d, counts = _soup_counts(m)
    assert counts.max() == 2 and counts.min() == 2 and 3 in d["polygon_sizes"]
    assert fb >= 0


def test_storey_walls_are_quads_with_their_own_columns_and_no_t_junction():
    m = _Mesh()
    poly = Polygon([[0, 0], [10, 0], [10, 10], [0, 10]])
    openings = {0: [[2.0, 3.0, 0.9, 2.4]], 1: [[4.0, 6.0, 0.6, 2.4], [7.0, 8.0, 0.9, 2.4]]}
    fs.storey_walls(m, poly, openings, 0.0, 3.0, INPUTS)
    d, counts = _soup_counts(m)
    assert set(d["polygon_sizes"]) == {4}
    assert counts.max() == 2                                                  # no T-junction, no fin
    v, t = np.asarray(d["vertices"]), np.asarray(d["triangles"])
    ids = weld(v, 1e-6)
    first = {int(k): i for i, k in reversed(list(enumerate(ids)))}
    e, c, _ = edge_uses(t, ids)
    zs = {round(float(v[first[int(k)], 2]), 6) for a, b in e[c == 1] for k in (a, b)}
    assert zs == {0.0, 3.0}                                                   # open only at its bottom and top ring
    assert 11 in d["material_ids"] and 6 in d["material_ids"]                 # opening planes and reveals


def test_an_opening_keeps_its_reveal_depth_off_a_convex_corner():
    poly = Polygon([[0, 0], [10, 0], [10, 10], [0, 10]])
    glass = [shapely.LineString([[0.05, 0.0], [3.0, 0.0]])]
    ops = fs.wall_openings(poly, glass, [(0.5, 2.5)], 0.0, 3.0, 0.003, depth=0.4)
    assert ops[0][0][0] == pytest.approx(0.45)                                # 0.4 + WALL_END_M


def test_railings_are_one_closed_plate_per_free_side_trimmed_at_corners():
    m = _Mesh()
    deck = Polygon([[0, 0], [10, 0], [10, 3], [0, 3]])
    upper = Polygon([[0, 3], [10, 3], [10, 10], [0, 10]])                     # the storey above stands on y = 3
    assert fs.terrace_railings(m, deck, upper, 3.3, 1.2, 12) == 3              # south, east, west sides
    d, counts = _soup_counts(m)
    assert counts.max() == 2 and counts.min() == 2                            # closed, no shared face at a corner
    v = np.asarray(d["vertices"])
    assert v[:, 2].min() == pytest.approx(3.3 + fs.RAILING_LIFT_M) and v[:, 2].max() == pytest.approx(4.5)


def _boxes_soup(boxes):
    vs, ts, base = [], [], 0
    for lo, hi in boxes:
        d = _quad_box("x", lo, hi)
        vs.append(np.asarray(d["vertices"], float))
        ts.append(np.asarray(d["triangles"], int) + base)
        base += len(d["vertices"])
    return np.vstack(vs), np.vstack(ts)


def test_decor_pieces_of_one_element_merge_and_an_off_axis_piece_is_not_boxed():
    v, t = _boxes_soup([((0, 0, 0), (0.3, 0.2, 3.0)), ((0, 0, 3.02), (0.3, 0.2, 6.0)),   # one pier, split at 3 m
                        ((5, 0, 0), (5.3, 0.25, 3.0))])                                  # another section
    odd = []
    els = fs.decor_elements(v, t, odd=odd)
    assert len(els) == 2 and not odd
    zs = sorted((lo[2], hi[2]) for _, lo, hi in els)
    assert (0.0, 6.0) in [(round(a, 3), round(b, 3)) for a, b in zs]
    c, s = np.cos(np.radians(23)), np.sin(np.radians(23))
    rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    v2, t2 = _boxes_soup([((0, 0, 0), (1.0, 0.2, 1.0))])
    odd = []
    assert fs.decor_elements(v2 @ rot.T, t2, odd=odd) == [] and len(odd) == 1


def test_flat_pieces_are_planes_and_a_sloped_face_keeps_its_own_plane():
    p = np.array([[77.116, 166.66, 78.5], [78.246, 166.66, 78.9], [78.246, 168.86, 78.9], [77.116, 168.86, 78.5]])
    v, t = p, np.array([[0, 1, 2], [0, 2, 3]])
    flat, solid = fs.split_flat(v, t)
    assert len(flat) == 2 and len(solid) == 0
    m = _Mesh()
    fs.face_planes(m, v, flat, 26)
    out = np.asarray(m.mesh("x")["vertices"])
    assert np.abs(out[:, 0].max() - 78.246) < 1e-6 and np.abs(out[:, 0].min() - 77.116) < 1e-6   # no rounded plane


# ---------------------------------------------------------------------------------------------- end to end

def _source():
    """A synthetic panelised source: slabs at L1 and the roof, glass panes on the south wall, a pier, a deck with
    a glass railing is left out; modules with their build_as."""
    def mesh(name, faces, mid=0):
        v, t = [], []
        for f in faces:
            n = len(v)
            v += [list(map(float, p)) for p in f]
            t += [[n, n + 1, n + 2], [n, n + 2, n + 3]]
        return {"name": name, "vertices": v, "triangles": t, "material_ids": [mid] * len(t), "polygon_sizes": [3] * len(t)}
    slabs = []
    for z in (3.3, 6.6):
        box = _quad_box("Slabs", (0, 0, z - 0.3), (10, 10, z))
        slabs.append(box)
    sv = slabs[0]["vertices"] + slabs[1]["vertices"]
    st = slabs[0]["triangles"] + [[a + len(slabs[0]["vertices"]) for a in tr] for tr in slabs[1]["triangles"]]
    slab = {"name": "Slabs", "vertices": sv, "triangles": st, "material_ids": [0] * len(st), "polygon_sizes": [3] * len(st)}
    glass = mesh("Glass", [[[x0, -0.03, z0], [x1, -0.03, z0], [x1, -0.03, z1], [x0, -0.03, z1]]
                           for x0, x1 in ((2, 3), (3.05, 4.5)) for z0, z1 in ((0.9, 2.4), (4.2, 5.7))])
    pier = _quad_box("Pier", (5.0, -0.25, 0.0), (5.6, 0.0, 6.6))
    pier["material_ids"] = [0] * len(pier["triangles"])
    pier["polygon_sizes"] = [3] * len(pier["triangles"])
    pier.pop("polygons", None)
    for m in (slab,):
        m.pop("polygons", None)
    dump = {"source": "synthetic", "meshes": [slab, glass, pier], "helpers": []}
    part = lambda k, o: {"source": k, "object": o, "slot": None}                       # noqa: E731
    modules = {"modules": [
        {"module": "slabs", "ids": {"Slabs": 21}, "parts": [part("Slabs", "Slabs")], "build_as": "slab_boxes"},
        {"module": "glazing", "ids": {"Glass": 11}, "parts": [part("Glass", "Glass")], "build_as": "openings_glass"},
        {"module": "decor", "ids": {"Pier": 26}, "parts": [part("Pier", "Pier")], "build_as": "boxes"}]}
    return dump, modules


def test_a_synthetic_building_by_modules_passes_its_spec_checks():
    dump, modules = _source()
    model, spec_doc, report = fs.build_from_modules(dump, modules, "syn-modules", INPUTS)
    spec = Spec.model_validate(spec_doc)
    assert [len(f.openings) for f in spec.floors] == [1, 1]                  # two panes 5 cm apart: one opening
    assert report["decor"]["boxes_total"] == 1
    soup = from_dump(model)
    res = {c["id"]: c for c in checks.run(soup, soup, spec, TOL, source_class="panelised")["checks"]}
    for cid in ("levels", "mesh", "opening_planes", "triangle_budget", "floor_areas"):
        assert res[cid]["status"] == "pass", (cid, res[cid])
    assert res["floor_areas"]["details"]["basis"] == "spec-based"
    seated = [lp for lp in res["mesh"]["details"]["open_loops"] if lp["kind"] == "seated"]
    assert seated                                                             # walls stand on the slab boxes
    with pytest.raises(Exception, match="build_as"):
        fs.build_from_modules(dump, {"modules": [{**modules["modules"][0], "build_as": "nope"}]}, "syn-modules", INPUTS)


# ---------------------------------------------------------------------------------------------- checker rules

def _dump(*meshes):
    return {"source": "synthetic", "meshes": list(meshes),
            "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]} for n, z in LEVELS]}


def _tube(name, z0, z1, size=10.0, inset=0.02):
    """Four walls (an open tube) inside a slab outline."""
    m = _Mesh()
    a, b = inset, size - inset
    pts = [np.array(p) for p in ((a, a), (b, a), (b, b), (a, b))]
    for p, q in zip(pts, pts[1:] + pts[:1]):
        d = q - p
        m.quad([[*p, z0], [*q, z0], [*q, z1], [*p, z1]], 1, [d[1], -d[0], 0])
    d = m.mesh(name)
    d.pop("polygons", None)
    return d


def test_a_wall_ring_standing_on_a_slab_is_seated_and_a_floating_one_is_not():
    slab = _quad_box("slabs", (0, 0, 3.0), (10, 10, 3.3), 21)
    on = checks.check_mesh(from_dump(_dump(slab, _tube("walls", 3.3, 6.0))), TOL, checks.load_ranges())
    kinds = [(lp["kind"], lp["allowed"]) for lp in on["details"]["open_loops"]]
    assert ("seated", True) in kinds and ("other", False) in kinds            # the top ring stands on nothing
    off = checks.check_mesh(from_dump(_dump(slab, _tube("walls", 3.4, 6.0))), TOL, checks.load_ranges())
    assert not any(lp["kind"] == "seated" for lp in off["details"]["open_loops"])


def test_the_decor_mesh_is_left_out_of_the_topology_checks():
    a = _quad_box("decor", (0, 0, 0), (1, 1, 1), 26)
    b = _quad_box("x", (0.5, 0.0, 0.0), (1.5, 1.0, 1.0), 26)        # overlapping its neighbour
    b["name"] = "decor"
    both = {"name": "decor", "vertices": a["vertices"] + b["vertices"],
            "triangles": a["triangles"] + [[i + len(a["vertices"]) for i in tr] for tr in b["triangles"]],
            "material_ids": a["material_ids"] + b["material_ids"], "polygon_sizes": a["polygon_sizes"] + b["polygon_sizes"]}
    res = checks.check_mesh(from_dump(_dump(both)), TOL, checks.load_ranges())
    assert res["details"]["decor_triangles_left_out"] == 24 and res["details"]["overlap_pairs"] == 0
    body = {**both, "name": "walls"}
    assert checks.check_mesh(from_dump(_dump(body)), TOL, checks.load_ranges())["details"]["overlap_pairs"] > 0


@pytest.mark.parametrize("gap, overlap", [(0.002, True), (0.005, False)])
def test_an_overlap_is_a_crossing_deeper_than_the_weld(gap, overlap):
    """User 2026-10-14: faces within weld_m (3 mm) overlap; a plate 5 mm off a face (plate_gap_m) does not."""
    lo = _quad_box("slabs", (0, 0, 0), (4, 4, 1), 21)
    hi = _quad_box("terraces", (0, 0, 1 + gap), (4, 4, 2), 22)
    res = checks.check_mesh(from_dump(_dump(lo, hi)), TOL, checks.load_ranges())
    assert (res["details"]["overlap_pairs"] > 0) == overlap


def test_spec_based_storey_area_takes_the_opening_recesses_off_the_contour():
    spec = Spec.model_validate({
        "id": "syn-area", "profile": "npm_min", "frame": {"object": "syn-area", "source": "s", "to_object": np.eye(4).tolist()},
        "levels": [{"name": n, "elev_m": z} for n, z in LEVELS],
        "floors": [{"level": "L0", "contour": [[0, 0], [10, 0], [10, 10], [0, 10]],
                    "openings": [{"wall": 0, "x_m": 2, "w_m": 2, "sill_m": 0.5, "h_m": 2.5, "kind": "window"}]},
                   {"level": "L1", "contour": [[0, 0], [10, 0], [10, 10], [0, 10]]}],
        "roof": {"parapet_h_m": 0.0}})
    m = _Mesh()
    fs.storey_walls(m, Polygon([[0, 0], [10, 0], [10, 10], [0, 10]]), {0: [[2, 4, 0.5, 3.0]]}, 0.0, 3.3, INPUTS)
    fs.storey_walls(m, Polygon([[0, 0], [10, 0], [10, 10], [0, 10]]), {}, 3.3, 6.6, INPUTS)
    d = m.mesh("walls")
    d.pop("polygons", None)
    soup = from_dump(_dump(d))
    res = checks.check_floor_areas(soup, soup, spec, TOL, "spec")
    assert res["status"] == "pass" and res["details"]["basis"] == "spec-based"
    rows = {r["z"]: r for r in res["details"]["floors"]["L0"]}
    assert any(r.get("etalon_m2") == pytest.approx(100 - 2 * 0.4) for r in rows.values())

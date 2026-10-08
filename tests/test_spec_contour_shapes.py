"""Level contour shapes and not-full-height deviations (issue #6). Synthetic data; not a real object."""
import json
import math

import numpy as np
import pytest
import shapely
from shapely.geometry import Polygon

from dt_ai.cli.main import main
from dt_ai.spec import extract_spec
from test_spec_extract import OBJECT, Mesh, close

LEVELS = (("L0", 0.0), ("L1", 3.3), ("roof", 6.6))


def flat(mesh, poly, z, up=True):
    """Triangulate a (possibly concave or holed) polygon at height z, facing up or down."""
    for tri in shapely.get_parts(shapely.constrained_delaunay_triangles(poly)):
        a, b, c = list(tri.exterior.coords)[:3]
        (ux, uy), (vx, vy) = np.subtract(b, a), np.subtract(c, a)
        if (ux * vy - uy * vx > 0) != up:
            b, c = c, b
        mesh.vertices += [[*a, z], [*b, z], [*c, z]]
        n = len(mesh.vertices)
        mesh.triangles.append([n - 3, n - 2, n - 1])


def walls(mesh, contour, z0, z1, boxes=(), extra_u=None):
    """Vertical walls of a CCW contour from z0 to z1, split so box corners are shared vertices.
    boxes: (wall, u0, u1, bz0, bz1, depth) projections outward from that wall."""
    pts = np.asarray(contour, dtype=float)
    for w in range(len(pts)):
        a, b = pts[w], pts[(w + 1) % len(pts)]
        length = float(np.linalg.norm(b - a))
        us = {0.0, length, *[u for bx in boxes if bx[0] == w for u in bx[1:3]], *(extra_u or {}).get(w, [])}
        zs = {z0, z1, *[z for bx in boxes if bx[0] == w for z in bx[3:5] if z0 < z < z1]}
        us, zs = sorted(us), sorted(zs)
        t = (b - a) / length
        for u0, u1 in zip(us, us[1:]):
            for za, zb in zip(zs, zs[1:]):
                p, q = a + u0 * t, a + u1 * t
                mesh.quad((*p, za), (*q, za), (*q, zb), (*p, zb))
    for w, u0, u1, bz0, bz1, depth in boxes:
        a, b = pts[w], pts[(w + 1) % len(pts)]
        t = (b - a) / np.linalg.norm(b - a)
        n = np.array([t[1], -t[0]])                      # outward for a CCW contour
        p0, p1 = a + u0 * t, a + u1 * t
        o0, o1 = p0 + depth * n, p1 + depth * n
        mesh.quad((*o0, bz0), (*o1, bz0), (*o1, bz1), (*o0, bz1))   # front
        mesh.quad((*p0, bz1), (*o0, bz1), (*o1, bz1), (*p1, bz1))   # top
        mesh.quad((*p0, bz0), (*p1, bz0), (*o1, bz0), (*o0, bz0))   # bottom
        mesh.quad((*p0, bz0), (*o0, bz0), (*o0, bz1), (*p0, bz1))   # side at u0
        mesh.quad((*o1, bz0), (*p1, bz0), (*p1, bz1), (*o1, bz1))   # side at u1


def prism(contour, boxes=(), height=6.6):
    """One block from 0 to `height` with a flat roof and no parapet."""
    b = Mesh("Body")
    walls(b, contour, 0.0, height, boxes)
    flat(b, Polygon(contour), height, up=True)
    flat(b, Polygon(contour), 0.0, up=False)
    return dump_of(b)


def dump_of(mesh):
    return {"source": "synthetic-shapes", "meshes": [mesh.dump()],
            "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]} for n, z in LEVELS]}


SQUARE10 = [[0, 0], [10, 0], [10, 10], [0, 10]]


def test_b02_like_non_90_corner_niche_and_two_roof_levels():
    lower = [[0, 0], [4, 0], [4, 0.5], [6, 0.5], [6, 0], [12, 0], [12, 6], [9, 9], [0, 9]]
    upper = [[6, 0], [12, 0], [12, 6], [9, 9], [6, 9]]
    b = Mesh("Body")
    walls(b, lower, 0.0, 3.3, extra_u={8: [3.0]})          # vertex at (6, 9) shared with the upper block
    walls(b, upper, 3.3, 6.6)
    flat(b, Polygon(lower).difference(Polygon(upper)), 3.3, up=True)   # lower roof (terrace)
    flat(b, Polygon(upper), 6.6, up=True)
    flat(b, Polygon(lower), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert close(spec.floors[0].contour, lower)
    assert close(spec.floors[1].contour, upper)
    assert (report["roof"]["plane_m"], spec.roof.parapet_h_m) == (6.6, 0.0)
    assert report["questions"] == []


def test_rounded_corner_is_one_point_with_radius():
    r, n = 1.5, 12
    arc = [[10 - r + r * math.cos(a), 10 - r + r * math.sin(a)] for a in np.linspace(0, math.pi / 2, n + 1)]
    contour = [[0, 0], [10, 0], *arc, [0, 10]]
    spec, _ = extract_spec(prism(contour), OBJECT)
    pts = spec.floors[0].contour
    assert len(pts) == 4
    corner = [p for p in pts if len(p) == 3]
    assert len(corner) == 1 and math.dist(corner[0][:2], [10, 10]) <= 0.02
    assert corner[0][2]["r"] == pytest.approx(1.5, abs=0.02)


@pytest.mark.parametrize("deg, kept", [(3.0, False), (7.0, True)])
def test_kinks_over_5_degrees_are_kept(deg, kept):
    y = 10 * math.tan(math.radians(deg))
    contour = [[0, 0], [10, 0], [20, y], [20, 10], [0, 10]]
    spec, _ = extract_spec(prism(contour), OBJECT)
    pts = spec.floors[0].contour
    assert (any(math.dist(p[:2], [10, 0]) < 0.01 for p in pts)) == kept
    assert len(pts) == (5 if kept else 4)


def only_question(dump):
    spec, report = extract_spec(dump, OBJECT)
    assert close(spec.floors[0].contour, SQUARE10) and close(spec.floors[1].contour, SQUARE10)
    assert len(report["questions"]) == 1, report["questions"]
    return report["questions"][0]


def test_plinth_never_changes_the_contour_and_is_a_high_priority_question():
    q = only_question(prism(SQUARE10, boxes=[(0, 0.0, 10.0, 0.0, 0.6, 0.1)]))
    assert (q["kind"], q["levels"], q["wall"], q["priority"]) == ("projection", ["L0"], 0, "high")
    assert q["depth_m"] == pytest.approx(0.1, abs=0.01) and q["length_m"] == pytest.approx(10, abs=0.01)


@pytest.mark.parametrize("u1, priority", [(2.9, "normal"), (3.1, "high")])
def test_facade_share_threshold_sets_priority_not_route(u1, priority):
    q = only_question(prism(SQUARE10, boxes=[(0, 2.0, u1, 1.0, 1.5, 0.2)]))
    assert q["facade_share"] == pytest.approx((u1 - 2.0) / 10, abs=0.002)
    assert (q["priority"], q["levels"]) == (priority, ["L0"])
    assert q["depth_m"] == pytest.approx(0.2, abs=0.01)


@pytest.mark.parametrize("z1, levels, priority", [(3.2, ["L0"], "normal"), (3.8, ["L0", "L1"], "high")])
def test_two_levels_threshold_sets_priority_not_route(z1, levels, priority):
    q = only_question(prism(SQUARE10, boxes=[(0, 2.0, 2.5, 2.8, z1, 0.2)]))
    assert (q["levels"], q["priority"]) == (levels, priority)


def test_full_height_pilaster_is_in_the_contour_without_a_question():
    spec, report = extract_spec(prism(SQUARE10, boxes=[(0, 2.0, 2.5, 0.0, 3.3, 0.2)]), OBJECT)
    assert close(spec.floors[0].contour, [[0, 0], [2, 0], [2, -0.2], [2.5, -0.2], [2.5, 0], [10, 0], [10, 10], [0, 10]],
                 tol=0.01) or close(spec.floors[0].contour,
                                    [[2, -0.2], [2.5, -0.2], [2.5, 0], [10, 0], [10, 10], [0, 10], [0, 0], [2, 0]])
    assert close(spec.floors[1].contour, SQUARE10)
    assert report["questions"] == []


def test_cli_writes_the_questions_file(tmp_path):
    dump, obj, out = tmp_path / "dump.json", tmp_path / "object.json", tmp_path / "spec-v001.json"
    dump.write_text(json.dumps(prism(SQUARE10, boxes=[(0, 0.0, 10.0, 0.0, 0.6, 0.1)])), encoding="utf-8")
    obj.write_text(json.dumps(OBJECT), encoding="utf-8")
    assert main(["spec", "extract", "--dump", str(dump), "--object", str(obj), "--output", str(out)]) == 0
    text = out.with_suffix(".questions.md").read_text(encoding="utf-8")
    assert "| 1 | high | projection | L0 | 0 | 0.1 | 10.0 | 100% |" in text

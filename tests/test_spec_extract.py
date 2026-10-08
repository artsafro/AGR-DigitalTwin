"""Spec extractor on a synthetic box (issue #5). Synthetic data; not a real object."""
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pytest

from dt_ai.cli.main import main
from dt_ai.spec import Spec, SpecError, extract_spec
from twinqa.scene import find_blender

IDENTITY = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
OBJECT = {"id": "bench-synth-box", "frame": {"to_object": IDENTITY}}
SQUARE = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
ROOT = Path(__file__).resolve().parents[1]


class Mesh:
    def __init__(self, name):
        self.name, self.vertices, self.triangles = name, [], []

    def quad(self, a, b, c, d):
        n = len(self.vertices)
        self.vertices += [list(map(float, p)) for p in (a, b, c, d)]
        self.triangles += [[n, n + 1, n + 2], [n, n + 2, n + 3]]

    def box(self, lo, hi):
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        self.quad((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0))
        self.quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))
        self.quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1))
        self.quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))
        self.quad((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1))
        self.quad((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1))

    def dump(self):
        return {"name": self.name, "vertices": self.vertices, "triangles": self.triangles}


def box_building(canopy=True, helpers=True, shift=(0.0, 0.0, 0.0), zs=None, holes=None, roof=True,
                 dense_canopy=False):
    """B01-like box: 10 x 10 m, levels 0 / 3.3 / 6.6, parapet to 7.2, one window hole per storey
    on the south wall (exterior faces only, holes left open), optional detached canopy."""
    body = Mesh("Body")
    corners = SQUARE
    us = [0, 2, 3.5, 10]
    zs = zs or [0, 0.9, 2.4, 3.3, 4.2, 5.7, 6.6, 7.2]
    holes = {(1, 1), (1, 4)} if holes is None else holes  # (u cell, z cell) on wall 0
    for w in range(4):
        (ax, ay), (bx, by) = corners[w], corners[(w + 1) % 4]
        for i in range(3):
            for k in range(len(zs) - 1):
                if w == 0 and (i, k) in holes:
                    continue
                t0, t1 = us[i] / 10, us[i + 1] / 10
                p0 = (ax + (bx - ax) * t0, ay + (by - ay) * t0)
                p1 = (ax + (bx - ax) * t1, ay + (by - ay) * t1)
                body.quad((*p0, zs[k]), (*p1, zs[k]), (*p1, zs[k + 1]), (*p0, zs[k + 1]))
    if roof:
        inner = [[0.2, 0.2], [9.8, 0.2], [9.8, 9.8], [0.2, 9.8]]
        for w in range(4):
            o0, o1, i0, i1 = corners[w], corners[(w + 1) % 4], inner[w], inner[(w + 1) % 4]
            body.quad((*o0, 7.2), (*o1, 7.2), (*i1, 7.2), (*i0, 7.2))   # parapet cap
            body.quad((*i1, 6.6), (*i0, 6.6), (*i0, 7.2), (*i1, 7.2))   # parapet inner face
        body.quad((0.2, 0.2, 6.6), (9.8, 0.2, 6.6), (9.8, 9.8, 6.6), (0.2, 9.8, 6.6))  # roof plane
    body.quad((0, 0, 0), (0, 10, 0), (10, 10, 0), (10, 0, 0))                      # bottom
    meshes = [body]
    if canopy:
        c = Mesh("Canopy")
        c.box((1.5, -1.0, 2.5), (4.0, -0.05, 2.7))
        meshes.append(c)
    if dense_canopy:  # small area, many triangles: must not win the body by triangle count
        c = Mesh("DenseCanopy")
        for i in range(25):
            for j in range(25):
                x, y = 1.5 + i * 0.1, -1.0 - j * 0.04
                c.quad((x, y, 2.6), (x + 0.1, y, 2.6), (x + 0.1, y - 0.04, 2.6), (x, y - 0.04, 2.6))
        meshes.append(c)
    ucx = Mesh("UCX_Body_001")
    ucx.box((-5, -5, 0), (15, 15, 7.2))
    meshes.append(ucx)
    dump = {"source": "synthetic-box", "meshes": [m.dump() for m in meshes], "helpers": []}
    if helpers:
        dump["helpers"] = [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]}
                           for n, z in (("L0", 0.0), ("L1", 3.3), ("roof", 6.6))]
    for m in dump["meshes"]:
        m["vertices"] = [[x + shift[0], y + shift[1], z + shift[2]] for x, y, z in m["vertices"]]
    for h in dump["helpers"]:
        h["location"] = [a + b for a, b in zip(h["location"], shift)]
    return dump


def close(a, b, tol=0.01):
    return len(a) == len(b) and all(math.dist(p[:2], q[:2]) <= tol for p, q in zip(a, b))


def test_box_levels_contours_and_roof():
    spec, report = extract_spec(box_building(), OBJECT)
    assert [(lv.name, lv.elev_m) for lv in spec.levels] == [("L0", 0.0), ("L1", 3.3), ("roof", 6.6)]
    assert [f.level for f in spec.floors] == ["L0", "L1"]
    for f in spec.floors:
        assert close(f.contour, SQUARE), f.contour
    assert abs(spec.roof.parapet_h_m - 0.6) <= 0.01
    assert abs(report["roof"]["plane_m"] - 6.6) <= 0.01 and report["roof"]["plane_vs_top_level_m"] == 0
    # sections through the window holes stay open; the closed ones decide the contour
    assert report["floors"]["L0"]["closed_sections"] < report["floors"]["L0"]["sections"]
    assert spec.frame.object == "bench-synth-box"


def test_attachments_and_collision_are_not_body():
    with_canopy, rep = extract_spec(box_building(canopy=True), OBJECT)
    without, _ = extract_spec(box_building(canopy=False), OBJECT)
    assert rep["attachment_parts_ignored"] == 1
    assert with_canopy.floors == without.floors
    # attachments are deferred (HARNESS_PLAN §4: first step without them): no spec entry yet
    assert with_canopy.attachments == [] and with_canopy == without


def test_frame_moves_source_into_object_system():
    shifted = box_building(shift=(100.0, -50.0, 2.0))
    obj = {"id": "bench-synth-box", "frame": {"to_object": [[1, 0, 0, -100], [0, 1, 0, 50], [0, 0, 1, -2], [0, 0, 0, 1]]}}
    spec, _ = extract_spec(shifted, obj)
    assert close(spec.floors[0].contour, SQUARE)
    assert spec.levels[1].elev_m == pytest.approx(3.3)


def test_missing_frame_fails():
    with pytest.raises(SpecError, match="frame"):
        extract_spec(box_building(), {"id": "bench-synth-box"})


def test_levels_are_never_guessed():
    with pytest.raises(SpecError, match="no levels"):
        extract_spec(box_building(helpers=False), OBJECT)
    revit_levels = {**OBJECT, "levels": [{"name": "L0", "elev_m": 0}, {"name": "L1", "elev_m": 3.3},
                                         {"name": "roof", "elev_m": 6.6}]}
    spec, _ = extract_spec(box_building(helpers=False), revit_levels)
    assert [lv.name for lv in spec.levels] == ["L0", "L1", "roof"]
    with pytest.raises(SpecError, match="twice"):
        extract_spec(box_building(), revit_levels)


def test_spec_contract_round_trip():
    spec, _ = extract_spec(box_building(), OBJECT)
    again = Spec.model_validate(json.loads(spec.model_dump_json(exclude_none=True)))
    assert again == spec
    bad = spec.model_dump()
    bad["frame"]["to_object"][3] = [0, 0, 1, 1]
    with pytest.raises(ValueError):
        Spec.model_validate(bad)


def test_cli_writes_spec_and_report_and_refuses_overwrite(tmp_path, capsys):
    dump, obj, out = tmp_path / "dump.json", tmp_path / "object.json", tmp_path / "spec-v001.json"
    dump.write_text(json.dumps(box_building()), encoding="utf-8")
    obj.write_text(json.dumps(OBJECT), encoding="utf-8")
    args = ["spec", "extract", "--dump", str(dump), "--object", str(obj), "--output", str(out)]
    assert main(args) == 0
    assert Spec.model_validate_json(out.read_text(encoding="utf-8")).floors[0].level == "L0"
    assert json.loads(out.with_suffix(".report.json").read_text(encoding="utf-8"))["parts"] == 2
    assert main(args) == 1
    assert "exists" in capsys.readouterr().err
    out2 = tmp_path / "spec-v002.json"
    out2.with_suffix(".report.json").write_text("{}", encoding="utf-8")   # evidence of an earlier run
    assert main(args[:-1] + [str(out2)]) == 1 and not out2.exists()
    assert out2.with_suffix(".report.json").read_text(encoding="utf-8") == "{}"


def stepped_building():
    """Lower block 10 x 10 m to 3.3 with an 84 m2 outside terrace, upper block 4 x 4 m to 6.6,
    parapet to 7.2: the terrace must not be taken for the roof (Codex review P1)."""
    b = Mesh("Body")
    lo, hi = SQUARE, [[3.0, 3.0], [7.0, 3.0], [7.0, 7.0], [3.0, 7.0]]
    inner = [[3.2, 3.2], [6.8, 3.2], [6.8, 6.8], [3.2, 6.8]]
    for w in range(4):
        a, c = w, (w + 1) % 4
        b.quad((*lo[a], 0), (*lo[c], 0), (*lo[c], 3.3), (*lo[a], 3.3))            # lower walls
        b.quad((*lo[a], 3.3), (*lo[c], 3.3), (*hi[c], 3.3), (*hi[a], 3.3))        # terrace
        b.quad((*hi[a], 3.3), (*hi[c], 3.3), (*hi[c], 7.2), (*hi[a], 7.2))        # upper walls
        b.quad((*hi[a], 7.2), (*hi[c], 7.2), (*inner[c], 7.2), (*inner[a], 7.2))  # parapet cap
        b.quad((*inner[c], 6.6), (*inner[a], 6.6), (*inner[a], 7.2), (*inner[c], 7.2))
    b.quad((3.2, 3.2, 6.6), (6.8, 3.2, 6.6), (6.8, 6.8, 6.6), (3.2, 6.8, 6.6))
    b.quad((0, 0, 0), (0, 10, 0), (10, 10, 0), (10, 0, 0))
    return {"source": "synthetic-stepped", "meshes": [b.dump()],
            "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]}
                        for n, z in (("L0", 0.0), ("L1", 3.3), ("roof", 6.6))]}


def test_terrace_is_not_the_roof():
    spec, report = extract_spec(stepped_building(), OBJECT)
    assert close(spec.floors[0].contour, SQUARE)
    assert close(spec.floors[1].contour, [[3, 3], [7, 3], [7, 7], [3, 7]])
    assert report["roof"]["plane_m"] == pytest.approx(6.6, abs=0.01)
    assert spec.roof.parapet_h_m == pytest.approx(0.6, abs=0.01)


def test_missing_roof_is_an_error_not_a_zero_parapet():
    with pytest.raises(SpecError, match="no up-facing roof surface"):
        extract_spec(box_building(roof=False), OBJECT)


def test_storey_without_a_closed_section_is_an_error():
    # a slot through the whole ground storey: no cut closes, and no contour is invented
    with pytest.raises(SpecError, match="level L0: none of"):
        extract_spec(box_building(holes={(1, 0), (1, 1), (1, 2)}), OBJECT)


def test_cuts_on_vertex_rows_still_section():
    rows = [round(0.137 + 0.25 * k, 3) for k in range(27)]
    zs = sorted({0, 3.3, 6.6, 7.2, *[z for z in rows if z < 6.6]})
    spec, report = extract_spec(box_building(zs=zs, holes=set()), OBJECT)
    assert report["floors"]["L0"]["closed_sections"] == report["floors"]["L0"]["sections"]
    assert close(spec.floors[0].contour, SQUARE)


def test_body_is_the_largest_area_not_the_most_triangles():
    spec, report = extract_spec(box_building(dense_canopy=True), OBJECT)
    assert report["attachment_parts_ignored"] == 2
    assert close(spec.floors[0].contour, SQUARE)


def test_weld_does_not_depend_on_the_rounding_grid():
    from dt_ai.spec.mesh import _weld
    rep = _weld(np.array([[0.000049, 0.0, 0.0], [0.000051, 0.0, 0.0], [0.5, 0.0, 0.0]]))
    assert rep[0] == rep[1] != rep[2]


def wide_cap_building(roof=True, inner_x=8.0):
    """10 x 10 m walls to 6.8, a wide parapet cap at 6.8 around a roof at 6.6 spanning x 2..inner_x,
    y 2..8 (Codex reviews 2 and 3 P1): the larger cap near the roof level must not become the roof.
    inner_x=8 is symmetric (cap 64 m2, roof 36 m2); inner_x=4 is asymmetric (cap 88 m2 covers the
    contour's interior point, roof 12 m2)."""
    b = Mesh("Body")
    inner = [[2.0, 2.0], [inner_x, 2.0], [inner_x, 8.0], [2.0, 8.0]]
    for w in range(4):
        a, c = w, (w + 1) % 4
        b.quad((*SQUARE[a], 0), (*SQUARE[c], 0), (*SQUARE[c], 6.8), (*SQUARE[a], 6.8))
        b.quad((*SQUARE[a], 6.8), (*SQUARE[c], 6.8), (*inner[c], 6.8), (*inner[a], 6.8))
        b.quad((*inner[c], 6.6), (*inner[a], 6.6), (*inner[a], 6.8), (*inner[c], 6.8))
    if roof:
        b.quad((2, 2, 6.6), (inner_x, 2, 6.6), (inner_x, 8, 6.6), (2, 8, 6.6))
    b.quad((0, 0, 0), (0, 10, 0), (10, 10, 0), (10, 0, 0))
    return {"source": "synthetic-wide-cap", "meshes": [b.dump()],
            "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]}
                        for n, z in (("L0", 0.0), ("L1", 3.3), ("roof", 6.6))]}


@pytest.mark.parametrize("inner_x", [8.0, 4.0])
def test_wide_cap_around_a_small_roof_is_a_question_never_6_8(inner_x):
    # roof 36 % / 12 % of the floor under a cap at 6.8: "roof or cap?" goes to the user (issue #16)
    with pytest.raises(SpecError, match="covers only .* roof or cap"):
        extract_spec(wide_cap_building(inner_x=inner_x), OBJECT)
    with pytest.raises(SpecError, match="no up-facing roof surface"):
        extract_spec(wide_cap_building(roof=False, inner_x=inner_x), OBJECT)


def test_mirroring_frame_keeps_the_roof_facing_up():
    mirror = {"id": "bench-synth-box", "frame": {"to_object": [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}}
    spec, report = extract_spec(box_building(canopy=False), mirror)
    assert close(spec.floors[0].contour, [[-10, 0], [0, 0], [0, 10], [-10, 10]])
    assert (report["roof"]["plane_m"], spec.roof.parapet_h_m) == (6.6, 0.6)


def test_flat_roof_without_parapet_is_the_roof():
    b = Mesh("Body")
    for w in range(4):
        a, c = w, (w + 1) % 4
        b.quad((*SQUARE[a], 0), (*SQUARE[c], 0), (*SQUARE[c], 6.6), (*SQUARE[a], 6.6))
    b.quad((0, 0, 6.6), (10, 0, 6.6), (10, 10, 6.6), (0, 10, 6.6))
    b.quad((0, 0, 0), (0, 10, 0), (10, 10, 0), (10, 0, 0))
    dump = {"source": "synthetic-flat", "meshes": [b.dump()],
            "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]}
                        for n, z in (("L0", 0.0), ("L1", 3.3), ("roof", 6.6))]}
    spec, report = extract_spec(dump, OBJECT)
    assert report["roof"]["plane_m"] == pytest.approx(6.6, abs=0.001)
    assert spec.roof.parapet_h_m == 0


def ring_building(inner, roof_z=6.6, edge_z=6.8, roof=True, shaft=False, roof_level=6.6):
    """Counterexamples of Codex review of PR #18: 10 x 10 m walls to edge_z, a cap ring at edge_z
    around `inner`, a roof at roof_z inside it (optional), or an open shaft through the building."""
    b = Mesh("Body")
    for a in range(4):
        c = (a + 1) % 4
        b.quad((*SQUARE[a], 0), (*SQUARE[c], 0), (*SQUARE[c], edge_z), (*SQUARE[a], edge_z))
        b.quad((*SQUARE[a], edge_z), (*SQUARE[c], edge_z), (*inner[c], edge_z), (*inner[a], edge_z))
        b.quad((*inner[c], roof_z), (*inner[a], roof_z), (*inner[a], edge_z), (*inner[c], edge_z))
        if shaft:
            b.quad((*inner[a], 0), (*inner[c], 0), (*inner[c], edge_z), (*inner[a], edge_z))
    if roof:
        b.quad(*[(*q, roof_z) for q in inner])
    b.quad((0, 0, 0), (0, 10, 0), (10, 10, 0), (10, 0, 0))
    return b, {"source": "synthetic-ring", "meshes": [b.dump()],
               "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]}
                           for n, z in (("L0", 0.0), ("L1", 3.3), ("roof", roof_level))]}


SMALL = [[2, 2], [3, 2], [3, 2.6], [2, 2.6]]


def test_roof_is_confirmed_at_the_input_level_not_guessed():
    # cap covering 99.4 % of the floor around a 0.6 m2 patch, or around a 0.1 m2 ledge only:
    # the patch is not confirmed as the roof (Codex review 2 of PR #18)
    for ledge in (False, True):
        b, d = ring_building(SMALL, roof=not ledge)
        if ledge:
            b.quad((2, 2, 6.6), (3, 2, 6.6), (3, 2.1, 6.6), (2, 2.1, 6.6))
            d["meshes"] = [b.dump()]
        with pytest.raises(SpecError, match="covers only"):
            extract_spec(d, OBJECT)
    # same cap, no roof: the cap is not taken for a roof 0.2 m off the level
    with pytest.raises(SpecError, match="no up-facing roof surface .* \\[6.8\\]"):
        extract_spec(ring_building(SMALL, roof=False)[1], OBJECT)
    # roof truly at 6.4 while the input says 6.6: a question about the level, not a silent pick
    b, d = ring_building([[2, 2], [4, 2], [4, 8], [2, 8]], roof_z=6.4)
    b.quad((0, 0, 6.8), (10, 0, 6.8), (10, 0, 6.5), (0, 0, 6.5))
    b.quad((0, 0, 6.5), (10, 0, 6.5), (10, -2, 6.5), (0, -2, 6.5))   # outside terrace at 6.5
    d["meshes"] = [b.dump()]
    with pytest.raises(SpecError, match="check the roof level"):
        extract_spec(d, OBJECT)


def test_flat_roof_with_a_small_open_shaft_is_the_roof():
    _, d = ring_building([[2, 2], [4, 2], [4, 4], [2, 4]], roof_z=6.4, edge_z=6.6, roof=False, shaft=True)
    spec, report = extract_spec(d, OBJECT)
    assert (report["roof"]["plane_m"], spec.roof.parapet_h_m, report["roof"]["closed_share"]) == (6.6, 0.0, 0.96)


@pytest.mark.parametrize("filler", ["ledge", "underside"])
def test_roof_that_does_not_close_the_floor_is_missing(filler):
    # wide asymmetric cap, no roof, but some up-facing surface at the roof level
    d = wide_cap_building(roof=False, inner_x=4)
    b = Mesh("Body")
    b.vertices, b.triangles = d["meshes"][0]["vertices"], d["meshes"][0]["triangles"]
    if filler == "ledge":
        b.quad((2, 2, 6.6), (3, 2, 6.6), (3, 2.1, 6.6), (2, 2.1, 6.6))
    else:
        inner = [[2, 2], [4, 2], [4, 8], [2, 8]]
        for a in range(4):
            c = (a + 1) % 4
            b.quad((*SQUARE[a], 6.6), (*SQUARE[c], 6.6), (*inner[c], 6.6), (*inner[a], 6.6))
    d["meshes"] = [b.dump()]
    with pytest.raises(SpecError, match="covers only 0%" if filler == "ledge" else "close only 88%"):
        extract_spec(d, OBJECT)


def test_weld_never_moves_a_vertex_more_than_the_weld_distance():
    from dt_ai.spec.mesh import WELD_M, _weld
    chain = np.array([[i * 4e-5, 0.0, 0.0] for i in range(301)])  # 12 mm of vertices 40 um apart
    rep = _weld(chain)
    assert np.abs(chain - chain[rep]).max() <= WELD_M
    assert len(set(rep.tolist())) > 1


def test_object_levels_give_the_same_spec_as_helpers():
    revit_levels = {**OBJECT, "levels": [{"name": "L0", "elev_m": 0}, {"name": "L1", "elev_m": 3.3},
                                         {"name": "roof", "elev_m": 6.6}]}
    from_object, _ = extract_spec(box_building(helpers=False), revit_levels)
    from_helpers, _ = extract_spec(box_building(), OBJECT)
    assert from_object.levels == from_helpers.levels and from_object.floors == from_helpers.floors
    assert from_object.roof == from_helpers.roof


BLENDER = find_blender()
MAKE_BLEND = """
import bpy, json, sys
src, out = sys.argv[sys.argv.index('--') + 1:]
d = json.load(open(src))
bpy.ops.wm.read_factory_settings(use_empty=True)
for m in d['meshes']:
    me = bpy.data.meshes.new(m['name'])
    me.from_pydata(m['vertices'], [], m['triangles'])
    bpy.context.scene.collection.objects.link(bpy.data.objects.new(m['name'], me))
for h in d['helpers']:
    e = bpy.data.objects.new(h['name'], None)
    e.location = h['location']
    bpy.context.scene.collection.objects.link(e)
bpy.ops.wm.save_as_mainfile(filepath=out)
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
def test_blender_dump_to_spec(tmp_path):
    src, make, blend, dump = (tmp_path / n for n in ("box.json", "make.py", "box.blend", "dump.json"))
    src.write_text(json.dumps(box_building()), encoding="utf-8")
    make.write_text(MAKE_BLEND, encoding="utf-8")
    base = [BLENDER, "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1"]
    subprocess.run(base + ["--python", str(make), "--", str(src), str(blend)], check=True, capture_output=True)
    subprocess.run(base + ["--python", str(ROOT / "tools/source/measure_spec_blender.py"), "--", str(blend), str(dump)],
                   check=True, capture_output=True)
    spec, report = extract_spec(json.loads(dump.read_text(encoding="utf-8")), OBJECT)
    assert [lv.name for lv in spec.levels] == ["L0", "L1", "roof"]
    assert close(spec.floors[0].contour, SQUARE) and close(spec.floors[1].contour, SQUARE)
    assert [lv.elev_m for lv in spec.levels] == pytest.approx([0.0, 3.3, 6.6], abs=1e-4)
    assert spec.roof.parapet_h_m == pytest.approx(0.6, abs=0.01)
    assert report["attachment_parts_ignored"] == 1

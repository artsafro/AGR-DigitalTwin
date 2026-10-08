"""Spec extractor on a synthetic box (issue #5). Synthetic data; not a real object."""
import json
import math
import subprocess
from pathlib import Path

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


def box_building(canopy=True, helpers=True, shift=(0.0, 0.0, 0.0)):
    """B01-like box: 10 x 10 m, levels 0 / 3.3 / 6.6, parapet to 7.2, one window hole per storey
    on the south wall (exterior faces only, holes left open), optional detached canopy."""
    body = Mesh("Body")
    corners = SQUARE
    us = [0, 2, 3.5, 10]
    zs = [0, 0.9, 2.4, 3.3, 4.2, 5.7, 6.6, 7.2]
    holes = {(1, 1), (1, 4)}  # (u cell, z cell) on wall 0
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
    assert report["attachment_parts_ignored"] == 1

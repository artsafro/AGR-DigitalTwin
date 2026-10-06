# Boundary cases ported from AGR tests/test_glb_clearance.py (sha256 b11dd4371c83) on 2026-10-06; changes: call the
# function directly, tolerance from the VPM profile, plus an FBX roundtrip through Blender.
"""Near-parallel overlap: 0 / 4 / 6 mm, both orientations, split borders, FBX input."""
import json
import subprocess

import pytest

import check_clearance
from test_validator import PROFILES
from twinqa.clearance import near_parallel_overlaps
from twinqa.scene import find_blender

TOL = PROFILES.vpm["geometry"]["near_coplanar_spacing_m"]["min"]


def test_tolerance_comes_from_profile():
    assert TOL == 0.005  # reg p.29: 5 mm - 2 cm spacing


@pytest.mark.parametrize("distance, reverse, shift, expected", [
    (0.0, False, 0.25, 1), (0.004, True, 0.25, 1), (0.006, True, 0.25, 0), (0.0, True, 1.0, 0)])
@pytest.mark.parametrize("split_border", [False, True])
def test_partial_area_clearance_both_orientations(distance, reverse, shift, expected, split_border):
    a = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    if split_border:
        a.insert(1, [0.5, 0, 0])
    b = [[x + shift, y, distance] for x, y, _ in a]
    if reverse:
        b.reverse()
    pairs = near_parallel_overlaps([{"object": "a", "index": 0, "points": a},
                                    {"object": "b", "index": 0, "points": b}], TOL)
    assert len(pairs) == expected
    if expected:
        assert pairs[0]["same_direction"] == (not reverse)


BLENDER = find_blender()
TWO_PLANES = """
import bpy, sys
out = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
for z in (0.0, 0.003):  # 3 mm apart, overlapping
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, z))
bpy.ops.export_scene.fbx(filepath=out)
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
def test_fbx_planes_3mm_apart_are_reported(tmp_path):
    fbx = tmp_path / "planes.fbx"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", TWO_PLANES, "--", str(fbx)], check=True, capture_output=True, timeout=300)
    report = tmp_path / "report.json"
    assert check_clearance.main([str(fbx), str(report)]) == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["pair_count"] == 1 and abs(data["pairs"][0]["distance_m"] - 0.003) < 1e-6

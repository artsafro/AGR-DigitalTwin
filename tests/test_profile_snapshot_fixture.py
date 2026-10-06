"""Synthetic comparison fixtures; these do not establish native DCC delivery QA."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


@pytest.fixture
def compare(monkeypatch):
    # Only loading the pure comparison function. No Blender operations are stubbed
    # or accepted as DCC evidence; real adapters still require native bpy.
    monkeypatch.setitem(sys.modules, "bpy", ModuleType("bpy"))
    path = Path(__file__).resolve().parents[1] / "tools/profile_snapshot_common.py"
    spec = importlib.util.spec_from_file_location("profile_snapshot_fixture_common", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.compare_triangles


def quad_surface_triangles():
    positions = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    uv = [[0, 0], [1, 0], [1, 1], [0, 1]]
    return [
        {"positions": [positions[i] for i in corners],
         "uv": [uv[i] for i in corners],
         "uv_layers": {"Atlas": [uv[i] for i in corners]},
         "material": "approved_atlas", "material_index": 0}
        for corners in ([0, 1, 2], [0, 2, 3])
    ]


def test_source_quad_and_triangulated_export_keep_same_surface(compare):
    expected = quad_surface_triangles()
    actual = deepcopy(expected[::-1])
    for tri in actual:
        for key in ("positions", "uv"):
            tri[key] = tri[key][1:] + tri[key][:1]
        tri["uv_layers"] = {"FBX_UV": tri["uv_layers"]["Atlas"][1:] + tri["uv_layers"]["Atlas"][:1]}
    source_polygon_sizes = {"4": 1}
    export_polygon_sizes = {"3": 2}
    # This is the intentionally wrong test criterion from the pilot plan.
    incorrect_criterion = export_polygon_sizes == source_polygon_sizes
    assert incorrect_criterion is False
    # Correcting a representation criterion does not weaken corner/material QA.
    assert source_polygon_sizes == {"4": 1}
    assert export_polygon_sizes == {"3": 2}
    assert compare(expected, actual)["passed"] is True


@pytest.mark.parametrize("corruption", ["active_uv", "secondary_uv", "material_index", "winding", "missing_triangle"])
def test_actual_surface_corruption_fails_comparison(compare, corruption):
    expected = quad_surface_triangles()
    if corruption == "secondary_uv":
        for tri in expected:
            tri["uv_layers"]["Second"] = deepcopy(tri["uv"])
    actual = deepcopy(expected)
    if corruption == "active_uv":
        actual[0]["uv"][0][0] += 0.25
    elif corruption == "secondary_uv":
        actual[0]["uv_layers"]["Second"][0][0] += 0.25
    elif corruption == "material_index":
        # Material name can remain identical while numeric slot assignment changes.
        for tri in actual:
            tri["material_index"] = 1
    elif corruption == "winding":
        actual[0]["positions"].reverse()
        actual[0]["uv"].reverse()
        actual[0]["uv_layers"]["Atlas"].reverse()
    else:
        actual.pop()
    verdict = compare(expected, actual)
    assert verdict["passed"] is False
    assert verdict["unmatched_expected"] > 0

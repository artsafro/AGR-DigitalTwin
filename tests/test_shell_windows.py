import importlib.util
from pathlib import Path

import pytest
pytest.importorskip('numpy')
pytest.importorskip('shapely')


def checker():
    spec=importlib.util.spec_from_file_location('shell_check',Path(__file__).parents[1]/'tools/check_shell_windows.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.audit


def scene(quads):
    vertices=[v for q in quads for v in q]
    return {'angle':0.,'windows':[],'meshes':[{'vertices':vertices,'faces':[[4*i+j for j in range(4)] for i in range(len(quads))]}]}


def test_rejects_partial_coplanar_overlap_without_duplicate_vertices():
    data=scene([[(0,0,0),(2,0,0),(2,2,0),(0,2,0)],[(1,1,0),(3,1,0),(3,3,0),(1,3,0)]])
    result=checker()(data)
    assert result['global_duplicate_vertices']==0
    assert result['coplanar_overlaps'] and not result['geometry_checks_passed']


def test_rejects_non_coplanar_crossing_but_allows_open_surface():
    quad=[(0,0,0),(2,0,0),(2,2,0),(0,2,0)]
    assert checker()(scene([quad]))['geometry_checks_passed']
    result=checker()(scene([quad,[(1,.5,-1),(1,1.5,-1),(1,1.5,1),(1,.5,1)]]))
    assert result['unapproved_crossings'] and not result['geometry_checks_passed']

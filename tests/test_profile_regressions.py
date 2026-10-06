"""Counterexamples from PR28 review; synthetic inputs are not model acceptance."""
from copy import deepcopy
import importlib.util
import itertools
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import pytest


@pytest.fixture
def common(monkeypatch):
    monkeypatch.setitem(sys.modules, 'bpy', ModuleType('bpy'))
    path = Path(__file__).resolve().parents[1] / 'tools/profile_snapshot_common.py'
    spec = importlib.util.spec_from_file_location('regression_common', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def triangle(z=0):
    uv = [[0,0],[1,0],[0,1]]
    return {'positions':[[0,0,z],[1,0,z],[0,1,z]], 'uv':uv,
            'uv_layers':{'Atlas':deepcopy(uv)}, 'material':'atlas', 'material_index':0}


@pytest.mark.parametrize('value',[float('nan'),float('inf'),float('-inf')])
@pytest.mark.parametrize('field',['positions','uv','secondary_uv'])
@pytest.mark.parametrize('side',['expected','actual'])
def test_nonfinite_corners_never_pass(common,value,field,side):
    expected, actual = [triangle()], [triangle()]
    target = expected[0] if side == 'expected' else actual[0]
    if field == 'secondary_uv':
        target['uv_layers']['Second'] = [[value,0],[1,0],[0,1]]
        other = actual[0] if side == 'expected' else expected[0]
        other['uv_layers']['Second'] = deepcopy(other['uv'])
    else:
        target[field][-1][-1] = value
    assert common.compare_triangles(expected,actual)['passed'] is False


def test_ambiguous_candidates_have_full_matching_in_every_order(common):
    expected = [triangle(0),triangle(-1.5e-5)]
    actual = [triangle(.75e-5),triangle(-.75e-5)]
    for left in itertools.permutations(expected):
        for right in itertools.permutations(actual):
            result = common.compare_triangles(left,right)
            assert result['passed'] is True
            assert result['max_matched_position_error'] <= 1e-5
    actual.append(triangle(10))
    assert common.compare_triangles(expected,actual)['passed'] is False


def test_exact_duplicate_triangles_retain_multiplicity(common):
    expected = [triangle() for _ in range(4)]
    assert common.compare_triangles(expected,deepcopy(expected))['passed']
    assert not common.compare_triangles(expected,deepcopy(expected[:-1]))['passed']


def test_render_scope_excludes_hidden_reference_and_requires_names(common):
    meshes = [SimpleNamespace(name='selected',type='MESH'),
              SimpleNamespace(name='hidden_far_reference',type='MESH'),
              SimpleNamespace(name='camera',type='CAMERA')]
    assert common.render_scope(meshes,['selected']) == [meshes[0]]
    for names in ([],['selected','selected'],['missing'],['camera']):
        with pytest.raises(ValueError):
            common.render_scope(meshes,names)


def test_snapshot_writer_rejects_nan_without_creating_report(common,tmp_path):
    path = tmp_path / 'report.json'
    with pytest.raises(ValueError):
        common.write(path,{'uv':float('nan')})
    assert not path.exists()


def test_asymmetric_projected_component_fits_about_fixed_target(common):
    x,y,aspect = [-6.91,1.47,-1.47],[-1,2,0],1400/600
    scale = common.orthographic_fit(x,y,aspect)
    assert all(abs(v) < scale/2 for v in x)
    assert all(abs(v) < scale/(2*aspect) for v in y)


@pytest.mark.parametrize('x,y,aspect', [([],[],1),([0],[0],1),([float('nan')],[1],1),([1],[1],0)])
def test_invalid_projected_bounds_fail(common,x,y,aspect):
    with pytest.raises(ValueError):
        common.orthographic_fit(x,y,aspect)

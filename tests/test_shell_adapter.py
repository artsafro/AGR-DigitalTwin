import pytest
np = pytest.importorskip('numpy')
from dt_ai.geometry.shell import shell_body


def shell(thickness=.4, **changes):
    args = dict(vertices=[[0,0,0],[2,0,0],[2,0,3],[0,0,3]], faces=[[0,1,2,3]],
                outward_normals=[[0,-1,0]], thickness_m=thickness, name='body',
                units='m', source_refs=['source:wall-1'])
    args.update(changes)
    return shell_body(**args)


def test_outside_fixed_no_inner_back_face_and_provenance():
    a, b = shell(.4), shell(.2)
    for result, depth in [(a,.4), (b,.2)]:
        mesh = result['mesh']; v = np.array(mesh['vertices'])
        assert len(mesh['faces']) == 5  # one outside plus four rims
        assert len(result['face_sources']) == 5
        assert np.allclose(v[mesh['faces'][0], 1], 0)
        assert np.isclose(v[:,1].max(), depth)
        assert all(s['source_ref'] == 'source:wall-1' for s in result['face_sources'])
        assert not any(np.allclose(v[f,1], depth) for f in mesh['faces'])


@pytest.mark.parametrize('changes', [dict(thickness_m=0), dict(thickness_m=float('nan')),
    dict(units='mm'), dict(source_refs=[]), dict(outward_normals=[[0,-2,0]]),
    dict(faces=[[0,1,2,2]]), dict(faces=[[0,1,2,3],[0,1,2,3]],
        outward_normals=[[0,-1,0]]*2,source_refs=['a','b'])])
def test_invalid_source_is_rejected(changes):
    with pytest.raises(ValueError):
        shell(**changes)


def test_inward_corner_miter():
    result = shell(vertices=[[0,0,0],[2,0,0],[2,0,3],[0,0,3],[2,2,0],[2,2,3]],
                   faces=[[0,1,2,3],[1,4,5,2]], outward_normals=[[0,-1,0],[1,0,0]],
                   source_refs=['south','east'])
    assert any(np.allclose(v, [1.6,.4,0]) for v in result['mesh']['vertices'])


def test_shared_edge_gets_no_internal_rim_and_inputs_are_unchanged():
    vertices = np.array([[0,0,0],[1,0,0],[2,0,0],[0,0,1],[1,0,1],[2,0,1]], dtype=float)
    faces = np.array([[0,1,4,3],[1,2,5,4]], dtype=int)
    vertices_before, faces_before = vertices.copy(), faces.copy()
    result = shell(vertices=vertices, faces=faces, outward_normals=[[0,-1,0]]*2,
                   source_refs=['left','right'])
    assert len(result['mesh']['faces']) == 8  # 2 exterior + 6 boundary rims
    assert [source['role'] for source in result['face_sources']].count('rim') == 6
    assert np.array_equal(vertices, vertices_before)
    assert np.array_equal(faces, faces_before)


@pytest.mark.parametrize('changes', [dict(name=''),
    dict(vertices=[[0,0,0],[2,0,0],[2,.1,3],[0,0,3]]),
    dict(outward_normals=[[1,1,0]])])
def test_unsupported_geometry_is_rejected(changes):
    with pytest.raises(ValueError):
        shell(**changes)

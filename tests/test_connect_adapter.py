import pytest

np = pytest.importorskip('numpy')
from dt_ai.geometry.connect import connect_quads


@pytest.mark.parametrize('limit', [0, -1, float('nan'), float('inf')])
def test_rejects_invalid_physical_limit(limit):
    with pytest.raises(ValueError, match='max_side_m'):
        connect_quads([], [], max_side_m=limit)


def test_parent_mapping_preserves_manual_material_decisions():
    vertices = [[0, 0, 0], [8, 0, 0], [8, 1, 0], [0, 1, 0],
                [8, 2, 0], [0, 2, 0]]
    faces = [[0, 1, 2, 3], [3, 2, 4, 5]]
    decisions = ['approved-grey', 'unresolved-ID0']
    v, f, parents = connect_quads(vertices, faces, max_side_m=3.9)
    assert [decisions[i] for i in parents] == ['approved-grey'] * 3 + ['unresolved-ID0'] * 3
    assert f.shape == (6, 4)
    assert np.max(np.linalg.norm(v[f] - np.roll(v[f], 1, axis=1), axis=2)) < 4
    assert faces == [[0, 1, 2, 3], [3, 2, 4, 5]]


@pytest.mark.parametrize('faces', [[[0, 1, 2]], [[0, 1, 2, 8]],
                                    [[0, 1, 2, -1]], [[0, 1, 2, 2]],
                                    [[0., 1., 2., 3.]]])
def test_rejects_invalid_face_contract(faces):
    with pytest.raises(ValueError):
        connect_quads([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
                      faces, max_side_m=3.9)

@pytest.mark.parametrize('vertices', [[], [[0, 0]], [[0, 0, float('nan')]],
                                      [[0, float('inf'), 0]]])
def test_rejects_invalid_coordinates(vertices):
    with pytest.raises(ValueError, match='vertices'):
        connect_quads(vertices, [[0, 1, 2, 3]], max_side_m=1)


def test_shared_edges_are_conforming_and_winding_is_preserved():
    v = np.array([[0., 0, 0], [8, 0, 0], [6, 1, 0], [0, 1, 0],
                  [8, 2, 0], [0, 2, 0]])
    f = np.array([[0, 1, 2, 3], [3, 2, 4, 5]])
    before_v, before_f = v.copy(), f.copy()
    out, faces, parents = connect_quads(v, f, max_side_m=3)
    np.testing.assert_array_equal(v, before_v)
    np.testing.assert_array_equal(f, before_f)
    assert len(parents) == len(faces)
    edge_uses = {}
    for face in faces:
        q = out[face]
        assert np.cross(q[1] - q[0], q[3] - q[0])[2] > 0
        for a, b in zip(face, np.roll(face, -1)):
            key = tuple(sorted((int(a), int(b))))
            edge_uses[key] = edge_uses.get(key, 0) + 1
            edge = out[b] - out[a]
            t = (out - out[a]) @ edge / (edge @ edge)
            on_line = np.linalg.norm(out - (out[a] + t[:, None] * edge), axis=1) < 1e-9
            assert not np.any(on_line & (t > 1e-9) & (t < 1 - 1e-9))
    shared = [uses for (a, b), uses in edge_uses.items()
              if abs(out[a, 1] - 1) < 1e-9 and abs(out[b, 1] - 1) < 1e-9]
    assert len(shared) == 3
    assert shared == [2, 2, 2]

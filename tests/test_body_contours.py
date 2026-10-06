"""Synthetic geometry regression: openings, shared quad edges, fail-closed scope."""
import importlib.util
from pathlib import Path

import pytest

np = pytest.importorskip('numpy')
pytest.importorskip('shapely')


def load_tool(name):
    path = Path(__file__).parents[1] / 'tools' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_wall():
    axes = [np.array([0., 1., 2., 4.]), np.array([0., .2]), np.array([0., 1., 2., 3.])]
    occupied = np.ones((3, 1, 3), dtype=bool)
    occupied[1, 0, 1] = False  # A measured opening through the whole wall thickness.
    vertices, faces, index = [], [], {}
    for cell in np.argwhere(occupied):
        for axis in range(3):
            for sign in (-1, 1):
                neighbour = cell.copy()
                neighbour[axis] += sign
                if (neighbour >= 0).all() and (neighbour < occupied.shape).all() and occupied[tuple(neighbour)]:
                    continue
                origin = cell.copy()
                if sign > 0:
                    origin[axis] += 1
                corners = []
                u, v = (axis+1) % 3, (axis+2) % 3
                for du, dv in [(0, 0), (1, 0), (1, 1), (0, 1)]:
                    q = origin.copy()
                    q[u] += du
                    q[v] += dv
                    xyz = tuple(axes[a][q[a]] for a in range(3))
                    if xyz not in index:
                        index[xyz] = len(vertices)
                        vertices.append(xyz)
                    corners.append(index[xyz])
                faces.append(corners if sign > 0 else corners[::-1])
    triangles = [t for f in faces for t in [[f[0], f[1], f[2]], [f[0], f[2], f[3]]]]
    return {'local_to_revit_internal_m': 'synthetic-test-only', 'items': [{
        'name': 'SYNTHETIC_wall_with_opening', 'group': '02_Стены',
        'props': {'revit_element_id': '4242'}, 'vertices': vertices,
        'faces': faces, 'triangles': triangles,
    }]}


def test_contour_reconstruction_preserves_opening_in_both_directions(tmp_path):
    builder = load_tool('build_floor_body_contours')
    builder.rebuild_body(synthetic_wall(), tmp_path)
    x = np.load(tmp_path/'body-grid.npz')['owner']
    assert x.shape == (3, 1, 3)
    assert not x[1, 0, 1]
    assert np.count_nonzero(x) == 8
    builder.rebuild_body(synthetic_wall(), tmp_path, crosscheck_y=True)
    y = np.load(tmp_path/'body-grid.npz')['owner']
    assert np.array_equal(x, y.transpose(1, 0, 2))


@pytest.mark.parametrize('structured', [False, True])
def test_compact_quads_keep_shared_boundary_and_opening(tmp_path, structured):
    load_tool('build_floor_body_contours').rebuild_body(synthetic_wall(), tmp_path)
    load_tool('compact_floor_body').compact(tmp_path, structured=structured)
    data = np.load(tmp_path/('body-structured-mesh.npz' if structured else 'body-compact-mesh.npz'))
    v, f = data['vertices'], data['faces']
    assert f.shape[1] == 4
    assert len(v) == len(np.unique(v, axis=0))
    edges = np.stack([f, np.roll(f, -1, axis=1)], axis=2).reshape(-1, 2)
    _, count = np.unique(np.sort(edges, axis=1), axis=0, return_counts=True)
    assert (count == 2).all()  # No cracks/T-junctions at opening reveals.
    assert np.array_equal(v.min(axis=0), [0., 0., 0.])
    assert np.allclose(v.max(axis=0), [4., .2, 3.], rtol=0, atol=1e-12)
    # A through-hole must remain: a vertical face across its centre would close it.
    from shapely.geometry import Point, Polygon
    for q in v[f]:
        if np.ptp(q[:, 1]) < 1e-10:
            assert not Polygon(q[:, [0, 2]]).contains(Point(1.5, 1.5))
    assert (data['source_indices'] == 1).all()


def test_nonorthogonal_wall_is_rejected_without_flattening(tmp_path):
    source = synthetic_wall()
    v = np.array(source['items'][0]['vertices'])
    v[:, 0] += .05*v[:, 1]  # Slant across thickness is actual geometry, not float noise.
    source['items'][0]['vertices'] = v.tolist()
    with pytest.raises(ValueError, match='Non-orthogonal'):
        load_tool('build_floor_body_contours').rebuild_body(source, tmp_path)

"""Synthetic regression fixtures; no real-object delivery acceptance."""
import numpy as np
import pytest
from technical_library.mesh_audit.core import inspect_mesh
from technical_library.texture_tiles.cli import build, draw, validate
from tools.facades_texture_pattern import raster


def test_mesh_material_interface_and_loose_component():
    result = inspect_mesh([(0,0,0),(1,0,0),(1,1,0),(0,1,0),(3,0,0),(4,0,0)],
                          [(0,1,2),(0,2,3)], [(4,5)], [1,2])
    assert result['boundary_edges'] == 4
    assert result['material_interface_edges'] == 1
    assert result['connected_components'] == 2
    assert result['loose_edges'] == 1
    assert result['vertices_unused_by_faces'] == 2
    assert result['triangles'] == 2
    assert result['delivery_passed'] is False


def test_mesh_duplicates_and_degeneracy_are_separate():
    result = inspect_mesh([(0,0,0),(1,0,0),(2,0,0),(0,0,0)], [(0,1,2),(2,1,0)])
    assert result['duplicate_vertices_rounded'] == 1
    assert result['duplicate_faces_by_vertex_set'] == 1
    assert result['zero_area_faces_fan'] == 2


@pytest.mark.parametrize('vertices,faces,edges,materials', [
    ([(float('nan'),0,0)],[],[],None),
    ([(0,0,0)],[(0,1,2)],[],None),
    ([(0,0,0)],[],[(0,2)],None),
    ([(0,0,0)],[],[],[1]),
])
def test_mesh_invalid_inputs(vertices,faces,edges,materials):
    with pytest.raises(ValueError):
        inspect_mesh(vertices,faces,edges,materials)


def tile(**changes):
    return dict(id=1,udim=1001,rgb=[120,150,180],size=[16,16],kind='solid',**changes)


def test_tile_archive_readback_and_no_overwrite(tmp_path):
    config = {'tiles':[tile()]}
    result = build(config,tmp_path/'new')
    assert result['archive_readback_equal']
    assert result['tiles'][0]['solid']
    assert result['delivery_passed'] is False
    with pytest.raises(FileExistsError):
        build(config,tmp_path/'new')


def test_tile_rejects_duplicate_and_non_numeric_filenames():
    with pytest.raises(ValueError):
        validate({'tiles':[tile(),tile()]})
    candidate = tile(); candidate['udim'] = '../input'
    with pytest.raises(ValueError):
        validate({'tiles':[candidate]})


def test_metric_tile_reuses_canonical_raster():
    candidate = tile(); candidate.update(kind='metric_pattern',pattern_id=102,extent_m=[1.2,1.6])
    expected = raster(102,16,16,[1.2,1.6],np.array(candidate['rgb'])/255)
    expected = np.rint(np.clip(expected,0,1)*255).astype(np.uint8)
    assert np.array_equal(np.asarray(draw(candidate)),expected)
    candidate['extent_m'] = [0,1]
    with pytest.raises(ValueError):
        validate({'tiles':[candidate]})

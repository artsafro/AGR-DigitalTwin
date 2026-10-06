import importlib.util
from pathlib import Path

import pytest
pytest.importorskip('numpy')


def packer(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]/'tools'))
    spec=importlib.util.spec_from_file_location('prepare_uv',Path(__file__).parents[1]/'tools/prepare_floor_uv.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.pack


def test_padding_and_sequential_udim_packing(monkeypatch):
    boxes=packer(monkeypatch)([(3.,3.)]*12,2048,16,512.)
    assert sorted({b['tile'] for b in boxes.values()})==list(range(12))
    for box in boxes.values():
        assert box['x']>=16 and box['y']>=16
        assert box['x']+box['width']<=2048-16
        assert box['y']+box['height']<=2048-16
        assert box['density']==512
    assert packer(monkeypatch)([(3.,3.)]*2,2048,16,512.,True) is None


def test_oversized_face_has_explicit_density_exception_not_cross_tile_uv(monkeypatch):
    box=packer(monkeypatch)([(12.,1.)],4096,32,512.)[0]
    assert box['density']<512
    assert box['x']+box['width']<=4096-32


def test_connect_propagates_to_shared_edge_without_t_junction(monkeypatch):
    import numpy as np
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]/'tools'))
    from quad_connect import subdivide
    # Long face above a tapered neighbour: subdivisions must agree on the shared edge.
    vertices=[[0,0,0],[12,0,0],[12,1,0],[0,1,0],[9,2,0],[3,2,0]]
    v,f,parents=subdivide(vertices,[[0,1,2,3],[3,2,4,5]],3.9)
    assert len(f)==8 and set(parents)=={0,1}
    edges=np.sort(np.stack([f,np.roll(f,1,axis=1)],axis=2).reshape(-1,2),axis=1)
    unique,counts=np.unique(edges,axis=0,return_counts=True)
    for edge,count in zip(unique,counts):
        if np.allclose(v[edge,1],1):assert count==2
    assert np.max(np.linalg.norm(v[f]-np.roll(v[f],1,axis=1),axis=2))<4

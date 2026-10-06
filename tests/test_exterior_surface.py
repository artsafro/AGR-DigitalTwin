"""Synthetic risk cases: internal walls must not become facade cuts or faces."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest
np=pytest.importorskip('numpy')
shapely=pytest.importorskip('shapely')


def load_tool(monkeypatch):
    directory=Path(__file__).parents[1]/'tools'
    monkeypatch.syspath_prepend(str(directory))
    spec=importlib.util.spec_from_file_location('exterior_builder',directory/'build_exterior_surface.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_interior_partition_does_not_create_facade_cuts_and_window_stays_empty(tmp_path,monkeypatch):
    module=load_tool(monkeypatch)
    x=np.array([0,.2,1,2,2.3,2.5,3.8,4.])
    y=np.array([0,.2,1.,1.8,2.])
    z=np.array([0,.3,.8,1.2,2.55,2.9])
    owner=np.zeros((len(x)-1,len(y)-1,len(z)-1),dtype=np.int32)
    owner[0,:,:]=1;owner[-1,:,:]=1;owner[:,0,:]=1;owner[:,-1,:]=1
    owner[4,:,:]=2  # Internal wall; x=2.3 and 2.5 must not cut the facade.
    owner[2,0,2:4]=0  # Measured opening x=1..2, z=.8..2.55.
    np.savez(tmp_path/'body-grid.npz',owner=owner,x=x,y=y,z=z,angle=0.)
    (tmp_path/'floor-selection.json').write_text(json.dumps({'nextLevelElevationMeters':3.,'levelElevationMeters':0.}))
    (tmp_path/'contour-source.json').write_text('{"items":[]}')
    module.build(tmp_path)
    report=json.loads((tmp_path/'exterior-surface.json').read_text())
    data=np.load(tmp_path/'exterior-surface.npz')
    assert report['facade_runs']==4
    assert report['z_cuts_m']==[0.,.8,2.55,3.]
    assert sum(r['closed_openings'] for r in report['profiles'])==1
    for run in report['profiles']:
        assert 2.3 not in run['u_cuts_m'] and 2.5 not in run['u_cuts_m']
    for q in data['vertices'][data['faces']]:
        assert any(np.allclose(q[:,axis],value) for axis,value in [(0,0),(0,4),(1,0),(1,2)])
        assert len(q)==4
        if np.allclose(q[:,1],0):
            assert shapely.Polygon(q[:,[0,2]]).intersection(shapely.box(1,.8,2,2.55)).area<1e-10


def test_coordinate_normalization_preserves_real_steps(monkeypatch):
    module=load_tool(monkeypatch)
    coordinates=[(0,0),(2,0),(2,1),(1.0004,1),(1.0004,1.05),(1,1.05),(1,2),(0,2),(0,0)]
    original=shapely.Polygon(coordinates)
    normalized=module.clean_ring(coordinates)
    assert normalized.is_valid
    assert shapely.hausdorff_distance(original.boundary,normalized.boundary)<.001
    mapping=module.clustered([0,.0008,.0016,.05])
    assert mapping[0]==mapping[.0008]
    assert mapping[.0016]!=mapping[0]  # No unbounded transitive merge.
    assert mapping[.05]==.05

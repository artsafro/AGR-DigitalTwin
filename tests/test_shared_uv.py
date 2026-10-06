"""Shared UVs must preserve physical scale, phase, orientation and region boundaries."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('shared_uv',Path(__file__).parents[1]/'tools/prepare_floor_shared_uv.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


@pytest.mark.parametrize('ident,period',[(2,.605),(4,.605),(5,.260)])
@pytest.mark.parametrize('variant',['NPM_ATLAS','VPM_UDIM'])
def test_repeated_faces_stack_without_scale_change(ident,period,variant):
    q=np.array([[.13,0,.2],[1.13,0,.2],[1.13,0,1.4],[.13,0,1.4]])
    uv,_,density=module.map_face(q,ident,variant)
    other=q.copy();other[:,0]+=period*10
    uv2,_,_=module.map_face(other,ident,variant)
    assert np.allclose(uv,uv2,atol=1e-12)
    size=4096 if variant=='VPM_UDIM' else 2048
    assert np.linalg.norm(np.array(uv)[1]-uv[0])*size==pytest.approx(density)


def test_long_horizontal_rim_uses_atlas_width():
    q=np.array([[0,0,3],[.4,0,3],[.4,15,3],[0,15,3]])
    uv,region,_=module.map_face(q,2,'NPM_ATLAS')
    assert np.ptp(uv,axis=0)[0]>np.ptp(uv,axis=0)[1]
    assert np.max(np.array(uv)[:,1])*2048 < region[3]-8


def test_large_face_requires_cut_instead_of_density_loss():
    q=np.array([[0,0,0],[5,0,0],[5,0,3],[0,0,3]])
    with pytest.raises(AssertionError):module.map_face(q,4,'VPM_UDIM')


@pytest.mark.parametrize('ident,w,h,joint',[(2,.6,1.2,.005),(4,.6,1.2,.005),(3,.6,1.2,.005),(5,.25,.065,.01)])
def test_rebaked_physical_joint_width(ident,w,h,joint):
    source=np.full((160,160,3),200.,dtype=float)
    source[50,19]=40;source[50,23]=40;source[50,26]=40
    step=.0001
    x=np.arange(0,w+joint,step)+step/2
    rgb=module.shade(x,np.full_like(x,.03),ident,source)
    mortar=np.max(rgb,axis=-1)<100
    assert mortar.sum()*step==pytest.approx(joint,abs=step)
    assert (~mortar).sum()*step==pytest.approx(w,abs=step)

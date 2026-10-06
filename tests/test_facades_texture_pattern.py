import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('facades_pattern',Path(__file__).parents[1]/'tools/facades_texture_pattern.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.mark.parametrize('mid',range(101,106))
def test_full_4800mm_repeat_and_dark_edges(mid):
    x=np.array([[.0001,.137,.99,2.35,4.7999]])
    y=np.array([[.0001],[.212],[1.43],[4.7999]])
    a=module.pattern(mid,x,y,[.6,.48,.38])
    np.testing.assert_allclose(a,module.pattern(mid,x+4.8,y+4.8,[.6,.48,.38]),atol=1e-9)
    np.testing.assert_allclose(a[0],a[-1])
    np.testing.assert_allclose(a[:,0],a[:,-1])

def test_brick_panel_horizontal_joint_distinct_from_mortar():
    color=[.6,.48,.38]
    joint=module.pattern(101,np.array([[.04]]),np.array([[1.2]]),color)
    mortar=module.pattern(101,np.array([[.04]]),np.array([[.076]]),color)
    assert np.max(joint)<np.min(mortar)*.2

@pytest.mark.parametrize('mid',range(101,106))
def test_updated_600_1200_modules(mid):
    dims=(1.2,.6) if mid==101 else (.6,1.2)
    x=np.array([[.137,.333,.571]]);y=np.array([[.111],[.213]])
    color=[.6,.48,.38]
    a=module.pattern(mid,x,y,color,panel_dimensions=dims)
    np.testing.assert_allclose(a,module.pattern(mid,x+dims[0],y+dims[1],color,panel_dimensions=dims),atol=1e-9)


@pytest.mark.parametrize('mid', [101, 102])
def test_raster_periodicity_with_offset_and_row_blocks(mid):
    dims = (1.2, .6) if mid == 101 else (.6, 1.2)
    args = dict(mid=mid, width=7, height=65, extent=(.7, .65),
                color=[.6, .48, .38], panel_dimensions=dims)
    a = module.raster(**args, offset=(-.123, -.213))
    b = module.raster(**args, offset=(-.123 + dims[0], -.213 + dims[1]))
    assert a.shape == (65, 7, 3)
    assert a.dtype == np.float32
    assert np.isfinite(a).all()
    assert 0 <= a.min() <= a.max() <= 1
    np.testing.assert_allclose(a, b, atol=2e-7)
    # Read the last row as a separate image with matching physical origin.
    last = module.raster(mid, 7, 1, (.7, .01), [.6, .48, .38],
                         offset=(-.123, -.213 + .64), panel_dimensions=dims)
    np.testing.assert_allclose(a[64:], last, atol=2e-7)


def test_raster_solid_panel_without_joint_preserves_color():
    color = [.6, .48, .38]
    result = module.raster(102, 9, 3, (.6, 1.2), color, joint=0,
                           panel_dimensions=(.6, 1.2))
    np.testing.assert_allclose(result, np.broadcast_to(color, result.shape), atol=2e-7)

"""Physical joint widths and phase reconstruction protect the facade bake."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('texture_floor', Path(__file__).parents[1]/'tools/texture_floor.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('ident,width,height,joint', [(2,.6,1.2,.005),(4,.6,1.2,.005),(5,.25,.065,.01)])
def test_measured_face_and_mortar_width(ident, width, height, joint):
    # Scan one physical module at 0.1 mm resolution, far from a horizontal seam.
    step = .0001
    x = np.arange(0, width+joint, step)+step/2
    rgb = module.pattern(x, np.full_like(x, joint+height/2), ident)
    mortar = np.max(rgb, axis=-1) < (130 if ident == 5 else 180 if ident == 2 else 80)
    assert mortar.sum()*step == pytest.approx(joint, abs=step)
    assert (~mortar).sum()*step == pytest.approx(width, abs=step)
    y = np.arange(0, height+joint, step)+step/2
    rgb = module.pattern(np.full_like(y, joint+width/2), y, ident)
    mortar = np.max(rgb, axis=-1) < (130 if ident == 5 else 180 if ident == 2 else 80)
    assert mortar.sum()*step == pytest.approx(joint, abs=step)


def test_running_bond_half_offset():
    assert np.max(module.pattern(np.array(.005), np.array(.04), 5)) < 130
    assert np.max(module.pattern(np.array(.005), np.array(.115), 5)) > 130
    assert np.max(module.pattern(np.array(.135), np.array(.115), 5)) < 130


@pytest.mark.parametrize('reverse', [False, True])
def test_adjacent_faces_keep_metric_coordinates_after_uv_origin_reset(reverse):
    for start, end in [(-2.73, -.38), (-.38, 1.43)]:
        q = np.array([[start,3.,.21],[end,3.,.21],[end,3.,2.9],[start,3.,2.9]])
        if reverse:
            q = q[::-1]
        axes, sign, minimum = module.projection(q)
        uv = q[:, axes].copy()
        uv[:,0] *= sign
        uv -= uv.min(0)
        reconstructed = uv + minimum
        reconstructed[:,0] *= sign
        assert np.max(abs(reconstructed-q[:,axes])) < 1e-12

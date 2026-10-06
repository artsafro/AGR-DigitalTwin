"""UDIM / mirroring / density. Ported from AGR tests/integration/test_pipeline.py
(sha256 42064d134594) test_udim_row_transition_and_mirroring on 2026-10-06; changes: split
by failure reason, density limits read from VPM_STANDARD.yaml."""
import pytest

from twinqa.profiles import load_profiles
from twinqa.uv import edge_densities, face_issue, sequential_tiles, tile_origin, tile_quad, udim_of, validate_uv


def test_udim_row_transition_and_mirroring():
    assert tile_origin(1010) == (9, 0)
    assert tile_origin(1011) == (0, 1)
    assert tile_origin(1100) == (9, 9)
    uv = tile_quad(1011, 2048, 16)
    assert validate_uv(uv, 1011, 2048, 16)
    assert udim_of(uv) == 1011
    assert face_issue(list(reversed(uv)), 1011, 2048, 16) == "mirrored"
    uv[0][0] = -0.1
    assert face_issue(uv, 1011, 2048, 16) == "cross_tile"
    with pytest.raises(ValueError):
        tile_origin(1101)
    with pytest.raises(ValueError):
        tile_origin(1000)


def test_margin_is_separate_from_cross_tile():
    uv = tile_quad(1001, 2048, 0)  # touches the border but stays inside the tile
    assert face_issue(uv, 1001, 2048, 16) == "margin"
    assert face_issue(uv, 1001, 2048, 0) is None


def test_sequential_tiles():
    assert sequential_tiles([1001, 1002, 1003])
    assert sequential_tiles([1003, 1001, 1002, 1002])
    assert not sequential_tiles([1001, 1010])
    assert not sequential_tiles([1002])


@pytest.mark.parametrize("side_m,size,ok", [(4.0, 4096, True), (7.9, 4096, True), (8.1, 4096, False),
                                             (1.21, 2048, True), (1.19, 2048, False)])
def test_density_limits_from_profile(side_m, size, ok):
    limits = load_profiles().vpm["uv"]["diffuse_density_px_per_m"]  # 512..1706 px/m, reg p.32 §6.2
    square = [[0, 0, 0], [side_m, 0, 0], [side_m, 0, side_m], [0, 0, side_m]]
    uv = [[0, 0], [1, 0], [1, 1], [0, 1]]
    values = edge_densities(square, uv, size)
    assert all(limits["min"] <= d <= limits["max"] for d in values) == ok

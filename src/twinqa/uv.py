# Ported from AGR src/dt_ai/geometry/uv.py (sha256 259a15fe300c) on 2026-10-06;
# changes: tile range and density limits come from VPM_STANDARD.yaml, added
# udim_of()/face_issue() so a failure says why (mirrored / cross-tile / margin),
# added sequential_tiles(). tile_origin/tile_quad/signed_area/edge_densities unchanged.
"""UDIM tiles, mirrored islands, tile margins and texel density (VPM, reg p.31-32, 39)."""
import math

# UDIM = 1001 + U + 10 * V on a 10 x 10 grid (reg p.23, p.31 §2.1.3, p.39;
# VPM_STANDARD.yaml uv.udim_grid; figure typo on p.39 is conflict #9, text wins).
FIRST_TILE, LAST_TILE = 1001, 1100
EPS = 1e-6


def tile_origin(tile: int):
    if type(tile) is not int or not FIRST_TILE <= tile <= LAST_TILE:
        raise ValueError("UDIM must be 1001..1100")
    return (tile - 1001) % 10, (tile - 1001) // 10


def tile_quad(tile: int, size: int, padding: int):
    u, v = tile_origin(tile)
    p = padding / size
    return [[u + p, v + p], [u + 1 - p, v + p],
            [u + 1 - p, v + 1 - p], [u + p, v + 1 - p]]


def signed_area(uv):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(uv, uv[1:] + uv[:1])) / 2


def udim_of(uv) -> int | None:
    """Tile of the face centroid, or None when it lies outside the 10 x 10 grid."""
    cu = sum(p[0] for p in uv) / len(uv)
    cv = sum(p[1] for p in uv) / len(uv)
    u, v = math.floor(cu), math.floor(cv)
    return 1001 + u + 10 * v if 0 <= u <= 9 and 0 <= v <= 9 else None


def face_issue(uv, tile, size, padding):
    """None if the face is valid in `tile`; otherwise 'invalid', 'mirrored', 'cross_tile' or 'margin'.

    mirrored: UV winding opposite to the polygon winding (reg p.31 §2.1.4 forbids mirrored islands).
    cross_tile: a vertex leaves the tile (geometry must be split, reg p.31 §2.1.2).
    margin: inside the tile but closer to its border than `padding` px; the regulation asks for
    a margin (reg p.31 §2.1.5) without a size, so the caller reports this as review.
    """
    if len(uv) < 3 or not all(len(x) == 2 and all(math.isfinite(c) for c in x) for x in uv):
        return "invalid"
    area = signed_area(uv)
    if abs(area) <= 1e-12:
        return "invalid"
    if area < 0:
        return "mirrored"
    u, v = tile_origin(tile)
    if not all(u - EPS <= x <= u + 1 + EPS and v - EPS <= y <= v + 1 + EPS for x, y in uv):
        return "cross_tile"
    p = padding / size
    if not all(u + p - EPS <= x <= u + 1 - p + EPS and v + p - EPS <= y <= v + 1 - p + EPS for x, y in uv):
        return "margin"
    return None


def validate_uv(uv, tile, size, padding):
    return face_issue(uv, tile, size, padding) is None


def sequential_tiles(tiles) -> bool:
    """Tiles filled from 1001 without gaps (reg p.31 §2.1.3)."""
    ordered = sorted(set(tiles))
    return ordered == list(range(FIRST_TILE, FIRST_TILE + len(ordered))) and (not ordered or ordered[-1] <= LAST_TILE)


def edge_densities(vertices, uv, size):
    """px/m per polygon edge: texture_side_px * |duv| / |dxyz| (reg p.32 §6.2, division per conflict #10)."""
    result = []
    for i in range(len(vertices)):
        j = (i + 1) % len(vertices)
        world = math.dist(vertices[i], vertices[j])
        if world <= 1e-9:
            raise ValueError("Degenerate surface edge")
        result.append(size * math.dist(uv[i], uv[j]) / world)
    return result

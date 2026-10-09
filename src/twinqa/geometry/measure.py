"""Measures of a triangle soup: bounding box, outer area of a horizontal section, silhouettes."""
import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import polygonize

GRID_M = 1e-5          # section points are snapped to this grid so neighbouring segments meet
VERTEX_CLEAR_M = 1e-4  # a cut this close to a vertex height is moved up by this much
AREA_MIN_M2 = 1e-10    # projected triangles smaller than this are edge-on and add nothing

# silhouette views: the two plan axes kept by each projection. Front and back (and left and right)
# orthographic silhouettes are mirror images, so three projections cover the 4 sides + top of §5.
VIEWS = {"x": (1, 2), "y": (0, 2), "top": (0, 1)}


def bbox(corners: np.ndarray) -> np.ndarray:
    """(2, 3) min and max over all triangle corners."""
    pts = corners.reshape(-1, 3)
    return np.stack([pts.min(0), pts.max(0)])


def section_area(corners: np.ndarray, z: float) -> float | None:
    """Area inside the outer ring of the largest closed section shape at height z; None if no ring closes."""
    if np.any(np.abs(corners[:, :, 2] - z) < VERTEX_CLEAR_M):
        z += VERTEX_CLEAR_M
    d = corners[:, :, 2] - z
    crossing = (d.min(1) < 0) & (d.max(1) > 0)
    segments = []
    for tri, dist in zip(corners[crossing], d[crossing]):
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if (dist[i] < 0) != (dist[j] < 0):
                s = dist[i] / (dist[i] - dist[j])
                pts.append(tri[i, :2] + s * (tri[j, :2] - tri[i, :2]))
        segments.append(np.round(pts, 5))
    if not segments:
        return None
    lines = shapely.set_precision(shapely.linestrings(np.asarray(segments)), GRID_M)
    noded = shapely.union_all(lines[~shapely.is_empty(lines)])
    shapes = list(polygonize(shapely.get_parts(noded)))
    if not shapes:
        return None
    return float(max(Polygon(p.exterior).area for p in shapes))


def silhouette(corners: np.ndarray, view: str, grid_m: float = 1e-4):
    """Union of all triangles projected along one axis (view in VIEWS)."""
    a, b = VIEWS[view]
    flat = corners[:, :, [a, b]]
    e1, e2 = flat[:, 1] - flat[:, 0], flat[:, 2] - flat[:, 0]
    keep = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) / 2 > AREA_MIN_M2
    polys = shapely.polygons(flat[keep])
    return shapely.union_all(polys, grid_size=grid_m)


def iou(a, b) -> float:
    union = shapely.union(a, b).area
    return float(shapely.intersection(a, b).area / union) if union > 0 else 1.0

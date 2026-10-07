"""UCX collision hulls for the KPP1 VPM model (reg p.36-37 §13; docs/domain/geometry.md).

Every piece is the convex hull of explicit points (closed, convex, triangulated, no material slots),
named UCX_SM_<Address>_Main_NNN. Pieces keep a GAP (2 mm, inside the recommended 0.2-10 mm) from each
other, so none intersect or touch. Coverage / tolerance choices (reg p.36 §13.2, §13.5):
- body box up to the roof membrane, parapet ring up to the cap (8.68), shaft and hood on the roof;
- entrance canopies, portal piers and porches (pedestrian zone, <= 30 cm): one box each;
- east steel stair: flights as sloped slabs, landing and +3.9 platform as boxes;
- not built: window surrounds/fins (9 cm), aerators, railings and ladder (< 5 cm members, §13.2),
  blind area (ground level, covered by the Ground collision).
"""
import itertools
import bmesh
from mathutils import Vector

GAP = 0.002


def hull(points):
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p)) for p in points]
    res = bmesh.ops.convex_hull(bm, input=vs)
    bmesh.ops.delete(bm, geom=[v for v in res["geom_interior"] if isinstance(v, bmesh.types.BMVert)], context="VERTS")
    bmesh.ops.delete(bm, geom=[g for g in res["geom_unused"] if isinstance(g, bmesh.types.BMVert)], context="VERTS")
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def box(x0, x1, y0, y1, z0, z1):
    return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def clip_outside(r, foot):
    """Pull a plan rect [x0, x1, y0, y1] that runs into the building back to GAP outside the facade."""
    X0, X1, Y0, Y1 = foot
    x0, x1, y0, y1 = r
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if cy < Y0:
        y1 = min(y1, Y0 - GAP)
    elif cy > Y1:
        y0 = max(y0, Y1 + GAP)
    elif cx < X0:
        x1 = min(x1, X0 - GAP)
    elif cx > X1:
        x0 = max(x0, X1 + GAP)
    return [x0, x1, y0, y1]


def pieces(foot, roof_z, parapet_in, cap_top, shaft, hood, canopies, piers, porches):
    """Return a list of (label, point list)."""
    X0, X1, Y0, Y1 = foot
    out = [("body", box(X0, X1, Y0, Y1, -1.2, roof_z))]
    z0 = roof_z + GAP
    pi0, pi1 = Y0 + parapet_in, Y1 - parapet_in
    out += [("parapet_S", box(X0, X1, Y0, pi0, z0, cap_top)),
            ("parapet_N", box(X0, X1, pi1, Y1, z0, cap_top)),
            ("parapet_W", box(X0, X0 + parapet_in, pi0 + GAP, pi1 - GAP, z0, cap_top)),
            ("parapet_E", box(X1 - parapet_in, X1, pi0 + GAP, pi1 - GAP, z0, cap_top))]
    sx0, sx1, sy0, sy1, st = shaft
    hx0, hx1, hy0, hy1, _, _, hz = hood
    out += [("shaft", box(sx0, sx1, sy0, sy1, z0, st)), ("hood", box(hx0, hx1, hy0, hy1, st + GAP, hz))]
    porch_top = {}
    for k, (r, top) in enumerate(porches):
        c = clip_outside(r, foot)
        out.append((f"porch_{k}", box(c[0], c[1], c[2], c[3], -0.6, top)))
        porch_top[k] = (c, top)

    def base_under(c):
        tops = [t for (pc, t) in porch_top.values() if pc[0] - 1e-6 <= c[0] and c[1] <= pc[1] + 1e-6
                and pc[2] - 1e-6 <= c[2] and c[3] <= pc[3] + 1e-6]
        return (max(tops) if tops else -0.1) + GAP
    for k, r in enumerate(piers):
        c = clip_outside(r, foot)
        out.append((f"pier_{k}", box(c[0], c[1], c[2], c[3], base_under(c), 2.70 - GAP)))
    for k, (r, z_lo, z_hi) in enumerate(canopies):
        c = clip_outside(r, foot)
        out.append((f"canopy_{k}", box(c[0], c[1], c[2], c[3], z_lo, z_hi)))
    # east steel stair (Revit stringers: lower flight x 28.83..31.33 y 2.32..3.68, slope 0.8;
    # landing +2.1 x 27.55..28.83; upper flight y 3.6..5.6 x 27.55..28.91; platform +3.9 to y 8.58)
    t = 0.30
    zl = lambda x: 2.1 - (x - 28.83) * 0.8
    xa, xb = 28.83 + GAP, 31.33
    out.append(("stair_lower", [(x, y, z) for x in (xa, xb) for y in (2.32, 3.68) for z in (zl(x) - t, zl(x))]))
    out.append(("stair_landing", box(27.55, 28.83, 2.32, 3.6 - GAP, 2.1 - t, 2.1)))
    zu = lambda y: 2.1 + (y - 3.6) * 0.9
    ya, yb = 3.68 + GAP, 5.6 - GAP  # starts past the lower flight's north stringer (y 3.6..3.68)
    out.append(("stair_upper", [(x, y, z) for x in (27.55, 28.91) for y in (ya, yb) for z in (zu(y) - t, zu(y))]))
    out.append(("stair_platform", box(X1 + GAP + 0.003, 28.91, 5.6, 8.58, 3.6, 3.9)))
    return out


def convex_closed(bm):
    closed = all(len(e.link_faces) == 2 for e in bm.edges)
    # 0.1 mm: float32 mesh coordinates around 30 m carry ~1e-6 noise
    convex = all((v.co - f.calc_center_median()).dot(f.normal) <= 1e-4 for f in bm.faces for v in bm.verts)
    return closed, convex


def intersect(a, b):
    """Separating-axis test for two convex triangulated hulls (face normals + edge cross products).
    Returns True if they overlap or touch within 1e-6."""
    axes = [f.normal.copy() for f in a.faces] + [f.normal.copy() for f in b.faces]
    ea = [(e.verts[1].co - e.verts[0].co).normalized() for e in a.edges]
    eb = [(e.verts[1].co - e.verts[0].co).normalized() for e in b.edges]
    for u, w in itertools.product(ea, eb):
        c = u.cross(w)
        if c.length > 1e-6:
            axes.append(c.normalized())
    for ax in axes:
        pa = [v.co.dot(ax) for v in a.verts]
        pb = [v.co.dot(ax) for v in b.verts]
        if max(pa) < min(pb) - 1e-6 or max(pb) < min(pa) - 1e-6:
            return False
    return True

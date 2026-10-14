"""Build path by source modules (user 2026-10-13), beside `from_spec`: the model is rebuilt module by module from
the source, the way a modeller does it by hand, and goes through the same checkers against the spec (the spec stays
the contract of the checks; this path does not read it).

Modules come from the job's `modules/modules.json` (confirmed by the user): source groups (an object, or one
material slot of it) with a module name and output ids.

- walls: storey by storey, from the top of the slab below to the underside of the slab above. The storey's wall
  line is the section of the wall and glazing modules at mid storey, its gaps behind the piers closed (a closing
  of WALL_CLOSE_M). Every wall is a grid of quads of its own: columns at its ends and its openings; rows are the
  storey's (its bottom, its top and every opening's sill and head on that storey), so the walls of one storey meet
  at their shared corners without a T-junction. Glazing on a wall is the opening: the glass span (panes closer
  than PANE_GAP_M are one opening), the plane at the opening depth (OD1, 0.4) with reveals.
- slabs and walkable decks: a closed box per slab - its top and underside filled with a grid of quads clipped by
  the outline (Cap -> Quadrify), a cell no quad or triangle can take triangulated (CDT, reported), the edge band
  cut at every fill vertex on the outline. A wall stands on a slab without sharing its vertices (no T-junction by
  construction): its open bottom and top loops are seated on the slab faces.
- decor (pattern facade-decor-inset): one box per element - pieces of one element (same section, one axis, seams
  up to DECOR_SEAM_M) merged; the box is the element's extent, its back set DECOR_INSET_M into the wall.
- planes: modules built as one-sided planes (the roof screen enclosure, decision 2a; textured bands).
- skipped: modules marked so (attachments over 0.8 m - EG2 -, textures with no geometry, interior parts).

Every module is compared with its source module (silhouettes, extent, area) and reported."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.polygon import orient

from dt_ai.geometry.from_spec import BuildError, _Mesh

WALL_CLOSE_M = 0.7       # gaps of the wall line behind a pier up to twice this are closed (OBJ03 piers 1.2 m)
PANE_GAP_M = 0.15        # glass panes closer than this along a wall are one opening (frames between them)
EDGE_TOL_M = 0.15        # glass within this of a wall line belongs to that wall
WALL_END_M = 0.05        # an opening keeps this frame at a wall end (no corner openings)
FILL_STEP_M = 3.0        # the quad grid of a slab's fill
DECOR_SEAM_M = 0.06      # pattern facade-decor-inset: split pieces merged across seams up to this (plate_gap_m x 12)
DECOR_INSET_M = 0.02     # the decor box's back set into the wall
SLAB_LEVEL_TOL_M = 0.25  # a slab belongs to the level its top lies within this of
SIMPLIFY_M = 0.005
ROW_SNAP_M = 0.05        # sills / heads within this are one row of the storey
KEY_M = 1e-6


@dataclass
class Inputs:
    levels: list[tuple[str, float]]       # (name, elevation) from the object's levels; the last is the roof
    opening_depth_m: float = 0.4          # OD1
    opening_id: int = 11
    reveal_id: int = 6
    facade_id: int = 1
    weld_m: float = 0.003


def module_tris(dump: dict, modules: dict) -> dict:
    """{source key: (vertices, triangles, module record)} of every module part, by object or object slot."""
    meshes = {m["name"]: m for m in dump["meshes"]}
    out = {}
    for mod in modules["modules"]:
        for part in mod["parts"]:
            m = meshes[part["object"]]
            v = np.asarray(m["vertices"], float)
            t = np.asarray(m["triangles"], int).reshape(-1, 3)
            if part["slot"] is not None:
                t = t[np.asarray(m["material_ids"]) == part["slot"]]
            out[part["source"]] = (v, t, mod)
    return out


def _section(v, t, z):
    p = v[t]
    d = p[:, :, 2] - z
    cut = (d.min(axis=1) < 0) & (d.max(axis=1) > 0)
    segs = []
    for tri, dist in zip(p[cut], d[cut]):
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if (dist[i] < 0) != (dist[j] < 0):
                s = dist[i] / (dist[i] - dist[j])
                pts.append(tri[i, :2] + s * (tri[j, :2] - tri[i, :2]))
        if len(pts) == 2 and np.hypot(*(pts[0] - pts[1])) > 1e-9:
            segs.append(LineString(np.round(pts, 6)))
    return segs


def _pieces(v, t):
    """Connected pieces (shared vertices) of a triangle set, as triangle-index arrays."""
    par = np.arange(len(v))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for a, b, c in t:
        for x, y in ((a, b), (b, c)):
            rx, ry = find(x), find(y)
            if rx != ry:
                par[rx] = ry
    groups = defaultdict(list)
    for k, tri in enumerate(t):
        groups[find(tri[0])].append(k)
    return [np.asarray(g) for g in groups.values()]


# ---------------------------------------------------------------------------------------------- slabs

def slabs_of(v, t, levels, tol=SLAB_LEVEL_TOL_M):
    """Slabs of a slab module at the levels: (level name, top z, underside z, outline polygon)."""
    p = v[t]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    ln = np.linalg.norm(n, axis=1)
    nz = np.divide(n[:, 2], ln, out=np.zeros(len(n)), where=ln > 0)
    zc = p[:, :, 2].mean(axis=1)
    tops, bottoms = sorted(set(np.round(zc[nz > 0.99], 4))), sorted(set(np.round(zc[nz < -0.99], 4)))
    out = []
    for name, elev in levels:
        cand = [z for z in tops if abs(z - elev) <= tol]
        if not cand:
            continue
        top = min(cand, key=lambda z: abs(z - elev))
        under = max((z for z in bottoms if z < top - KEY_M), default=None)
        faces = [Polygon(q[:, :2]) for q, up, z in zip(p, nz > 0.99, zc) if up and abs(z - top) <= 1e-3]
        outline = shapely.union_all([f.buffer(1e-6) for f in faces if f.area > 0]).buffer(0.0035).buffer(-0.0035)   # parts within the weld are one
        out.append((name, float(top), float(under) if under is not None else None, outline))
    return out


def _fill(poly, step, origin):
    """A polygon's fill: a grid of cells clipped by it; quads where a cell part has four corners, triangles where
    three, the rest triangulated (CDT) - counted. The pieces share their grid vertices (no T-junction inside)."""
    minx, miny, maxx, maxy = poly.bounds
    x0, y0 = origin
    xs = list(np.arange(x0 + np.floor((minx - x0) / step) * step, maxx + step, step))
    ys = list(np.arange(y0 + np.floor((miny - y0) / step) * step, maxy + step, step))
    out, fallback = [], 0
    for xa, xb in zip(xs, xs[1:]):
        for ya, yb in zip(ys, ys[1:]):
            part = poly.intersection(box(xa, ya, xb, yb))
            for g in shapely.get_parts(part):
                if g.geom_type != "Polygon" or g.area <= KEY_M:
                    continue
                g = orient(shapely.set_precision(g, 1e-7), 1.0)
                ring = np.asarray(g.exterior.coords)[:-1]
                if not g.interiors and len(ring) in (3, 4) and g.convex_hull.area - g.area <= 1e-9:
                    out.append(ring)
                    continue
                fallback += 1
                out += [np.asarray(tr.exterior.coords)[:-1]
                        for tr in shapely.get_parts(shapely.constrained_delaunay_triangles(g))]
    return out, fallback


def _outline_cuts(poly, pieces):
    """Every fill vertex on the outline of poly, per outline ring, ordered along it (the edge band's cuts)."""
    pts = np.unique(np.round(np.vstack(pieces), 7), axis=0)
    rings = []
    for ring in [poly.exterior, *poly.interiors]:
        on = [p for p in pts if ring.distance(shapely.Point(p)) <= 1e-6]
        on.sort(key=lambda p: ring.project(shapely.Point(p)))
        rings.append(np.asarray(on))
    return rings


def slab_box(mesh: _Mesh, outline, top, under, top_id, side_id, under_id, step=FILL_STEP_M):
    """A slab as a closed box: top and underside filled, the edge band cut at every fill vertex on the outline."""
    fallback = 0
    for poly in shapely.get_parts(outline):
        poly = orient(poly.simplify(SIMPLIFY_M, preserve_topology=True), 1.0)
        if poly.is_empty or poly.area <= KEY_M:
            continue
        pieces, fb = _fill(poly, step, (poly.bounds[0], poly.bounds[1]))
        fallback += fb
        if not pieces:
            continue
        for q in pieces:
            pts3 = [[*c, top] for c in q]
            (mesh.quad if len(q) == 4 else mesh.tri)(pts3, top_id, [0, 0, 1])
            pts3 = [[*c, under] for c in q]
            (mesh.quad if len(q) == 4 else mesh.tri)(pts3, under_id, [0, 0, -1])
        for ring, cuts in zip([poly.exterior, *poly.interiors], _outline_cuts(poly, pieces)):
            ccw = ring.is_ccw
            for a, b in zip(cuts, np.roll(cuts, -1, axis=0)):
                d = b - a
                out_n = np.array([d[1], -d[0], 0.0]) * (1 if ccw else -1)
                mesh.quad([[*a, under], [*b, under], [*b, top], [*a, top]], side_id, out_n)
    return fallback


# ---------------------------------------------------------------------------------------------- walls

def wall_line(sections, close=WALL_CLOSE_M):
    """The storey's wall line: its section lines unioned, gaps up to 2 x close bridged (a closing), the outer ring."""
    lines = shapely.union_all(sections)
    grown = lines.buffer(close, join_style="mitre", mitre_limit=4.0)
    rings = [Polygon(g.exterior) for g in shapely.get_parts(grown)]
    if not rings:
        return None
    outer = max(rings, key=lambda g: g.area)
    shrunk = outer.buffer(-close, join_style="mitre", mitre_limit=4.0)
    if shrunk.is_empty:
        return None
    poly = max(shapely.get_parts(shrunk), key=lambda g: g.area)
    return orient(Polygon(poly.exterior).simplify(SIMPLIFY_M, preserve_topology=True), 1.0)


def _convex_ends(pts):
    """Per wall of a CCW ring: (start, end) is at a convex corner."""
    n = len(pts)
    turn = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        d1, d2 = b - a, c - b
        turn.append(float(d1[0] * d2[1] - d1[1] * d2[0]) > 0)
    return [(turn[i], turn[(i + 1) % n]) for i in range(n)]


def wall_openings(poly, glass_segs, glass_z, z_lo, z_hi, w, depth=0.4):
    """Openings per wall of a storey from its glass: spans along the wall within EDGE_TOL_M of its line, panes
    closer than PANE_GAP_M one opening, kept WALL_END_M off the wall ends; heights from the glass parts."""
    pts = np.asarray(poly.exterior.coords)[:-1]
    convex = _convex_ends(pts)
    out = defaultdict(list)
    for wi in range(len(pts)):
        a, b = pts[wi], pts[(wi + 1) % len(pts)]
        L = float(np.linalg.norm(b - a))
        # at a convex corner an opening keeps its reveal depth off the end: the reveals of two openings round a
        # corner never meet inside it
        end0 = depth + WALL_END_M if convex[wi][0] else WALL_END_M
        end1 = depth + WALL_END_M if convex[wi][1] else WALL_END_M
        if L < 2 * WALL_END_M + 0.2:
            continue
        u = (b - a) / L
        nrm = np.array([u[1], -u[0]])
        spans = []
        for sg, (gz0, gz1) in zip(glass_segs, glass_z):
            c = np.asarray(sg.coords)
            rel = c - a
            s, d = rel @ u, rel @ nrm
            if np.abs(d).max() > EDGE_TOL_M or abs(float(np.dot((c[1] - c[0]) / max(np.linalg.norm(c[1] - c[0]), 1e-9), u))) < 0.99:
                continue
            s0, s1 = float(max(s.min(), end0)), float(min(s.max(), L - end1))
            if s1 - s0 > 0.05:
                spans.append([s0, s1, max(gz0, z_lo + w * 2), min(gz1, z_hi - w * 2)])
        spans.sort()
        merged = []
        for sp in spans:
            if merged and sp[0] - merged[-1][1] <= PANE_GAP_M:
                m = merged[-1]
                m[1], m[2], m[3] = max(m[1], sp[1]), min(m[2], sp[2]), max(m[3], sp[3])
            else:
                merged.append(list(sp))
        out[wi] = [m for m in merged if m[3] - m[2] > 0.1]
    return out


WALL_SEAT_M = 0.02       # the walls stand this far inside the slab edges they sit on (no shared vertex)


def storey_walls(mesh: _Mesh, poly, openings, z_lo, z_hi, inputs: Inputs):
    """The walls of one storey: quads per wall (columns its own, rows the storey's), holes with planes and reveals."""
    pts = np.asarray(poly.exterior.coords)[:-1]
    # the storey's rows: sills and heads within ROW_SNAP_M of each other are one row (panes of one band differ by
    # millimetres); an opening takes its row
    rows = []
    for z in sorted(z for ops in openings.values() for o in ops for z in o[2:4]):
        if not rows or z - rows[-1][0] > ROW_SNAP_M:
            rows.append([z])
        else:
            rows[-1].append(z)
    reps = [float(np.median(r)) for r in rows]
    snap = lambda z: min(reps, key=lambda r: abs(r - z))                                # noqa: E731
    openings = {wi: [[o[0], o[1], snap(o[2]), snap(o[3])] for o in ops if snap(o[3]) - snap(o[2]) > 0.1]
                for wi, ops in openings.items()}
    zs = sorted({round(z_lo, 6), round(z_hi, 6)} | {round(z, 6) for ops in openings.values() for o in ops for z in o[2:4]})
    depth = inputs.opening_depth_m
    eps = 1e-4
    for wi in range(len(pts)):
        a, b = pts[wi], pts[(wi + 1) % len(pts)]
        L = float(np.linalg.norm(b - a))
        u = (b - a) / L
        out_n = np.array([u[1], -u[0], 0.0])
        ops = openings.get(wi, [])
        ss = sorted({0.0, round(L, 9)} | {round(x, 9) for o in ops for x in o[:2]})
        P = lambda s, z: [*(a + u * s), z]                                               # noqa: E731
        Q = lambda s, z: [*(a + u * s - out_n[:2] * depth), z]                            # noqa: E731

        def hole(s, z):
            return next((o for o in ops if o[0] < s < o[1] and o[2] < z < o[3]), None)
        for s0, s1 in zip(ss, ss[1:]):
            for z0, z1 in zip(zs, zs[1:]):
                sm, zm = (s0 + s1) / 2, (z0 + z1) / 2
                o = hole(sm, zm)
                if o is None:
                    mesh.quad([P(s0, z0), P(s1, z0), P(s1, z1), P(s0, z1)], inputs.facade_id, out_n)
                    continue
                mesh.quad([Q(s0, z0), Q(s1, z0), Q(s1, z1), Q(s0, z1)], inputs.opening_id, out_n)
                for (sa, za), (sb, zb), outside, face in (
                        ((s0, z0), (s1, z0), (sm, z0 - eps), [0, 0, 1]), ((s0, z1), (s1, z1), (sm, z1 + eps), [0, 0, -1]),
                        ((s0, z0), (s0, z1), (s0 - eps, zm), [u[0], u[1], 0]), ((s1, z0), (s1, z1), (s1 + eps, zm), [-u[0], -u[1], 0])):
                    if hole(*outside) is o:
                        continue
                    mesh.quad([P(sa, za), P(sb, zb), Q(sb, zb), Q(sa, za)], inputs.reveal_id, face)


# ---------------------------------------------------------------------------------------------- decor

def _box(mesh, frame, lo, hi, mid):
    """A closed box in a plan frame (origin o, along u, out n): lo/hi = (s, d, z) corners."""
    o, u, n = frame
    def P(s, d, z):
        return [*(o + u * s + n * d), z]
    (s0, d0, z0), (s1, d1, z1) = lo, hi
    c = [P(s0, d0, z0), P(s1, d0, z0), P(s1, d1, z0), P(s0, d1, z0), P(s0, d0, z1), P(s1, d0, z1), P(s1, d1, z1), P(s0, d1, z1)]
    u3, n3 = np.array([*u, 0.0]), np.array([*n, 0.0])
    for ids, f in (((0, 1, 2, 3), [0, 0, -1]), ((4, 5, 6, 7), [0, 0, 1]), ((0, 1, 5, 4), -n3), ((2, 3, 7, 6), n3),
                   ((0, 3, 7, 4), -u3), ((1, 2, 6, 5), u3)):
        mesh.quad([c[i] for i in ids], mid, f)


def split_flat(v, t, thin=1e-3):
    """A module's triangles split into (flat, solid): pieces thinner than `thin` along their own normal are planes."""
    flat, solid = [], []
    for pc in _pieces(v, t):
        q = v[t[pc]]
        n = np.cross(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0])
        big = n[np.linalg.norm(n, axis=1).argmax()]              # the plane of its largest triangle (a closed
        ln = np.linalg.norm(big)                                  # solid's normals sum to zero: never that)
        thick = float(np.ptp(q.reshape(-1, 3) @ (big / ln))) if ln > 1e-12 else 0.0
        (flat if thick < thin else solid).append(t[pc])
    cat = lambda xs: np.vstack(xs) if xs else np.zeros((0, 3), int)                    # noqa: E731
    return cat(flat), cat(solid)


SECTION_SAME_M = 0.01   # pieces of one element share their section (depth range) within this
AXIS_DEG = 2.0           # a decor piece whose rectangle turns more than this off the building axes is no box


def decor_elements(v, t, seam=DECOR_SEAM_M, odd=None):
    """Elements of a decor module: each piece's plan rectangle (minimum rotated) and z range, pieces of one
    element (same rectangle within the seam, stacked in z with seams up to it; or one section run along one axis)
    merged. Returns (frame, lo, hi) per element."""
    rects = []
    for pc in _pieces(v, t):
        q = v[np.unique(t[pc])]
        r = shapely.MultiPoint(q[:, :2]).minimum_rotated_rectangle
        if r.geom_type != "Polygon":
            continue
        c = np.asarray(r.exterior.coords)[:4]
        e1, e2 = c[1] - c[0], c[2] - c[1]
        u = e1 / np.linalg.norm(e1) if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2 / np.linalg.norm(e2)
        if abs(u[0]) >= abs(u[1]):
            u = u * np.sign(u[0]) if u[0] else u
        else:
            u = u * np.sign(u[1]) if u[1] else u
        if odd is not None and min(abs(u[0]), abs(u[1])) > np.sin(np.radians(AXIS_DEG)):
            odd.append(t[pc])                      # a corner insert, a chamfer: rebuilt face by face, not boxed
            continue
        n = np.array([u[1], -u[0]])
        s, d = q[:, :2] @ u, q[:, :2] @ n
        ang = round(float(np.arctan2(u[1], u[0])), 3)
        s0, s1, d0, d1, z0, z1 = float(s.min()), float(s.max()), float(d.min()), float(d.max()), float(q[:, 2].min()), float(q[:, 2].max())
        hole = _front_hole(v[t[pc]], u)               # a frame (a ring in its front view): four bars round the hole
        if hole is None:
            rects.append([ang, s0, s1, d0, d1, z0, z1, u, n])
            continue
        hs0, hz0, hs1, hz1 = hole
        for bs0, bs1, bz0, bz1 in ((s0, hs0, z0, z1), (hs1, s1, z0, z1), (hs0, hs1, z0, hz0), (hs0, hs1, hz1, z1)):
            if bs1 - bs0 > 1e-3 and bz1 - bz0 > 1e-3:
                rects.append([ang, bs0, bs1, d0, d1, bz0, bz1, u, n])
    # merge: same direction and section, touching along s or z within the seam
    rects.sort(key=lambda r: (r[0], round(r[3], 2), round(r[4], 2), r[1], r[5]))
    merged = []
    for r in rects:
        hit = None
        for m in merged[-50:]:
            if m[0] != r[0] or abs(m[3] - r[3]) > SECTION_SAME_M or abs(m[4] - r[4]) > SECTION_SAME_M:
                continue
            same_s = abs(m[1] - r[1]) <= seam and abs(m[2] - r[2]) <= seam
            same_z = abs(m[5] - r[5]) <= seam and abs(m[6] - r[6]) <= seam
            if (same_s and r[5] - m[6] <= seam and m[5] - r[6] <= seam) or (same_z and r[1] - m[2] <= seam and m[1] - r[2] <= seam):
                hit = m
                break
        if hit is None:
            merged.append(list(r))
        else:
            hit[1], hit[2], hit[3], hit[4] = min(hit[1], r[1]), max(hit[2], r[2]), min(hit[3], r[3]), max(hit[4], r[4])
            hit[5], hit[6] = min(hit[5], r[5]), max(hit[6], r[6])
    return [((np.zeros(2), m[7], m[8]), (m[1], m[3], m[5]), (m[2], m[4], m[6])) for m in merged]


def _front_hole(p, u):
    """The bounds (s0, z0, s1, z1) of the largest hole in a piece's front view (along u, up z), or None."""
    flat = np.stack([p[:, :, :2] @ u, p[:, :, 2]], axis=2)
    e1, e2 = flat[:, 1] - flat[:, 0], flat[:, 2] - flat[:, 0]
    keep = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) > 1e-10
    if not keep.any():
        return None
    try:
        sil = shapely.union_all(shapely.polygons(flat[keep]), grid_size=1e-4)
    except shapely.errors.GEOSException:
        return None
    holes = [Polygon(r) for g in shapely.get_parts(sil) if g.geom_type == "Polygon" for r in g.interiors]
    holes = [h for h in holes if h.area > 0.01]
    return max(holes, key=lambda h: h.area).bounds if holes else None


# ---------------------------------------------------------------------------------------------- planes

def footprint_ring(v, t, simplify=0.02):
    """The outer ring of a module's plan footprint (its triangles projected and unioned), simplified."""
    p = v[t][:, :, :2]
    e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
    keep = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) > 1e-10
    polys = list(shapely.polygons(p[keep]))
    for a, b, c in p[~keep]:                       # vertical faces project to lines: a thin strip of them
        polys.append(LineString([a, b, c]).buffer(0.005))
    fp = shapely.union_all(polys, grid_size=1e-4).buffer(0.01).buffer(-0.01)
    g = max(shapely.get_parts(fp), key=lambda x: x.area)
    return orient(Polygon(g.exterior).simplify(simplify, preserve_topology=True), 1.0)


def planes_along(mesh: _Mesh, ring, z0, z1, mid, top=False):
    """One-sided planes on a ring from z0 to z1, facing out; with top, its fill at z1 facing up and the planes
    cut at every fill vertex on the ring (no T-junction at the top edge)."""
    ring = orient(ring, 1.0)
    cuts = [np.asarray(ring.exterior.coords)[:-1]]
    if top:
        pieces, _ = _fill(ring, FILL_STEP_M, (ring.bounds[0], ring.bounds[1]))
        for q in pieces:
            (mesh.quad if len(q) == 4 else mesh.tri)([[*x, z1] for x in q], mid, [0, 0, 1])
        cuts = _outline_cuts(ring, pieces)[:1]
    c = cuts[0]
    for a, b in zip(c, np.roll(c, -1, axis=0)):
        d = b - a
        mesh.quad([[*a, z0], [*b, z0], [*b, z1], [*a, z1]], mid, [d[1], -d[0], 0])


def _inset_ring(pts, t):
    """A CCW ring's points moved t inward along their mitres (same count, one to one)."""
    out = []
    n = len(pts)
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        d1, d2 = (b - a) / np.linalg.norm(b - a), (c - b) / np.linalg.norm(c - b)
        n1, n2 = np.array([-d1[1], d1[0]]), np.array([-d2[1], d2[0]])       # inward normals of a CCW ring
        m = n1 + n2
        m = m / np.linalg.norm(m) if np.linalg.norm(m) > 1e-9 else n1
        out.append(b + m * t / max(float(m @ n1), 0.2))
    return np.asarray(out)


def band_box(mesh: _Mesh, ring, z0, z1, thick, mid):
    """A closed band on a ring (a textured parapet band): outer and inner faces, top and bottom, `thick` wide."""
    o = np.asarray(orient(ring, 1.0).exterior.coords)[:-1]
    i = _inset_ring(o, thick)
    for k in range(len(o)):
        a, b, ia, ib = o[k], o[(k + 1) % len(o)], i[k], i[(k + 1) % len(o)]
        d = b - a
        mesh.quad([[*a, z0], [*b, z0], [*b, z1], [*a, z1]], mid, [d[1], -d[0], 0])
        mesh.quad([[*ib, z0], [*ia, z0], [*ia, z1], [*ib, z1]], mid, [-d[1], d[0], 0])
        mesh.quad([[*a, z1], [*b, z1], [*ib, z1], [*ia, z1]], mid, [0, 0, 1])
        mesh.quad([[*a, z0], [*ia, z0], [*ib, z0], [*b, z0]], mid, [0, 0, -1])


RAILING_T_M = 0.02       # pattern terrace (user 2026-10-14): a glass railing is one closed plate per ledge side
RAILING_LIFT_M = 0.004   # standing on the deck, not welded to it (past weld_m)


def terrace_railings(mesh: _Mesh, deck, upper, z, h, mid, thick=RAILING_T_M):
    """Pattern terrace, glass railings (user 2026-10-14): one closed plate `thick` thick per side of the ledge
    that does not run along the walls above (`upper`), its outer face on the ledge's edge, from the deck top to
    the railing height; plates of two sides meeting at a corner are trimmed by the thickness (no overlap); frames
    and edge trims are texture. Returns the number of plates."""
    n = 0
    for part in shapely.get_parts(deck):
        ring = np.asarray(orient(part.simplify(0.01, preserve_topology=True), 1.0).exterior.coords)[:-1]
        side = [upper.exterior.distance(shapely.Point(*((ring[i] + ring[(i + 1) % len(ring)]) / 2))) > 0.1
                for i in range(len(ring))]
        for i in range(len(ring)):
            if not side[i]:
                continue
            a, b = ring[i], ring[(i + 1) % len(ring)]
            L = float(np.linalg.norm(b - a))
            u = (b - a) / L
            inn = np.array([-u[1], u[0]])               # into the deck (CCW ring)
            s0 = thick + RAILING_LIFT_M if side[i - 1] else 0.0   # the previous side's plate holds the corner;
                                                                  # a gap past the weld, no shared face
            if L - s0 <= thick:
                continue
            o0, o1 = a + u * s0, b
            lo, hi = z + RAILING_LIFT_M, z + h
            c = [o0, o1, o1 + inn * thick, o0 + inn * thick]
            bot = [[*p, lo] for p in c]
            top = [[*p, hi] for p in c]
            mesh.quad(bot[::-1], mid, [0, 0, -1])
            mesh.quad(top, mid, [0, 0, 1])
            for k in range(4):
                d = c[(k + 1) % 4] - c[k]
                mesh.quad([bot[k], bot[(k + 1) % 4], top[(k + 1) % 4], top[k]], mid, [d[1], -d[0], 0])
            n += 1
    return n


def face_planes(mesh: _Mesh, v, t, mid, min_area=1e-3, thick=None):
    """A plane module rebuilt face by face: the source triangles grouped by plane (normal, offset) and by
    connection, each group one rectangle in its plane; a group that fills less than 90 % of its rectangle keeps
    its own triangles (counted)."""
    p = v[t]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-12
    n[ok] /= ln[ok, None]
    key = defaultdict(list)
    for k in np.flatnonzero(ok):
        nn = np.round(n[k], 3)
        key[(*nn, round(float(n[k] @ p[k, 0]), 3))].append(k)
    kept = 0
    for _, ks in key.items():                       # the key groups; the plane is the group's own (exact), never
        sub = t[ks]                                  # the rounded key (a rounded normal times an offset of ~80 m
        nn = n[ks].mean(axis=0)                      # moves a plane by centimetres)
        nn = nn / np.linalg.norm(nn)
        for pc in _pieces(v, sub):
            q = v[sub[pc]]
            area = float(np.linalg.norm(np.cross(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]), axis=1).sum() / 2)
            if area < min_area:
                continue
            ax = np.array([0.0, 0.0, 1.0]) if abs(nn[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
            e1 = np.cross(ax, nn); e1 /= np.linalg.norm(e1)
            e2 = np.cross(nn, e1)
            pts = q.reshape(-1, 3)
            a1, a2 = pts @ e1, pts @ e2
            if area < 0.99 * (np.ptp(a1) * np.ptp(a2)):
                kept += 1
                for tri in q:
                    mesh.tri(tri.tolist(), mid, nn)
                continue
            o = nn * float((pts @ nn).mean())
            corners = [o + e1 * a1.min() + e2 * a2.min(), o + e1 * a1.max() + e2 * a2.min(),
                       o + e1 * a1.max() + e2 * a2.max(), o + e1 * a1.min() + e2 * a2.max()]
            if thick is None:
                mesh.quad([c.tolist() for c in corners], mid, nn)
                continue
            back = [c - nn * thick for c in corners]          # a closed thin plate (glass of a railing)
            mesh.quad([c.tolist() for c in corners], mid, nn)
            mesh.quad([c.tolist() for c in back[::-1]], mid, -nn)
            for k in range(4):
                a_, b_ = corners[k], corners[(k + 1) % 4]
                mesh.quad([a_.tolist(), b_.tolist(), back[(k + 1) % 4].tolist(), back[k].tolist()], mid, (a_ + b_) / 2 - o - e1 * (a1.min() + a1.max()) / 2 - e2 * (a2.min() + a2.max()) / 2)
    return kept


# ---------------------------------------------------------------------------------------------- decor by profile

PROFILE_SIMPLIFY_M = 0.01   # a decor section keeps its shape within this (user 2026-10-14: the real section)
PROFILE_SAME_M = 0.02       # pieces of one run share a section within this (user 2026-10-14: seams are texture,
                            # a run is one mesh; the longest piece's section is kept)
JOINT_RECESS_M = 0.005      # where a pier meets a band, the one that gives way runs this far into the other
JOINT_PROUD_M = 0.005       # the band that runs through stands this far proud of the pier's face


def _frame_of(q):
    """The plan frame of a piece: u along its longer plan side snapped to the nearest building axis sign, n out."""
    r = shapely.MultiPoint(q[:, :2]).minimum_rotated_rectangle
    c = np.asarray(r.exterior.coords)[:4] if r.geom_type == "Polygon" else np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    e1, e2 = c[1] - c[0], c[2] - c[1]
    u = e1 / np.linalg.norm(e1) if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2 / np.linalg.norm(e2)
    if abs(u[0]) >= abs(u[1]):
        u = u * (np.sign(u[0]) or 1.0)
    else:
        u = u * (np.sign(u[1]) or 1.0)
    return u, np.array([u[1], -u[0]])


def _section_poly(v3, t, at, loose=None):
    """The section of a triangle set by the plane (third coordinate) = at, as one polygon in the first two, or None;
    with `loose`, the section lines off that polygon (zero-thickness sheets: a balcony's walls) are added to it."""
    segs = _section(v3, t, at)
    if not segs:
        return None
    lines = shapely.union_all(segs)
    polys = list(shapely.get_parts(shapely.polygonize(list(shapely.get_parts(lines)))))
    if polys:
        g = shapely.union_all(polys)
    else:                                                   # an open section: closed by a 1 mm growth
        g = lines.buffer(0.001, join_style="mitre").buffer(-0.0005, join_style="mitre")
    g = max(shapely.get_parts(g), key=lambda x: x.area) if not g.is_empty else None
    if g is None or g.area <= 1e-6:
        return None
    if loose is not None:
        rest = lines.difference(g.buffer(0.002))
        loose += [ls.simplify(PROFILE_SIMPLIFY_M) for ls in shapely.get_parts(shapely.line_merge(rest))
                  if ls.geom_type == "LineString" and ls.length > 0.05]
    return orient(Polygon(g.exterior).simplify(PROFILE_SIMPLIFY_M, preserve_topology=True), 1.0)


def profile_elements(v, t, centre, odd=None):
    """Decor elements by their real section (user 2026-10-14): each piece is cut across its main axis - a pier
    (taller than long) in plan at its mid height, a band or a balcony (longer than tall) across its length at its
    middle - and extruded over its extent; pieces of one element (same section within PROFILE_SAME_M, touching
    along the axis within DECOR_SEAM_M) merged; the back of the section is set DECOR_INSET_M into the wall.
    Returns [(axis "z" | "s", u, n, section polygon, a0, a1)]; a piece no section can be taken of goes to `odd`."""
    out = []
    for pc in _pieces(v, t):
        tri = t[pc]
        q = v[np.unique(tri)]
        u, n = _frame_of(q)
        if odd is not None and min(abs(u[0]), abs(u[1])) > np.sin(np.radians(AXIS_DEG)):
            odd.append(tri)
            continue
        s, d, z = q[:, :2] @ u, q[:, :2] @ n, q[:, 2]
        outward = float(((s.mean() * u + d.mean() * n) - centre) @ n) > 0
        if np.ptp(z) >= np.ptp(s):                          # a pier: the plan section, extruded up
            a0, a1 = float(z.min()), float(z.max())
            v3 = np.column_stack([v[:, :2] @ u, v[:, :2] @ n, v[:, 2]])
            axis = "z"
        else:                                               # a band, a balcony: the cross section, along u
            a0, a1 = float(s.min()), float(s.max())
            v3 = np.column_stack([v[:, :2] @ n, v[:, 2], v[:, :2] @ u])
            axis = "s"
        sec, loose = None, []
        for f in (0.5, 0.37, 0.63):                         # off a vertex or a seam
            loose = []
            sec = _section_poly(v3, tri, a0 + f * (a1 - a0), loose)
            if sec is not None:
                break
        if sec is None:
            if odd is not None:
                odd.append(tri)
            continue
        # the back into the wall: along d, the side away from the outside
        bx = sec.bounds                                      # (x0, y0, x1, y1) in the section's coordinates
        if axis == "z":                                      # section in (s, d): the back is the low d (outward) side
            back = (bx[1] - DECOR_INSET_M, bx[1] + 1e-3) if outward else (bx[3] - 1e-3, bx[3] + DECOR_INSET_M)
            near = [x for x, y in sec.exterior.coords if abs(y - (bx[1] if outward else bx[3])) <= 0.01]
            strip = shapely.box(min(near), back[0], max(near), back[1]) if near else None
        else:                                                # section in (d, z): the back is the low d (outward) side
            back = (bx[0] - DECOR_INSET_M, bx[0] + 1e-3) if outward else (bx[2] - 1e-3, bx[2] + DECOR_INSET_M)
            near = [y for x, y in sec.exterior.coords if abs(x - (bx[0] if outward else bx[2])) <= 0.01]
            strip = shapely.box(back[0], min(near), back[1], max(near)) if near else None
        if strip is not None and strip.area > 0:
            g = sec.union(strip)
            if g.geom_type == "Polygon":
                sec = orient(Polygon(g.exterior).simplify(PROFILE_SIMPLIFY_M / 2, preserve_topology=True), 1.0)
        out.append([axis, u, n, sec, a0, a1, loose])
    # merge touching pieces of one run along their axis (one mesh, no seam); the run keeps its longest piece's
    # section; a true change of section (past PROFILE_SAME_M) starts a new run
    out.sort(key=lambda e: (e[0], round(float(np.arctan2(e[1][1], e[1][0])), 3), round(e[3].centroid.x, 1),
                            round(e[3].centroid.y, 1), e[4]))
    runs = []
    for e in out:
        hit = None
        for r in runs[-30:]:
            if (r[0] == e[0] and np.allclose(r[1], e[1]) and e[4] - r[5] <= DECOR_SEAM_M and r[4] - e[5] <= DECOR_SEAM_M
                    and r[3].hausdorff_distance(e[3]) <= PROFILE_SAME_M):
                hit = r
                break
        if hit is None:
            runs.append(list(e) + [e[5] - e[4]])
        else:
            if e[5] - e[4] > hit[7]:                        # the longest piece's section
                hit[3], hit[7] = e[3], e[5] - e[4]
            hit[4], hit[5] = min(hit[4], e[4]), max(hit[5], e[5])
            hit[6] = hit[6] + e[6]
    return [tuple(r[:7]) for r in runs]


def _plan(e):
    """An element's plan polygon (world) and its z range."""
    axis, u, n, sec, a0, a1 = e[:6]
    if axis == "z":
        ring = [u * a + n * b for a, b in np.asarray(sec.exterior.coords)[:-1]]
        return Polygon(ring), (a0, a1)
    x0, z0, x1, z1 = sec.bounds                           # (d, z) section
    return Polygon([u * a0 + n * x0, u * a1 + n * x0, u * a1 + n * x1, u * a0 + n * x1]), (z0, z1)


def resolve_joints(elements):
    """Piers and bands where they meet (user 2026-10-14): a band whose plan covers the pier runs through - the
    pier stops JOINT_RECESS_M inside it with no cap there, and the band stands JOINT_PROUD_M proud of the pier's
    face; a pier deeper than the band runs through and the band stops inside it the same way. Returns
    [(element, caps_at)] and the joint count."""
    piers = [list(e) for e in elements if e[0] == "z"]
    bands = [list(e) for e in elements if e[0] == "s"]
    pcaps, bcaps = [[True, True] for _ in piers], [[True, True] for _ in bands]
    joints = 0
    split_piers = []
    for i, p in enumerate(piers):
        pp, (pz0, pz1) = _plan(p)
        cuts = []
        for j, b in enumerate(bands):
            bp, (bz0, bz1) = _plan(b)
            if bz1 <= pz0 or bz0 >= pz1 or not bp.intersects(pp) or bp.intersection(pp).area < 1e-4:
                continue
            joints += 1
            if bp.buffer(0.03).covers(pp):                   # the band runs through: proud of the pier, pier inside
                axis, u, n, sec, a0, a1 = b[:6]
                front = max(float(np.dot(q, n)) for q in np.asarray(pp.exterior.coords))
                x0, z0, x1, z1 = sec.bounds
                if x1 < front + JOINT_PROUD_M:              # its outer face (high d) stands proud of the pier's
                    b[3] = sec.union(shapely.box(x0, z0, front + JOINT_PROUD_M, z1)).simplify(1e-4)
                    b[3] = orient(Polygon(max(shapely.get_parts(b[3]), key=lambda g: g.area).exterior), 1.0)
                cuts.append((bz0, bz1))
            else:                                            # the pier runs through: the band stops inside it
                axis, u, n, sec, a0, a1 = b[:6]
                s_in = [float(np.dot(q, u)) for q in np.asarray(pp.exterior.coords)]
                lo, hi = min(s_in), max(s_in)
                if lo - JOINT_RECESS_M <= a0 <= hi:         # the band starts in the pier
                    b[4] = max(a0, hi - JOINT_RECESS_M)
                    bcaps[j][0] = False
                if lo <= a1 <= hi + JOINT_RECESS_M:         # the band ends in the pier
                    b[5] = min(a1, lo + JOINT_RECESS_M)
                    bcaps[j][1] = False
        # split the pier at the bands that run through it
        segs = [[pz0, pz1, True, True]]
        for bz0, bz1 in sorted(cuts):
            nxt = []
            for z0, z1, c0, c1 in segs:
                if bz1 <= z0 or bz0 >= z1:
                    nxt.append([z0, z1, c0, c1])
                    continue
                if bz0 - z0 > 0.02:
                    nxt.append([z0, bz0 + JOINT_RECESS_M, c0, False])
                if z1 - bz1 > 0.02:
                    nxt.append([bz1 - JOINT_RECESS_M, z1, False, c1])
            segs = nxt
        for z0, z1, c0, c1 in segs:
            q = list(p)
            q[4], q[5] = z0, z1
            split_piers.append((tuple(q), (c0, c1)))
    out = split_piers + [(tuple(b), tuple(c)) for b, c in zip(bands, bcaps) if b[5] - b[4] > 0.01]
    return out, joints


def inset_panels(mesh: _Mesh, v, t, stor, mid, gap=0.005):
    """Dark inserts (user 2026-10-14): flat panels in front of the wall, nearer than 2 cm to each other one panel,
    built as a box - its front at the outermost plane, its back WALL inset past the storey's wall line, no back
    face; its top and bottom kept `gap` off an opening's sill or head on that storey. Returns the panel count."""
    pieces = [v[np.unique(t[pc])] for pc in _pieces(v, t)]
    groups = []
    for q in pieces:
        hit = next((g for g in groups if np.all(q.min(0) - 0.02 <= g[1]) and np.all(q.max(0) + 0.02 >= g[0])), None)
        if hit is None:
            groups.append([q.min(0), q.max(0), [q]])
        else:
            hit[0], hit[1] = np.minimum(hit[0], q.min(0)), np.maximum(hit[1], q.max(0))
            hit[2].append(q)
    n_out, skipped = 0, []
    for lo, hi, qs in groups:
        allp = np.vstack(qs)
        zm = float(allp[:, 2].mean())
        st = next((x for x in stor.values() if x["z"][0] - 0.3 <= zm <= x["z"][1] + 0.3), None)
        if st is None:
            continue
        ring, poly = st["poly"].exterior, st["poly"]
        q0 = qs[0]                                           # the panel's own plane: its normal, out of the wall
        nn = np.cross(q0[1] - q0[0], q0[2] - q0[0])[:2] if len(q0) >= 3 else np.zeros(2)
        if np.linalg.norm(nn) < 1e-9:
            continue
        nvec = nn / np.linalg.norm(nn)
        c = allp[:, :2].mean(axis=0)
        if poly.distance(shapely.Point(*(c + nvec * 0.1))) < poly.distance(shapely.Point(*(c - nvec * 0.1))):
            nvec = -nvec                                     # out of the wall: away from the storey's plan
        hit = shapely.LineString([c, c - nvec * 5.0]).intersection(ring)   # back along the normal to the wall
        pts_hit = [np.asarray(g.coords[0]) for g in shapely.get_parts(hit) if not g.is_empty]
        if not pts_hit:
            skipped.append([round(float(x), 2) for x in c])
            continue
        back = min(pts_hit, key=lambda x: float(np.linalg.norm(x - c)))
        u = np.array([-nvec[1], nvec[0]])
        s_ = allp[:, :2] @ u
        d_out = float((allp[:, :2] @ nvec).max())            # the outermost plane
        d_wall = float(back @ nvec) - DECOR_INSET_M
        z0, z1 = float(allp[:, 2].min()), float(allp[:, 2].max())
        rows = [z for ops in st["openings"].values() for o in ops for z in o[2:4]]
        if any(abs(z0 - z) <= 0.01 for z in rows):
            z0 += gap
        if any(abs(z1 - z) <= 0.01 for z in rows):
            z1 -= gap
        if z1 - z0 <= 0.02 or d_out - d_wall <= 0.01:
            continue
        a0, a1 = float(s_.min()), float(s_.max())
        P = lambda a, d, z: [*(u * a + nvec * d), z]                                    # noqa: E731
        f = [P(a0, d_out, z0), P(a1, d_out, z0), P(a1, d_out, z1), P(a0, d_out, z1)]
        b = [P(a0, d_wall, z0), P(a1, d_wall, z0), P(a1, d_wall, z1), P(a0, d_wall, z1)]
        n3, u3 = [*nvec, 0.0], [*u, 0.0]
        mesh.quad(f, mid, n3)                                # front
        mesh.quad([b[0], b[1], f[1], f[0]], mid, [0, 0, -1])  # bottom
        mesh.quad([f[3], f[2], b[2], b[3]], mid, [0, 0, 1])   # top
        mesh.quad([b[0], f[0], f[3], b[3]], mid, [-x for x in u3])
        mesh.quad([f[1], b[1], b[2], f[2]], mid, u3)         # no back face: it lies in the wall
        n_out += 1
    return n_out


def extrude(mesh: _Mesh, element, mid, caps_at=(True, True)):
    """A decor element: its section extruded between a0 and a1 along its axis; side quads, caps (quads, else a
    triangulation of the section) - a cap inside another element is left out (caps_at)."""
    axis, u, n, sec, a0, a1 = element[:6]
    loose = element[6] if len(element) > 6 else []
    u3, n3, z3 = np.array([*u, 0.0]), np.array([*n, 0.0]), np.array([0.0, 0.0, 1.0])
    if axis == "z":
        P = lambda a, b, h: u3 * a + n3 * b + z3 * h                                      # noqa: E731
        along = z3
    else:
        P = lambda a, b, h: n3 * a + z3 * b + u3 * h                                      # noqa: E731
        along = u3
    ring = np.asarray(sec.exterior.coords)[:-1]
    for i in range(len(ring)):
        a, b = ring[i], ring[(i + 1) % len(ring)]
        e = b - a
        out2 = P(e[1], -e[0], 0.0)                         # the outward normal of a CCW ring in the section plane
        mesh.quad([P(*a, a0).tolist(), P(*b, a0).tolist(), P(*b, a1).tolist(), P(*a, a1).tolist()], mid, out2)
    caps = [ring] if len(ring) == 4 and sec.convex_hull.area - sec.area <= 1e-9 else \
        [np.asarray(x.exterior.coords)[:-1] for x in shapely.get_parts(shapely.constrained_delaunay_triangles(sec))]
    for c in caps:
        for h, f, on in ((a0, -along, caps_at[0]), (a1, along, caps_at[1])):
            if on:
                (mesh.quad if len(c) == 4 else mesh.tri)([P(*x, h).tolist() for x in c], mid, f)
    for ls in loose:                                    # zero-thickness sheets of the element: planes along it
        c = np.asarray(ls.coords)
        for a, b in zip(c[:-1], c[1:]):
            e = b - a
            mesh.quad([P(*a, a0).tolist(), P(*b, a0).tolist(), P(*b, a1).tolist(), P(*a, a1).tolist()], mid,
                      P(e[1], -e[0], 0.0))


# ---------------------------------------------------------------------------------------------- compare

def compare(src_v, src_t, mesh_v, mesh_t, views=("top", "x", "y")):
    """Silhouette IoU per view, extents and areas of a built module against its source module."""
    from twinqa.geometry.measure import iou, silhouette
    a, b = src_v[src_t], np.asarray(mesh_v, float)[np.asarray(mesh_t, int)]
    area = lambda p: float(np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1).sum() / 2)  # noqa
    def one(view):
        for grid in (1e-3, 1e-2, 5e-2):              # a finer grid can fail in GEOS on near-degenerate projections
            try:
                return round(iou(silhouette(a, view, grid), silhouette(b, view, grid)), 4)
            except shapely.errors.GEOSException:
                continue
        return None
    out = {"iou": {v: one(v) for v in views},
           "bbox_source": [np.round(a.reshape(-1, 3).min(0), 3).tolist(), np.round(a.reshape(-1, 3).max(0), 3).tolist()],
           "bbox_model": [np.round(b.reshape(-1, 3).min(0), 3).tolist(), np.round(b.reshape(-1, 3).max(0), 3).tolist()],
           "area_source_m2": round(area(a), 1), "area_model_m2": round(area(b), 1),
           "triangles_source": int(len(a)), "triangles_model": int(len(b))}
    return out


# ---------------------------------------------------------------------------------------------- measure + spec

def _storeys(glass_part, slabs, levels, inputs: Inputs):
    """Per storey (level name): its z range (top of the slab below to the underside of the slab above), its wall
    contour (the outline of the slab above - the storey's footprint, set WALL_SEAT_M in) and its openings from the
    glass module."""
    gv, gt = glass_part[:2]
    gpieces = []
    for pc in _pieces(gv, gt):
        q = gv[np.unique(gt[pc])]
        gpieces.append((pc, float(q[:, 2].min()), float(q[:, 2].max())))
    top_of = {n: (top, under, o) for n, top, under, o in slabs}
    out = {}
    for k in range(len(levels) - 1):
        name, nxt = levels[k][0], levels[k + 1][0]
        if nxt not in top_of:
            continue
        z_lo = top_of[name][0] if name in top_of else levels[k][1]
        z_hi = top_of[nxt][1] if top_of[nxt][1] is not None else levels[k + 1][1]
        ceil = top_of[nxt][2]
        poly = orient(Polygon(max(shapely.get_parts(ceil), key=lambda g: g.area).exterior)
                      .simplify(SIMPLIFY_M, preserve_topology=True), 1.0)
        poly = orient(Polygon(_inset_ring(np.asarray(poly.exterior.coords)[:-1], WALL_SEAT_M)), 1.0)   # seated, not shared
        zm = (z_lo + z_hi) / 2
        segs, gz = [], []
        for pc, za, zb in gpieces:
            if za < zm < zb:
                for sg in _section(gv, gt[pc], zm):
                    segs.append(sg)
                    gz.append((za, zb))
        out[name] = {"z": (z_lo, z_hi), "poly": poly,
                     "openings": snap_rows(wall_openings(poly, segs, gz, z_lo, z_hi, inputs.weld_m, inputs.opening_depth_m))}
    return out


def snap_rows(openings):
    """Sills and heads of one storey within ROW_SNAP_M are one row (panes of one band differ by millimetres)."""
    rows = []
    for z in sorted(z for ops in openings.values() for o in ops for z in o[2:4]):
        if not rows or z - rows[-1][0] > ROW_SNAP_M:
            rows.append([z])
        else:
            rows[-1].append(z)
    reps = [float(np.median(r)) for r in rows]
    snap = lambda z: min(reps, key=lambda r: abs(r - z))                                # noqa: E731
    return {wi: [[o[0], o[1], snap(o[2]), snap(o[3])] for o in ops if snap(o[3]) - snap(o[2]) > 0.1]
            for wi, ops in openings.items()}


def spec_of(object_id, levels, stor, decks, railing_h, enclosure, inputs: Inputs) -> dict:
    """The spec of a building measured by its modules (user 2026-10-13: the spec rebuilt by modules): levels,
    a contour and openings per storey, no roof parapet (a textured band is no parapet), the terraces where a
    walkable deck lies, the roof screen enclosure. The contract the checkers measure the model against."""
    elev = dict(levels)
    floors = []
    for name, st in stor.items():
        pts = np.asarray(st["poly"].exterior.coords)[:-1]
        ops = [{"wall": wi, "x_m": round(o[0], 4), "w_m": round(o[1] - o[0], 4), "sill_m": round(o[2] - elev[name], 4),
                "h_m": round(o[3] - o[2], 4), "kind": "window", "source": "glass", "material_id": inputs.opening_id}
               for wi, os_ in sorted(st["openings"].items()) for o in os_]
        floors.append({"level": name, "contour": [[round(float(x), 4), round(float(y), 4)] for x, y in pts], "openings": ops})
    spec = {"id": object_id, "spec_version": "0.7" if enclosure is not None else "0.4", "profile": "npm_min",
            "frame": {"object": object_id, "source": "from-modules", "to_object": np.eye(4).tolist()},
            "levels": [{"name": n, "elev_m": z} for n, z in levels], "floors": floors, "roof": {"parapet_h_m": 0.0},
            "terraces": [{"level": n, "parapet_h_m": round(railing_h, 3)} for n in decks],
            "opening_depth_default_m": inputs.opening_depth_m, "weld_m": inputs.weld_m}
    if enclosure is not None:
        ring, z_top = enclosure
        spec["roof_structures"] = [{"kind": "screen", "outline": [[round(float(x), 4), round(float(y), 4)]
                                                                  for x, y in np.asarray(ring.exterior.coords)[:-1]],
                                    "z_top_m": round(z_top, 3)}]
    return spec


def drop_shared_faces(mesh: _Mesh) -> int:
    """Faces that occur more than once on the same vertices (two boxes or planes touching face to face) are inside
    the module: every copy is removed. Returns how many were removed."""
    seen = defaultdict(list)
    for k, (ids, _) in enumerate(mesh.faces):
        seen[tuple(sorted(ids))].append(k)
    gone = {k for ks in seen.values() if len(ks) > 1 for k in ks}
    mesh.faces = [f for k, f in enumerate(mesh.faces) if k not in gone]
    return len(gone)


# ---------------------------------------------------------------------------------------------- the build

BUILD_AS = ("slab_boxes", "deck_boxes", "walls", "openings_glass", "boxes", "planes", "boxes_seated",
            "planes_enclosure", "roof_band", "railings", "skip")
BALCONY_OFF_M = 0.3      # glass further than this off its storey's wall line is a railing, not a window
LIFT_M = RAILING_LIFT_M   # a part standing on another (a roof box, a band, a railing) stands this far off it
BAND_T_M = 0.04          # a textured band's thickness (the roof slat band, user 2026-10-13)


def _group(parts, keys):
    vs, ts, base = [], [], 0
    for k in keys:
        v, t, _ = parts[k]
        used, inv = np.unique(t, return_inverse=True)
        vs.append(v[used])
        ts.append(inv.reshape(-1, 3) + base)
        base += len(used)
    return (np.vstack(vs), np.vstack(ts)) if vs else (np.zeros((0, 3)), np.zeros((0, 3), int))


def build_from_modules(dump: dict, modules: dict, object_id: str, inputs: Inputs):
    """The building rebuilt by its source modules (see the module docstring), each module by its `build_as`.
    Returns (mesh dump, spec, report): the spec is measured by the same modules (user 2026-10-13) and is the
    contract the checkers use."""
    parts = module_tris(dump, modules)
    how = {}
    for mod in modules["modules"]:
        b = mod.get("build_as")
        if b not in BUILD_AS:
            raise BuildError(f"module {mod['module']} ({[p['source'] for p in mod['parts']]}): build_as {b!r} "
                             f"not in {BUILD_AS}")
        for p in mod["parts"]:
            how[p["source"]] = b

    def keys(b):
        return [k for k in parts if how[k] == b]

    def pid(k, default):
        return parts[k][2]["ids"].get(k, default)

    levels, elev = inputs.levels, dict(inputs.levels)
    rep, meshes = {}, {}

    def done(name, mesh, src_keys):
        removed = drop_shared_faces(mesh)
        d = mesh.mesh(name)
        if not d["triangles"]:
            return
        meshes[name] = d
        sv, st = _group(parts, src_keys)
        rep[name] = {**rep.get(name, {}),
                     "compare": compare(sv, st, d["vertices"], d["triangles"]) if len(st) else None,
                     "triangles": len(d["triangles"]), "quads": sum(1 for x in d["polygon_sizes"] if x == 4),
                     "tris": sum(1 for x in d["polygon_sizes"] if x == 3), "shared_faces_removed": removed}

    if len(keys("slab_boxes")) != 1:
        raise BuildError(f"one slab module is needed (build_as slab_boxes), got {keys('slab_boxes')}")
    sk = keys("slab_boxes")[0]
    slabs = slabs_of(*parts[sk][:2], levels)
    m, fb = _Mesh(), 0
    for _, top, under, outline in slabs:
        fb += slab_box(m, outline, top, under, pid(sk, 21), pid(sk, 21), pid(sk, 21))
    rep["slabs"] = {"slabs": [x[0] for x in slabs], "cdt_cells": fb}
    done("slabs", m, [sk])

    decks = []
    m, fb = _Mesh(), 0
    for k in keys("deck_boxes"):
        for name, top, under, outline in slabs_of(*parts[k][:2], levels):
            decks.append((name, top, outline))      # off the slab by plate_gap_m: a part of its own
            fb += slab_box(m, outline, top, (under if under is not None else top - 0.2) + 0.005,
                           pid(k, 22), pid(k, 22), pid(k, 22))
    rep["terraces"] = {"decks": [x[0] for x in decks], "cdt_cells": fb}
    done("terraces", m, keys("deck_boxes"))

    glass = keys("openings_glass")
    if len(glass) != 1:
        raise BuildError(f"one glass module is needed (build_as openings_glass), got {glass}")
    stor = _storeys(parts[glass[0]], slabs, levels, inputs)
    m, srep = _Mesh(), {}
    for name, st in stor.items():
        storey_walls(m, st["poly"], st["openings"], *st["z"], inputs)
        srep[name] = {"z": [round(z, 3) for z in st["z"]], "walls": len(st["poly"].exterior.coords) - 1,
                      "openings": sum(len(x) for x in st["openings"].values()), "area_m2": round(st["poly"].area, 1)}
    rep["walls"] = {"storeys": srep}
    done("walls", m, keys("walls") + glass)

    m, n_el, all_els = _Mesh(), {}, []
    centre = np.asarray(max(shapely.get_parts(slabs[0][3]), key=lambda g: g.area).centroid.coords[0])
    for k in keys("boxes"):
        v, t, _ = parts[k]
        mid = pid(k, 26)
        flat_t, t = split_flat(v, t)               # zero-thickness pieces are planes, not boxes
        kept = face_planes(m, v, flat_t, mid) if len(flat_t) else 0
        odd = []
        els = profile_elements(v, t, centre, odd=odd) if len(t) else []
        if odd:
            kept += face_planes(m, v, np.vstack(odd), mid)
        all_els += [tuple(e[:7]) + (mid,) for e in els]
        n_el[k] = {"elements": len(els), "flat_pieces": len(_pieces(v, flat_t)) if len(flat_t) else 0,
                   "off_axis_or_no_section": len(odd), "kept_as_triangles": kept}
    resolved, joints = resolve_joints(all_els)        # piers into bands, bands proud (user 2026-10-14)
    for e, caps in resolved:
        extrude(m, e, e[7], caps)
    rep.setdefault("decor", {})["joints"] = joints
    panels = 0
    for k in keys("planes"):                         # dark inserts: boxes set into the wall (user 2026-10-14)
        v, t, _ = parts[k]
        panels += inset_panels(m, v, t, stor, pid(k, 5))
    n_el["inset_panels"] = panels
    rep["decor"] = {**rep.get("decor", {}), "elements": n_el,
                    "elements_total": sum(x.get("elements", 0) for x in n_el.values() if isinstance(x, dict))}
    done("decor", m, keys("boxes") + keys("planes"))

    m, enclosure = _Mesh(), None
    for k in keys("planes_enclosure"):
        ev, et = parts[k][:2]
        q = ev[np.unique(et)]
        ring = footprint_ring(ev, et)
        planes_along(m, ring, float(q[:, 2].min()), float(q[:, 2].max()), pid(k, 24))   # no top: the source
                                                                                          # has none (user 2026-10-14)
        enclosure = (ring, float(q[:, 2].max()))
    for k in keys("boxes_seated"):
        for (o, u, nn), lo, hi in decor_elements(*parts[k][:2]):
            _box(m, (o, u, nn), (lo[0], lo[1], lo[2] + LIFT_M), hi, pid(k, 25))
    done("superstructure", m, keys("planes_enclosure") + keys("boxes_seated"))

    m = _Mesh()
    roof = next((o for n, _, _, o in slabs if n == levels[-1][0]), None)
    for k in keys("roof_band"):
        pv, pt = parts[k][:2]
        q = pv[np.unique(pt)]
        if roof is not None:                        # the band runs along the roof edge
            ring = orient(Polygon(max(shapely.get_parts(roof), key=lambda g: g.area).exterior).simplify(0.01), 1.0)
            band_box(m, ring, float(q[:, 2].min()) + LIFT_M, float(q[:, 2].max()), BAND_T_M, pid(k, 23))
    railing_h, plates = None, 0
    for k in keys("railings"):
        rv, rt = parts[k][:2]
        heights = [float(rv[np.unique(rt[pc])][:, 2].max()) - elev[n] for n, _, _ in decks for pc in _pieces(rv, rt)
                   if abs(float(rv[np.unique(rt[pc])][:, 2].min()) - elev[n]) <= 0.05]   # standing on a deck
        railing_h = float(np.median(heights)) if heights else None
        for n, top, deck in decks:
            if railing_h and n in stor:
                plates += terrace_railings(m, deck, stor[n]["poly"], top, railing_h, pid(k, 12))
    # glass standing off the wall line (a small balcony's railing): the same rule - one closed plate per free
    # side of its plan, from its foot to its top (pattern terrace, glass railings, user 2026-10-14)
    gv, gt = parts[glass[0]][:2]
    lines = {n: st["poly"] for n, st in stor.items()}
    groups = []
    for pc in _pieces(gv, gt):
        q = gv[np.unique(gt[pc])]
        zm = float(q[:, 2].mean())
        name = next((n for n, st in stor.items() if st["z"][0] - 0.3 <= zm <= st["z"][1] + 0.3), None)
        if name is None:
            continue
        far = float(shapely.distance(shapely.points(q[:, :2]), lines[name].exterior).max())   # its furthest point
        if far <= BALCONY_OFF_M:
            continue
        groups.append([name, q])
    merged = []                                     # panes of one balcony touch: one plan
    for name, q in groups:
        hit = next((g for g in merged if g[0] == name and
                    shapely.MultiPoint(g[1][:, :2]).distance(shapely.MultiPoint(q[:, :2])) <= 0.05), None)
        if hit is None:
            merged.append([name, q])
        else:
            hit[1] = np.vstack([hit[1], q])
    balconies = 0
    for name, q in merged:
        plan = shapely.MultiPoint(q[:, :2]).convex_hull
        if plan.geom_type != "Polygon" or plan.area < 0.05:
            continue
        z0, z1 = float(q[:, 2].min()), float(q[:, 2].max())
        balconies += terrace_railings(m, plan, lines[name], z0, z1 - z0, pid(glass[0], 12))   # 4 mm off its foot
    rep["parapets"] = {"railing_h_m": round(railing_h, 3) if railing_h else None, "railing_plates": plates,
                       "balcony_glass_plates": balconies}
    done("parapets", m, keys("roof_band") + keys("railings"))

    rep["skipped"] = {k: parts[k][2].get("build", "") for k in keys("skip")}
    spec = spec_of(object_id, levels, stor, [x[0] for x in decks] if railing_h else [], railing_h or 0.0,
                   enclosure, inputs)
    out = {"source": "from_source", "units": "m", "meshes": list(meshes.values()),
           "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]} for n, z in levels]}
    rep["triangles"] = sum(len(d["triangles"]) for d in meshes.values())
    return out, spec, rep


def load_modules(path) -> dict:
    return json.loads(open(path, encoding="utf-8").read())

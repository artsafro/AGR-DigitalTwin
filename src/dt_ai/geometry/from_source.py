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
        outline = shapely.union_all([f.buffer(1e-6) for f in faces if f.area > 0]).buffer(-1e-6)
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


def wall_openings(poly, glass_segs, glass_z, z_lo, z_hi, w):
    """Openings per wall of a storey from its glass: spans along the wall within EDGE_TOL_M of its line, panes
    closer than PANE_GAP_M one opening, kept WALL_END_M off the wall ends; heights from the glass parts."""
    pts = np.asarray(poly.exterior.coords)[:-1]
    out = defaultdict(list)
    for wi in range(len(pts)):
        a, b = pts[wi], pts[(wi + 1) % len(pts)]
        L = float(np.linalg.norm(b - a))
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
            s0, s1 = float(max(s.min(), WALL_END_M)), float(min(s.max(), L - WALL_END_M))
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
        n = np.cross(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]).sum(axis=0)
        ln = np.linalg.norm(n)
        thick = float(np.ptp(q.reshape(-1, 3) @ (n / ln))) if ln > 1e-12 else 0.0
        (flat if thick < thin else solid).append(t[pc])
    cat = lambda xs: np.vstack(xs) if xs else np.zeros((0, 3), int)                    # noqa: E731
    return cat(flat), cat(solid)


def decor_elements(v, t, seam=DECOR_SEAM_M):
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
            if m[0] != r[0] or abs(m[3] - r[3]) > seam or abs(m[4] - r[4]) > seam:
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
    for (*nn, off), ks in key.items():
        nn = np.asarray(nn, float)
        sub = t[ks]
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
            if area < 0.9 * (np.ptp(a1) * np.ptp(a2)):
                kept += 1
                for tri in q:
                    mesh.tri(tri.tolist(), mid, nn)
                continue
            o = nn * off
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

def storeys(parts, slabs, levels, inputs: Inputs):
    """Per storey (level name): its z range (top of the slab below to the underside of the slab above), its wall
    contour (the outline of the slab above - the storey's footprint) and its openings from the glass module."""
    gv, gt = next((v, t) for k, (v, t, m) in parts.items() if m["module"] == "glazing" and m["ids"].get(k) == inputs.opening_id)
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
                     "openings": snap_rows(wall_openings(poly, segs, gz, z_lo, z_hi, inputs.weld_m))}
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


def load_modules(path) -> dict:
    return json.loads(open(path, encoding="utf-8").read())

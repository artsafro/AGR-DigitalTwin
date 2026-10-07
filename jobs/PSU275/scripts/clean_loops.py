"""Remove edge loops that support no opening, corner or finish change (Blender port of the logic of
Desktop/zavod/scripts/mesh/clean_opening_grid.ms, user's 3ds Max tool).

Used by vpm_stage5.py between seal.seal and vpm_uv.texel_cut (env PSU275_CLEAN_LOOPS=1): texel_cut then adds
back only the uniform cuts the texel / 4 m rule needs, so the grid keeps only meaningful lines.

Keep (per coplanar face island = plane):
- open edges, creases (faces not coplanar), finish changes, edges next to explicit-UV faces (uvx) or
  next to non-rectangular quads (skewed caps would outgrow their UV tile once merged);
- interior edges on the U or V line of any border corner of an island in that plane (the quad frame of
  openings, outline corners, band ends); diagonal edges.
Remove: an edge loop (through 4-valent all-quad vertices) whose edges are all junk; an open loop only if its
end vertices are left collinear. Faces on both sides merge (two quad rows -> one), collinear 2-valent
vertices are dissolved, so the result stays all quads and T-free.
"""
import math

import bmesh
from mathutils import Vector

COS_PLANE = math.cos(math.radians(2.0))
DIST = 0.005        # coplanarity offset tolerance (m)
TOL = 0.02          # critical line tolerance (m)
STRAIGHT = -0.98    # border vertex is a corner when its two border edges are not straight


def _axes(n):
    u = Vector((0, 0, 1)).cross(n) if abs(n.z) < 0.9 else Vector((1, 0, 0))
    u.normalize()
    v = n.cross(u); v.normalize()
    return u, v


def _key(n, c):
    return (round(n.x, 2), round(n.y, 2), round(n.z, 2), round(n.dot(c), 1))


def _coplanar(f, g):
    return f.normal.dot(g.normal) > COS_PLANE and abs(f.normal.dot(g.calc_center_median() - f.calc_center_median())) < DIST


def _cluster(vals):
    out = []
    for x in sorted(vals):
        if out and x - out[-1] <= TOL:
            continue
        out.append(x)
    return out


def _near(x, crit):
    lo, hi = 0, len(crit)
    while lo < hi:  # bisect
        m = (lo + hi) // 2
        if crit[m] < x - TOL:
            lo = m + 1
        else:
            hi = m
    return lo < len(crit) and abs(crit[lo] - x) <= TOL


def build_grids(bm):
    """Critical U/V lines per plane key (union over islands of that plane)."""
    bm.faces.ensure_lookup_table()
    seen, grids = set(), {}
    for seed in bm.faces:
        if seed.index in seen:
            continue
        isl, stack = [], [seed]
        seen.add(seed.index)
        while stack:
            f = stack.pop(); isl.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen and _coplanar(seed, g):
                        seen.add(g.index); stack.append(g)
        ids = {f.index for f in isl}
        border = set()
        for f in isl:
            for e in f.edges:
                if sum(1 for g in e.link_faces if g.index in ids) == 1:
                    border.add(e)
        n = seed.normal.copy()
        u, v = _axes(n)
        bv = {}
        for e in border:
            for w in e.verts:
                bv.setdefault(w, []).append(e)
        us, vs = [], []
        for w, es in bv.items():
            corner = len(es) != 2
            if not corner:
                d1 = es[0].other_vert(w).co - w.co; d2 = es[1].other_vert(w).co - w.co
                corner = d1.length > 1e-6 and d2.length > 1e-6 and d1.normalized().dot(d2.normalized()) > STRAIGHT
            if corner:
                us.append(w.co.dot(u)); vs.append(w.co.dot(v))
        g = grids.setdefault(_key(n, seed.calc_center_median()), [u, v, [], []])
        g[2].extend(us); g[3].extend(vs)
    for g in grids.values():
        g[2] = _cluster(g[2]); g[3] = _cluster(g[3])
    return grids


def _rect(f):
    """Quad with right corners (skewed/mitred quads keep their cuts: merged they outgrow the UV tile)."""
    co = [v.co for v in f.verts]
    for i in range(4):
        d1 = (co[i - 1] - co[i]); d2 = (co[(i + 1) % 4] - co[i])
        if d1.length < 1e-6 or d2.length < 1e-6 or abs(d1.normalized().dot(d2.normalized())) > 0.01:
            return False
    return True


def is_junk(e, grids, fl, fx):
    if len(e.link_faces) != 2:
        return False
    f, g = e.link_faces
    if len(f.verts) != 4 or len(g.verts) != 4 or f[fl] != g[fl] or (fx and (f[fx] or g[fx])):
        return False
    if not _coplanar(f, g) or not _rect(f) or not _rect(g):
        return False
    grid = grids.get(_key(f.normal, f.calc_center_median()))
    if grid is None:
        return False  # plane not indexed (rounding at a key boundary) -> keep
    u, v, cu, cv = grid
    a, b = e.verts[0].co, e.verts[1].co
    du, dv = abs((b - a).dot(u)), abs((b - a).dot(v))
    if dv <= TOL and du > TOL:      # runs along U: a V line
        return not (_near(a.dot(v), cv) and _near(b.dot(v), cv))
    if du <= TOL and dv > TOL:      # runs along V: a U line
        return not (_near(a.dot(u), cu) and _near(b.dot(u), cu))
    return False                    # diagonal: keep


def _next(e, w):
    """Continuation of an edge loop through a 4-valent all-quad vertex, else None."""
    if len(w.link_edges) != 4 or any(len(f.verts) != 4 for f in w.link_faces):
        return None
    fs = set(e.link_faces)
    for x in w.link_edges:
        if x is not e and not (set(x.link_faces) & fs):
            return x
    return None


def trace(e):
    """Edge loop through e: (edges, end vertices or [] when closed)."""
    loop, ends = [e], []
    for start in e.verts:
        cur, w = e, start
        while True:
            nx = _next(cur, w)
            if nx is None:
                ends.append(w); break
            if nx is e:
                return loop, []
            loop.append(nx)
            cur, w = nx, nx.other_vert(w)
    return loop, ends


def _straight_after(w, loop_edges):
    rest = [x for x in w.link_edges if x not in loop_edges]
    if len(rest) != 2:
        return False
    d1 = rest[0].other_vert(w).co - w.co; d2 = rest[1].other_vert(w).co - w.co
    return d1.length > 1e-6 and d2.length > 1e-6 and d1.normalized().dot(d2.normalized()) < -0.9998


def clean(bm, log=None):
    """Remove junk loops in place. Returns stats."""
    fl = bm.faces.layers.int["finish"]
    fx = bm.faces.layers.int.get("uvx")
    bm.normal_update()
    grids = build_grids(bm)
    f0, removed, failed = len(bm.faces), 0, set()
    for _ in range(100):
        progress = False
        for e in list(bm.edges):
            if not e.is_valid or e in failed or not is_junk(e, grids, fl, fx):
                continue
            loop, ends = trace(e)
            ls = set(loop)
            ok = all(is_junk(x, grids, fl, fx) for x in loop) and all(_straight_after(w, ls) for w in ends)
            if not ok:
                failed.update(ls)
                continue
            verts = {w for x in loop for w in x.verts}
            bmesh.ops.dissolve_edges(bm, edges=loop, use_verts=False, use_face_split=False)
            lone = [w for w in verts if w.is_valid and len(w.link_edges) == 2 and _straight_after(w, set())]
            if lone:
                bmesh.ops.dissolve_verts(bm, verts=lone)
            removed += 1; progress = True
        bm.normal_update()
        failed = {x for x in failed if x.is_valid}
        if not progress:
            break
    stats = {"loops_removed": removed, "faces": [f0, len(bm.faces)],
             "non_quads": sum(len(f.verts) != 4 for f in bm.faces), "planes": len(grids)}
    if log is not None:
        log.append(stats)
    return stats

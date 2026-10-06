"""Seal the KPP1 master mesh: no T-junctions, no near-coincident vertices, quads only.

Separate builder pieces meet with T-junctions (a vertex of one piece lies on an edge of another).
Rasterisers leave hairline cracks there. The fix keeps 100 % quads (docs/domain/geometry.md:
"no split seams or T-junctions", "propagate opposite-edge splits until converged, no fans"):

1. weld vertices closer than WELD (2.5 mm; SINTEZ counts doubles at 2 mm; deliberate offsets are
   >= 5 mm, so nothing real collapses; cuts closer than WELD along a ring are clustered first, so
   no strip thinner than WELD is ever created);
2. find T-junctions (vertex within TOL of the interior of an edge it does not belong to);
3. split every edge ring (chain of opposite quad edges) at all required parameters and rebuild its
   quads as non-uniform grids (bilinear points and UVs), so the cut runs across the ring and ends on a
   boundary or on the far side of the same seam -> no new T-junctions inside the mesh;
4. triangles become three quads (centroid + edge midpoints; the midpoints propagate as ring cuts);
5. repeat until no T-junction is left.

Face layers `finish`, `uvx` and the loop UV layer `UVM` are carried over.
"""
import bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree

WELD = 0.0025     # > SINTEZ doubles distance (2 mm); also the cut clustering distance
TOL = 0.001
MERGE_T = WELD    # cuts closer than this along a ring are one cut (single linkage, cluster mean)


def _rings(bm):
    """Union-find over quad opposite edges. Returns (root_of(edge_index), start vertex per edge, flipped roots)."""
    bm.edges.index_update()
    parent = list(range(len(bm.edges)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    quads = [f for f in bm.faces if len(f.loops) == 4]
    for f in quads:
        ls = list(f.loops)
        for a, b in ((0, 2), (1, 3)):
            ra, rb = find(ls[a].edge.index), find(ls[b].edge.index)
            if ra != rb:
                parent[ra] = rb
    # canonical start vertex per edge by BFS through quads
    start = {}
    bad = set()
    adj = {}
    for f in quads:
        ls = list(f.loops)
        for a, b in ((0, 2), (1, 3), (2, 0), (3, 1)):
            adj.setdefault(ls[a].edge.index, []).append((ls[a], ls[b]))
    for e in bm.edges:
        if e.index in start:
            continue
        start[e.index] = e.verts[0]
        stack = [e.index]
        while stack:
            i = stack.pop()
            for l, lo in adj.get(i, []):
                # l runs l.vert -> next; the opposite loop runs reversed
                s = lo.link_loop_next.vert if start[i] == l.vert else lo.vert
                j = lo.edge.index
                if j not in start:
                    start[j] = s
                    stack.append(j)
                elif start[j] != s:
                    bad.add(find(i))
    return find, start, bad


def t_junctions(bm, tol=TOL, seams_only=False):
    """{edge_index: [point]} for vertices lying on the interior of edges they do not belong to.
    seams_only: only open (boundary) edges and boundary vertices -> the joints between pieces where a
    crack can open; a vertex resting on the inside of a continuous surface cannot crack it."""
    bm.verts.index_update()
    bm.verts.ensure_lookup_table()
    bm.edges.index_update()
    kd = KDTree(len(bm.verts))
    for v in bm.verts:
        kd.insert(v.co, v.index)
    kd.balance()
    out = {}
    for e in bm.edges:
        a, b = e.verts[0].co, e.verts[1].co
        ab = b - a
        L2 = ab.length_squared
        if L2 < 1e-12:
            continue
        open_e = len(e.link_faces) == 1
        dn = ab.normalized()
        for co, idx, _ in kd.find_range((a + b) / 2, ab.length / 2 + tol):
            v = bm.verts[idx]
            if v in e.verts:
                continue
            if seams_only:
                # a seam = two open borders running along each other (edge-to-edge joint). Parts that
                # stand on or run into another surface are embedded instead, never split or welded.
                if not open_e or not any(len(x.link_faces) == 1 and
                                         abs((x.other_vert(v).co - v.co).normalized().dot(dn)) > 0.999
                                         for x in v.link_edges):
                    continue
            t = (co - a).dot(ab) / L2
            if t * ab.length <= tol or (1 - t) * ab.length <= tol:
                continue
            if (a + ab * t - co).length < tol:
                out.setdefault(e.index, []).append(co.copy())
    return out


def ring_split(bm, cuts, quadify_tris=True):
    """Rebuild bm with every edge ring split at the union of its cut parameters.
    cuts: {edge_index: [world point on the edge]}."""
    find, start, bad = _rings(bm)
    fl = bm.faces.layers.int.get("finish")
    fx = bm.faces.layers.int.get("uvx")
    uvm = bm.loops.layers.uv.get("UVM")
    if quadify_tris:
        for f in bm.faces:
            if len(f.loops) == 3:
                for e in f.edges:
                    cuts.setdefault(e.index, []).append((e.verts[0].co + e.verts[1].co) / 2)
    # ring parameters measured from the canonical start vertex
    ring_t = {}
    bm.edges.ensure_lookup_table()
    for ei, pts in cuts.items():
        e = bm.edges[ei]
        s = start[ei]
        a, b = s.co, e.other_vert(s).co
        L = (b - a).length
        r = find(ei)
        for p in pts:
            t = (p - a).dot(b - a) / (L * L)
            ring_t.setdefault(r, []).append(t)
            if r in bad:
                ring_t[r].append(1 - t)

    # one clustered parameter list per ring (canonical orientation), measured on the ring's shortest edge
    ring_len = {}
    for e in bm.edges:
        r = find(e.index)
        ring_len[r] = min(ring_len.get(r, 1e9), e.calc_length())
    ring_p = {}
    for r, ts in ring_t.items():
        L = ring_len[r]
        ts = sorted(t for t in ts if t * L > MERGE_T and (1 - t) * L > MERGE_T)
        groups = []
        for t in ts:
            if groups and (t - groups[-1][-1]) * L <= MERGE_T:
                groups[-1].append(t)
            else:
                groups.append([t])
        ring_p[r] = [sum(g) / len(g) for g in groups]

    def params(e, from_vert):
        """Sorted interior split parameters of e measured from from_vert."""
        ts = ring_p.get(find(e.index))
        if not ts:
            return []
        flip = from_vert != start[e.index]
        return sorted((1 - t) if flip else t for t in ts)

    nb = bmesh.new()
    nfl = nb.faces.layers.int.new("finish")
    nfx = nb.faces.layers.int.new("uvx")
    nuv = nb.loops.layers.uv.new("UVM")
    vmap = {}

    def vert(key, co):
        if key not in vmap:
            vmap[key] = nb.verts.new(co)
        return vmap[key]

    def old(v):
        return vert(("v", v.index), v.co)

    def epoint(e, from_vert, t):
        """Shared vertex on old edge e at parameter t from from_vert."""
        tc = t if from_vert == e.verts[0] else 1 - t
        a, b = e.verts[0].co, e.verts[1].co
        return vert(("e", e.index, round(tc, 9)), a.lerp(b, tc))

    def face(vs, uvs, f):
        try:
            nf = nb.faces.new(vs)
        except ValueError:
            return
        for l, uv in zip(nf.loops, uvs):
            l[nuv].uv = uv
        nf[nfl] = f[fl] if fl else 0
        nf[nfx] = f[fx] if fx else 0

    bm.verts.index_update()
    for f in bm.faces:
        ls = list(f.loops)
        uv0 = [l[uvm].uv.copy() if uvm else Vector((0, 0)) for l in ls]
        if len(ls) == 4:
            v = [l.vert.co for l in ls]
            S = [0.0] + params(ls[0].edge, ls[0].vert) + [1.0]
            T = [0.0] + params(ls[3].edge, ls[0].vert) + [1.0]
            # opposite edges share the ring, so their params coincide with S/T (canonical mapping)
            P = lambda s, t: (1 - s) * (1 - t) * v[0] + s * (1 - t) * v[1] + s * t * v[2] + (1 - s) * t * v[3]
            U = lambda s, t: (1 - s) * (1 - t) * uv0[0] + s * (1 - t) * uv0[1] + s * t * uv0[2] + (1 - s) * t * uv0[3]
            grid = {}
            ni, nj = len(S) - 1, len(T) - 1
            for i, s in enumerate(S):
                for j, t in enumerate(T):
                    corner = {(0, 0): 0, (ni, 0): 1, (ni, nj): 2, (0, nj): 3}.get((i, j))
                    if corner is not None:
                        vv = old(ls[corner].vert)
                    elif j == 0:
                        vv = epoint(ls[0].edge, ls[0].vert, s)
                    elif j == nj:
                        vv = epoint(ls[2].edge, ls[3].vert, s)
                    elif i == 0:
                        vv = epoint(ls[3].edge, ls[0].vert, t)
                    elif i == ni:
                        vv = epoint(ls[1].edge, ls[1].vert, t)
                    else:
                        vv = nb.verts.new(P(s, t))
                    grid[(i, j)] = (vv, U(s, t))
            for i in range(ni):
                for j in range(nj):
                    cs = [grid[(i, j)], grid[(i + 1, j)], grid[(i + 1, j + 1)], grid[(i, j + 1)]]
                    face([c[0] for c in cs], [c[1] for c in cs], f)
            continue
        # non-quads: boundary with all edge points
        ring = []  # (vert, uv, is_corner, corner_index)
        for k, l in enumerate(ls):
            ring.append((old(l.vert), uv0[k], k))
            ua, ub = uv0[k], uv0[(k + 1) % len(ls)]
            for t in params(l.edge, l.vert):
                ring.append((epoint(l.edge, l.vert, t), ua.lerp(ub, t), None))
        if len(ls) == 3 and quadify_tris:
            c = sum((l.vert.co for l in ls), Vector()) / 3
            cuv = sum(uv0, Vector((0, 0))) / 3
            cv = nb.verts.new(c)
            corners = [i for i, r in enumerate(ring) if r[2] is not None]
            n = len(ring)
            for ci in corners:
                k = ring[ci][2]
                nxt = _closest_mid(ring, ci, +1, ls, k)
                prv = _closest_mid(ring, ci, -1, ls, (k - 1) % 3)
                if nxt is None or prv is None:
                    print("SEAL-DEBUG tri", [tuple(round(c, 4) for c in l.vert.co) for l in ls],
                          [(r[2], tuple(round(c, 4) for c in r[0].co)) for r in ring],
                          [find(l.edge.index) in ring_t for l in ls], [l.edge.calc_length() for l in ls])
                    raise RuntimeError("tri quadify")
                seq = []
                i = prv
                while True:
                    seq.append(ring[i])
                    if i == nxt:
                        break
                    i = (i + 1) % n
                face([cv] + [r[0] for r in seq], [cuv] + [r[1] for r in seq], f)
        else:
            face([r[0] for r in ring], [r[1] for r in ring], f)
    bm.free()
    nb.normal_update()
    return nb


def _closest_mid(ring, ci, step, ls, edge_k):
    """Index in ring of the midpoint (t = 0.5) of triangle edge edge_k, walking from corner ci."""
    a, b = ls[edge_k].vert.co, ls[edge_k].link_loop_next.vert.co
    m = (a + b) / 2
    n = len(ring)
    best, bd = None, 1e9
    i = ci
    for _ in range(n):
        i = (i + step) % n
        if ring[i][2] is not None:
            break
        d = (ring[i][0].co - m).length
        if d < bd:
            best, bd = i, d
    return best


def quadify(bm, log=None):
    """Turn triangles into three quads each (centroid + midpoints; midpoints run as ring cuts)."""
    for _ in range(4):
        tris = sum(len(f.loops) == 3 for f in bm.faces)
        if log is not None:
            log.append({"quadify_tris": tris})
        if not tris:
            break
        bm = ring_split(bm, {})
    return bm


def weld(bm, dist=WELD):
    """Weld open-border vertices only (seams). A vertex inside a surface is never merged with a part
    touching it: that would give edges with 3+ faces (3ds Max splits them into overlapping vertices)."""
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if v.is_boundary], dist=dist)
    return n0 - len(bm.verts)


def seal(bm, max_iter=12, log=None):
    """Split seam T-junctions inside each piece (rings do not cross unwelded joints, so cuts stay local),
    iterate to convergence, then weld the seams once. Returns the new bmesh."""
    log = log if log is not None else []
    for it in range(max_iter):
        tj = t_junctions(bm, seams_only=True)
        tris = sum(len(f.loops) == 3 for f in bm.faces)
        log.append({"iter": it, "seam_t_edges": len(tj), "tris": tris, "faces": len(bm.faces)})
        if not tj and not tris:
            break
        bm = ring_split(bm, tj)
    welded = weld(bm)
    left = t_junctions(bm)
    log.append({"final_weld": welded, "t_edges_left_all": len(left),
                "seam_t_edges_left": len(t_junctions(bm, seams_only=True)), "faces": len(bm.faces),
                "non_quads": sum(len(f.loops) != 4 for f in bm.faces)})
    bm.normal_update()
    return bm

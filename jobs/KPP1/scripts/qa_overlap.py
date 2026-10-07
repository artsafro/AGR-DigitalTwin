"""Overlapping faces / vertices like 3ds Max xView (Overlapping Faces tol 0.005, Overlapping Vertices 0.002).

overlap_pairs(bm): pairs of faces whose planes are parallel (|cos| > COS), closer than TOL along the
normal (both ways) and whose projections overlap with area > MIN_AREA (convex polygons, Sutherland-
Hodgman clip). Same and opposite facing both count (xView flags back-to-back contact too).
non_manifold(bm): edges with > 2 faces; 3ds Max Editable Poly cannot hold them and splits vertices on
import, which then shows up as overlapping vertices.
Standalone: blender --background <file.blend> --python qa_overlap.py -- <out.json> [object ...]
"""
import bmesh
from mathutils import Vector

TOL = 0.005
COS = 0.9998
MIN_AREA = 1e-6
CELL = 0.5


def _clip(subject, clip):
    """Sutherland-Hodgman: subject polygon clipped by convex clip polygon (2D, CCW)."""
    out = subject
    n = len(clip)
    for i in range(n):
        a, b = clip[i], clip[(i + 1) % n]
        inp, out = out, []
        if not inp:
            break
        side = lambda p: (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x)
        for j in range(len(inp)):
            p, q = inp[j], inp[(j + 1) % len(inp)]
            sp, sq = side(p), side(q)
            if sp >= 0:
                out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq)
                out.append(p + (q - p) * t)
    return out


def _seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-18)))
    return (a + ab * t - p).length


def _dist2d(A, B):
    """Minimum distance between two non-overlapping convex polygons (vertex to edge, both ways)."""
    d = 1e9
    for P, Q in ((A, B), (B, A)):
        for p in P:
            for k in range(len(Q)):
                d = min(d, _seg_dist(p, Q[k], Q[(k + 1) % len(Q)]))
    return d


def _area(poly):
    return 0.5 * sum(poly[i].x * poly[(i + 1) % len(poly)].y - poly[(i + 1) % len(poly)].x * poly[i].y
                     for i in range(len(poly)))


def overlap_pairs(bm, tol=TOL):
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    grid = {}
    data = []
    for f in bm.faces:
        pts = [v.co.copy() for v in f.verts]
        lo = Vector([min(p[i] for p in pts) - tol for i in range(3)])
        hi = Vector([max(p[i] for p in pts) + tol for i in range(3)])
        data.append((pts, f.normal.copy(), f.calc_center_median(), lo, hi))
        for x in range(int(lo.x // CELL), int(hi.x // CELL) + 1):
            for y in range(int(lo.y // CELL), int(hi.y // CELL) + 1):
                for z in range(int(lo.z // CELL), int(hi.z // CELL) + 1):
                    grid.setdefault((x, y, z), []).append(f.index)
    seen, pairs = set(), []
    for cell in grid.values():
        for a_i in range(len(cell)):
            i = cell[a_i]
            pi, ni, ci, loi, hii = data[i]
            for j in cell[a_i + 1:]:
                key = (i, j) if i < j else (j, i)
                if key in seen:
                    continue
                seen.add(key)
                pj, nj, cj, loj, hij = data[j]
                if any(loi[k] > hij[k] or loj[k] > hii[k] for k in range(3)):
                    continue
                if abs(ni.dot(nj)) < COS:
                    continue
                if abs(ni.dot(cj - ci)) > tol or abs(nj.dot(ci - cj)) > tol:
                    continue
                # project onto face i's plane
                u = (pi[1] - pi[0]).normalized()
                w = ni.cross(u)
                P = lambda p: Vector(((p - ci).dot(u), (p - ci).dot(w)))
                A = [P(p) for p in pi]
                B = [P(p) for p in pj]
                if _area(A) < 0:
                    A.reverse()
                if _area(B) < 0:
                    B.reverse()
                inter = _clip(B, A)
                if len(inter) >= 3 and abs(_area(inter)) > 1e-6:
                    pairs.append((i, j, round(abs(_area(inter)), 6)))
                elif not (set(bm.faces[i].verts) & set(bm.faces[j].verts)) and _dist2d(A, B) < 1e-5:
                    pairs.append((i, j, 0.0))  # coplanar faces of different parts touching (xView counts them)
    return pairs


def non_manifold(bm):
    return [e for e in bm.edges if len(e.link_faces) > 2]


def doubles(bm, dist=0.002):
    return len(bmesh.ops.find_doubles(bm, verts=bm.verts, dist=dist)["targetmap"])


if __name__ == "__main__":
    import bpy, sys, json, collections
    args = sys.argv[sys.argv.index("--") + 1:]
    out, names = args[0], args[1:]
    rep = {}
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or (names and o.name not in names) or o.name.startswith("UCX_"):
            continue
        if any(c.name.startswith("REF_") for c in o.users_collection):
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.transform(o.matrix_world)
        fl = bm.faces.layers.int.get("finish")
        fn = o.get("finish_names", "").split(",")
        pairs = overlap_pairs(bm)
        nm = non_manifold(bm)
        groups = collections.Counter()
        samples = []
        bm.faces.ensure_lookup_table()
        for i, j, a in pairs:
            fi, fj = bm.faces[i], bm.faces[j]
            name = lambda f: fn[f[fl]] if fl is not None and f[fl] < len(fn) else "?"
            k = tuple(sorted((name(fi), name(fj))))
            groups[k] += 1
            if len(samples) < 200:
                samples.append([name(fi), name(fj), [round(x, 3) for x in fi.calc_center_median()],
                                [round(x, 3) for x in fj.calc_center_median()],
                                [round(x, 2) for x in fi.normal], [round(x, 2) for x in fj.normal], a])
        rep[o.name] = {"overlap_pairs": len(pairs), "overlap_faces": len({x for p in pairs for x in p[:2]}),
                       "non_manifold_edges": len(nm), "doubles_2mm": doubles(bm),
                       "non_manifold_samples": [[round(x, 3) for x in ((e.verts[0].co + e.verts[1].co) / 2)] for e in nm[:60]],
                       "groups": {" | ".join(k): v for k, v in groups.items()}, "samples": samples}
        bm.free()
        print("OVERLAP", o.name, {k: v for k, v in rep[o.name].items() if k in ("overlap_pairs", "overlap_faces", "non_manifold_edges", "doubles_2mm")})
        for k, v in groups.most_common(30):
            print("   ", v, k)
    json.dump(rep, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

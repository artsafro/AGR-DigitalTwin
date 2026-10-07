"""Separate OKS next to the PSU275 main building, rebuilt by parameters measured on S3 (Главное.fbx).

    uv run --with scipy python jobs/PSU275/scripts/build_oks_extras.py <extras_points.npz> <out_dir>

User decisions 2026-10-07: chimney, gas ducts, transformer and tanks are separate OKS (own SM_<A> package,
addresses Psu_2.. continue the main Psu_1); racks skipped (absent in S3); tanks rebuilt as full cylinders
to the ground. Local frame as the other PSU275 scripts (0.000 = 169.65). Measurements:
outputs/extras_measure_v001.json, islands_v001.json, extras_points_v001.npz, handrail_points_v001.npz.

- chimney (Psu_2): shaft R 6.70 / flue R 6.00, 0..120, centre (4.818, 110.791); signal bands RAL 3020 at
  32.685-46.734, 70.79-84.84, 105.908-120 (S3 Cylinder004-006; the 4 cm white strip at the top is dropped),
  rest RAL 9016 (S4 schedule). Platform 105.883-105.983 to R 8.506, railing ring R 8.37, 1.0 m high.
  Flue closed by a soot-coloured floor 6 m below the top. 32 segments.
- gas ducts (Psu_3): Ø4 tubes (16 sides) on measured centrelines, axis z 5.798, bends R 3.5 in 3 segments
  (mitred rings). Lower ducts start in the main north wall (y 54.28, embed 11 mm) with the S3 cone
  Ø8 -> Ø4 (y 54.0-58.0), run north and turn east into the duct buildings (embed 11 mm). The upper U duct
  joins both chimney inlets; the two S3 halves (11 cm gap at x 4.82) are joined into one tube; its ends
  stop inside the chimney wall. Duct buildings: boxes 0..10.032 (S3 'здание с трубами'), supports:
  4 boxes 0..3.321.
- transformer (Psu_4): S3 surfaces voxelised at 0.25 m, interior filled, made well-composed (no edge/vertex
  only contacts -> manifold), one quad per voxel face. UCX: greedy boxes over 1.0 m blocks.
- tanks (Psu_5): 3 cylinders R 4.895, 0..11.973 (S3 holds only the 1.3 m roof part), railing ring R 4.68,
  0.937 m high on the roof.
Colours of ducts, buildings, transformer, tanks and platform are proposals (no source colour).
Railing planes: double alpha planes 8 mm apart (KPP1 rule); UV v scaled so the 1.2 m texture pattern
fits the measured height.
Output per OKS: <out>/<key>.json {address, mesh, finishes, uvm, ucx (convex point sets), report}.
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import ndimage

EMBED, GAP, UCX_SHRINK = 0.011, 0.008, 0.002


class Piece:
    def __init__(self, address):
        self.address = address
        self.verts, self.faces, self.fins, self.uvms, self.lookup, self.ucx = [], [], [], [], {}, []

    def face(self, pts, finish, normal=None, uv=None):
        q = np.array(pts, float)
        if normal is not None and np.dot(newell(q), normal) < 0:
            q = q[::-1]
            uv = uv[::-1] if uv is not None else None
        idx = []
        for p in q:
            k = tuple(np.round(p, 5))
            if k not in self.lookup:
                self.lookup[k] = len(self.verts); self.verts.append(p.tolist())
            idx.append(self.lookup[k])
        self.faces.append(idx); self.fins.append(finish); self.uvms.append(uv)

    def box(self, lo, hi, finish, top=None, ucx=True):
        x0, y0, z0 = lo; x1, y1, z1 = hi
        c = np.array([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
        P = [[(x, y, z) for x in (x0, x1) for y in (y0, y1)] for z in (z0, z1)]
        quads = [([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], top or finish),
                 ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], finish),
                 ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], finish),
                 ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], finish),
                 ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], finish),
                 ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], finish)]
        for q, f in quads:
            q = np.array(q, float)
            self.face(q, f, q.mean(0) - c)
        if ucx:
            self.hull(P[0] + P[1])

    def hull(self, pts):
        p = np.array(pts, float); c = p.mean(0)
        d = p - c
        n = np.linalg.norm(d, axis=1, keepdims=True)
        self.ucx.append((p - d / np.maximum(n, 1e-9) * UCX_SHRINK).round(5).tolist())

    def save(self, path, report):
        path.write_text(json.dumps({"address": self.address, "mesh": {"name": self.address, "vertices": self.verts,
                                                                      "faces": self.faces},
                                    "finishes": self.fins, "uvm": self.uvms, "ucx": self.ucx, "report": report},
                                   ensure_ascii=False), encoding="utf-8")
        return {"faces": len(self.faces), "tris": 2 * len(self.faces), "ucx": len(self.ucx),
                "finishes": dict(Counter(self.fins))}


def newell(q):
    n = np.zeros(3)
    for a, b in zip(q, np.roll(q, -1, 0)):
        n += np.cross(a, b)
    return n


def ring(c, r, z, n, phase=0.0):
    a = phase + 2 * np.pi * np.arange(n) / n
    return np.stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a), np.full(n, z)], 1)


def wall(pc, c, r, z0, z1, n, finish, outward=True):
    lo, hi = ring(c, r, z0, n), ring(c, r, z1, n)
    for i in range(n):
        j = (i + 1) % n
        q = [lo[i], lo[j], hi[j], hi[i]]
        m = np.mean(q, 0) - [c[0], c[1], (z0 + z1) / 2]
        pc.face(q, finish, m if outward else -m)


def disc(pc, c, r, z, n, finish, up, r_in=0.0):
    """Annulus r..r_in (or r..r/2) plus a fan of quads in the middle (all quads, radial < 3.9 m)."""
    nz = np.array([0, 0, 1.0 if up else -1.0])
    mid = r_in if r_in else r / 2
    o, i_ = ring(c, r, z, n), ring(c, mid, z, n)
    for k in range(n):
        j = (k + 1) % n
        pc.face([o[k], o[j], i_[j], i_[k]], finish, nz)
    if r_in:
        return
    cc = np.array([c[0], c[1], z])
    for k in range(0, n, 2):
        pc.face([cc, i_[k], i_[(k + 1) % n], i_[(k + 2) % n]], finish, nz)


def railing_ring(pc, c, r, z0, h, n, finish="Railing_Alpha_RAL1021"):
    """Double alpha ring (8 mm apart, outer faces out, inner faces in), u = arc length, v = 0.05 + 1.2 z/h."""
    seg = 2 * r * math.sin(math.pi / n)
    for s in (+1, -1):
        rr = r + s * GAP / 2
        ph = math.pi / n                                    # posts between the radial edges of the deck (no T)
        lo, hi = ring(c, rr, z0, n, ph), ring(c, rr, z0 + h, n, ph)
        for i in range(n):
            j = (i + 1) % n
            u0 = i * seg
            q = [lo[i], lo[j], hi[j], hi[i]]
            uv = [(u0, 0.05), (u0 + seg, 0.05), (u0 + seg, 1.25), (u0, 1.25)]
            m = np.mean(q, 0) - [c[0], c[1], z0 + h / 2]
            pc.face(q, finish, m * s, uv)


# ------------------------------------------------------------------ chimney
def chimney(out):
    pc = Piece("Psu_2")
    C, R, RI, N, TOP = (4.818, 110.791), 6.70, 6.00, 32, 120.0
    W, RED = "Concrete_RAL9016", "Paint_RAL3020"
    levels = [(0.0, W), (32.685, RED), (46.734, W), (70.79, RED), (84.84, W), (105.908, RED)]
    for k, (z0, f) in enumerate(levels):
        z1 = levels[k + 1][0] if k + 1 < len(levels) else TOP
        wall(pc, C, R, z0, z1, N, f)
    disc(pc, C, R, TOP, N, RED, True, r_in=RI)            # top annulus
    wall(pc, C, RI, TOP - 6.0, TOP, N, "Soot_Dark", outward=False)
    disc(pc, C, RI, TOP - 6.0, N, "Soot_Dark", True)       # flue floor (closes the solid)
    disc(pc, C, R, 0.0, N, W, False)
    # platform: annulus slab embedded 11 mm into the shaft, railing ring on top
    PZ0, PZ1, PR = 105.883, 105.983, 8.506
    wall(pc, C, PR, PZ0, PZ1, N, "Grating_RAL7004")
    wall(pc, C, R - EMBED, PZ0, PZ1, N, "Grating_RAL7004", outward=False)
    disc(pc, C, PR, PZ1, N, "Grating_RAL7004", True, r_in=R - EMBED)
    disc(pc, C, PR, PZ0, N, "Grating_RAL7004", False, r_in=R - EMBED)
    railing_ring(pc, C, 8.37, PZ1, 1.0, N)
    # UCX: shaft below / above the platform and the platform disc, 2 mm apart
    pc.hull(np.vstack([ring(C, R, 0.0, N), ring(C, R, PZ0 - 0.001, N)]))
    pc.hull(np.vstack([ring(C, PR, PZ0 + 0.001, N), ring(C, PR, PZ1 - 0.001, N)]))
    pc.hull(np.vstack([ring(C, R, PZ1 + 0.001, N), ring(C, R, TOP, N)]))
    return pc.save(out / "chimney.json", {"centre": C, "R": R, "R_flue": RI, "top": TOP, "bands_RAL3020": levels})


# ------------------------------------------------------------------ gas ducts
def fillet(pts, rb, nseg=3):
    """Polyline with 90-degree (or any) corners replaced by arcs of radius rb (nseg segments)."""
    out = [np.array(pts[0], float)]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        a, b, c = map(lambda p: np.array(p, float), (a, b, c))
        d0 = (b - a) / np.linalg.norm(b - a); d1 = (c - b) / np.linalg.norm(c - b)
        th = math.acos(np.clip(np.dot(d0, d1), -1, 1))
        t = rb * math.tan(th / 2)
        p0, p1 = b - d0 * t, b + d1 * t
        nrm = d1 - d0; nrm /= np.linalg.norm(nrm)
        ctr = b + nrm * (rb / math.cos(th / 2))
        v0, v1 = p0 - ctr, p1 - ctr
        for k in range(nseg + 1):
            s = k / nseg
            ang = th * s
            # slerp between v0 and v1 around the arc centre
            v = (math.sin((1 - s) * th) * v0 + math.sin(s * th) * v1) / math.sin(th)
            out.append(ctr + v)
    out.append(np.array(pts[-1], float))
    return out


def tube(pc, stations, radii, n, finish, z, caps=True, ucx_trim_end=0.0):
    """Sweep a horizontal-axis polygon along plan stations (x, y) at height z; mitred rings at joints.
    ucx_trim_end: the last hull stops this far before the tube end (end embedded in a box of the same OKS)."""
    P = [np.array([s[0], s[1], z]) for s in stations]
    rings = []
    for k, p in enumerate(P):
        a = P[k] - P[k - 1] if k else P[1] - P[0]
        b = P[k + 1] - P[k] if k + 1 < len(P) else a
        a /= np.linalg.norm(a); b /= np.linalg.norm(b)
        e1 = np.cross(a, [0, 0, 1.0]); e1 /= np.linalg.norm(e1)
        m = a + b; m /= np.linalg.norm(m)
        pts = []
        for i in range(n):
            th = 2 * np.pi * (i + 0.5) / n
            q = p + radii[k] * (e1 * math.cos(th) + np.array([0, 0, 1.0]) * math.sin(th))
            q = q - a * np.dot(q - p, m) / np.dot(a, m)        # project onto the mitre plane
            pts.append(q)
        rings.append(np.array(pts))
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        axis = (P[k] + P[k + 1]) / 2
        for i in range(n):
            j = (i + 1) % n
            q = [A[i], A[j], B[j], B[i]]
            pc.face(q, finish, np.mean(q, 0) - axis)
        if k == len(rings) - 2 and ucx_trim_end:
            d = (P[-1] - P[-2]) / np.linalg.norm(P[-1] - P[-2])
            B = B - d * ucx_trim_end
        pc.hull(np.vstack([A, B]))
    if caps:
        for k, sgn in ((0, -1), (len(rings) - 1, 1)):
            d = P[1] - P[0] if k == 0 else P[-1] - P[-2]
            d = d / np.linalg.norm(d) * sgn
            R_ = rings[k]; cc = P[k]
            for i in range(0, n, 2):
                pc.face([cc, R_[i], R_[(i + 1) % n], R_[(i + 2) % n]], finish, d)


def ducts(out):
    pc = Piece("Psu_3")
    Z, R, N, RB, AX = 5.798, 2.0, 16, 3.5, 4.818
    D = "Duct_RAL9006"
    mirror = lambda pts: [(2 * AX - x, y) for x, y in pts]
    wall_y, bld_x = 54.28, -5.311
    # lower ducts: wall -> cone end -> corner -> duct building wall
    y0 = wall_y - EMBED
    lower = [(-13.254, y0), (-13.254, 58.0), (-13.254, 71.339), (bld_x + EMBED, 71.339)]
    for pts in (lower, mirror(lower)):
        st = [np.array(pts[0]), np.array(pts[1])] + fillet(pts[1:], RB)[1:]
        r0 = 4.0 - (y0 - 54.0) * 0.5
        tube(pc, st, [r0] + [R] * (len(st) - 1), N, D, Z, ucx_trim_end=EMBED + 0.003)
    # upper U duct: chimney inlet (inside the shaft wall) -> west -> south -> east -> north -> chimney inlet
    xe = AX - math.sqrt(6.70 ** 2 - R ** 2) + EMBED + 0.004    # tube end inside the shaft at its edge
    up = [(xe, 110.791), (-8.70, 110.791), (-8.70, 80.556), (2 * AX + 8.70, 80.556), (2 * AX + 8.70, 110.791),
          (2 * AX - xe, 110.791)]
    st = fillet(up, RB)
    tube(pc, st, [R] * len(st), N, D, Z)
    # duct buildings and supports
    for x0, x1 in ((-5.311, 3.918), (5.718, 14.947)):
        pc.box((x0, 65.467, 0.0), (x1, 77.11, 10.032), "Sandwich_RAL7047", top="Roof_RAL7004")
    for x0, x1 in ((-16.215, -6.737), (-3.366, 4.213), (5.352, 12.931), (18.238, 25.817)):
        pc.box((x0, 57.376, 0.0), (x1, 60.569, 3.321), "Concrete_Grey")
    return pc.save(out / "ducts.json", {"axis_z": Z, "R": R, "bend_R": RB, "chimney_inlet_x": round(xe, 3),
                                         "joined_upper_halves": True})


# ------------------------------------------------------------------ transformer
def transformer(out, v, f, cell=0.25):
    pc = Piece("Psu_4")
    v = v.copy(); v[:, 2] = np.maximum(v[:, 2], 0.0)
    lo = np.floor(v.min(0) / cell) * cell; lo[2] = 0.0
    shape = np.ceil((v.max(0) - lo) / cell).astype(int) + 1
    occ = np.zeros(shape + 2, bool)                       # 1-cell empty border
    tri = v[f]
    L = np.max(np.linalg.norm(tri - np.roll(tri, 1, 1), axis=2), 1)
    for n in np.unique(np.clip(np.ceil(L / (cell * 0.4)).astype(int), 1, 200)):
        sel = tri[np.clip(np.ceil(L / (cell * 0.4)).astype(int), 1, 200) == n]
        a, b = np.meshgrid(np.arange(n + 1), np.arange(n + 1))
        m = a + b <= n
        w = np.stack([a[m], b[m]], 1) / n
        pts = sel[:, None, 0] + w[None, :, :1] * (sel[:, None, 1] - sel[:, None, 0]) + w[None, :, 1:] * (sel[:, None, 2] - sel[:, None, 0])
        ijk = np.floor((pts.reshape(-1, 3) - lo) / cell).astype(int) + 1
        ijk = np.clip(ijk, 1, np.array(occ.shape) - 2)
        occ[ijk[:, 0], ijk[:, 1], ijk[:, 2]] = True
    occ[:, :, 0] = False
    occ = ndimage.binary_fill_holes(occ)
    surf_cells = int(occ.sum())
    # well-composed: no 2x2 diagonal pairs, no 2x2x2 vertex-only pairs (foreground or background)
    for it in range(50):
        changed = 0
        for ax in range(3):
            o = np.moveaxis(occ, ax, 0)
            a, b, c, d = o[:, :-1, :-1], o[:, 1:, :-1], o[:, :-1, 1:], o[:, 1:, 1:]
            bad = (a & d & ~b & ~c) | (b & c & ~a & ~d)
            if bad.any():
                ii = np.nonzero(bad)
                for di in (0, 1):
                    for dj in (0, 1):
                        o[ii[0], ii[1] + di, ii[2] + dj] = True
                changed += int(bad.sum())
        cs = [occ[i:occ.shape[0] - 1 + i, j:occ.shape[1] - 1 + j, k:occ.shape[2] - 1 + k]
              for i in (0, 1) for j in (0, 1) for k in (0, 1)]
        cnt = sum(c.astype(int) for c in cs)
        diag = np.zeros_like(cnt, bool)
        for p in range(4):                                 # opposite corner pairs (p, 7-p)
            diag |= (cnt == 2) & cs[p] & cs[7 - p]
            diag |= (cnt == 6) & ~cs[p] & ~cs[7 - p]
        if diag.any():
            ii = np.nonzero(diag)
            for i in (0, 1):
                for j in (0, 1):
                    for k in (0, 1):
                        occ[ii[0] + i, ii[1] + j, ii[2] + k] = True
            changed += int(diag.sum())
        occ[:, :, 0] = False
        if not changed:
            break
    occ[:, :, 0] = False
    # one quad per boundary voxel face; grid lattice vertices are shared
    fin = "Equipment_RAL7035"
    org = lo - cell                                       # index 0 = border cell
    for ax in range(3):
        e = np.eye(3, dtype=int)[ax]
        nxt = np.roll(occ, -1, ax)
        for sgn, mask in ((+1, occ & ~nxt), (-1, ~occ & nxt)):
            for idx in np.argwhere(mask):
                base = idx + e                            # the face plane between idx and idx+e
                u, w = [k for k in range(3) if k != ax]
                corners = []
                for du, dw in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    g = base.astype(float).copy(); g[u] += du; g[w] += dw
                    corners.append(org + g * cell)
                nrm = e * sgn
                pc.face(corners, fin, nrm)
    # UCX: greedy boxes over 1.0 m blocks (any voxel)
    B = 4
    sh = (np.array(occ.shape) + B - 1) // B
    pad = np.zeros(sh * B, bool); pad[:occ.shape[0], :occ.shape[1], :occ.shape[2]] = occ
    blk = pad.reshape(sh[0], B, sh[1], B, sh[2], B).any((1, 3, 5))
    used = np.zeros_like(blk)
    for i, j, k in np.argwhere(blk):
        if used[i, j, k]:
            continue
        i1 = i
        while i1 + 1 < sh[0] and blk[i1 + 1, j, k] and not used[i1 + 1, j, k]:
            i1 += 1
        j1 = j
        while j1 + 1 < sh[1] and (blk[i:i1 + 1, j1 + 1, k] & ~used[i:i1 + 1, j1 + 1, k]).all():
            j1 += 1
        k1 = k
        while k1 + 1 < sh[2] and (blk[i:i1 + 1, j:j1 + 1, k1 + 1] & ~used[i:i1 + 1, j:j1 + 1, k1 + 1]).all():
            k1 += 1
        used[i:i1 + 1, j:j1 + 1, k:k1 + 1] = True
        a = org + np.array([i, j, k]) * B * cell
        b = org + (np.array([i1, j1, k1]) + 1) * B * cell
        a[2] = max(a[2], 0.0)
        pc.hull([(x, y, z) for x in (a[0], b[0]) for y in (a[1], b[1]) for z in (a[2], b[2])])
    return pc.save(out / "transformer.json", {"cell_m": cell, "voxels_filled": int(occ.sum()),
                                               "voxels_after_fill": surf_cells, "ucx_block_m": B * cell})


# ------------------------------------------------------------------ tanks
def tanks(out):
    pc = Piece("Psu_5")
    R, H, N, X = 4.895, 11.973, 32, 50.832
    for yc in (67.396, 79.392, 90.987):
        C = (X, yc)
        wall(pc, C, R, 0.0, H, N, "Tank_RAL9016")
        disc(pc, C, R, H, N, "Tank_RAL9016", True)
        disc(pc, C, R, 0.0, N, "Tank_RAL9016", False)
        railing_ring(pc, C, 4.68, H, 0.937, N)
        pc.hull(np.vstack([ring(C, R, 0.0, N), ring(C, R, H, N)]))
    return pc.save(out / "tanks.json", {"R": R, "H": H, "centres_y": [67.396, 79.392, 90.987], "x": X})


if __name__ == "__main__":
    npz, out = np.load(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=False)
    rep = {"chimney": chimney(out), "ducts": ducts(out),
           "transformer": transformer(out, npz["Layer_0__2_v"], npz["Layer_0__2_f"]), "tanks": tanks(out)}
    (out / "build_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False))

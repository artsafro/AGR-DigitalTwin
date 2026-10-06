"""Opening fills in two variants from sampled source fills: NPM planes and VPM frames with panes.

    uv run python jobs/PSU275/scripts/opening_fills.py <exterior-surface.json> <opening-samples.npz> <body-shell.json> <out_dir>

Per opening (BODY profile k, opening i):
  kind      window | door | louvre | void, from the sampled first-hit classes
  depths    frame plane d_f and glass plane d_g behind the facade (clamped inside the 0.4 m shell)
  panes     greedy rectangles of glass cells, edges snapped to source vertices, clustered 12 mm,
            kept >= 30 mm inside the opening outline
NPM: one quad per opening at d_f, outline embedded 10 mm into the reveals (project joint rule).
VPM: frame/leaf = outline (+10 mm) minus panes as T-free grid quads at d_f; each pane as a glass quad
at d_g with four side quads from d_f to d_g (split on the same grid lines).
Both variants are audited with BODY through tools/check_shell_windows.audit (window contract).
"""
import json
import sys
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Point, box
from shapely.ops import unary_union

surface_json, samples_npz, body_json, out = sys.argv[1:5]
out = Path(out)
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from check_shell_windows import audit  # noqa: E402

SHELL, EMBED, SNAP, CLUSTER, BAND, MIN_PANE, MIN_MULLION = 0.4, 0.01, 0.02, 0.012, 0.03, 0.15, 0.02
MATERIALS = ["glass", "frame_RAL9016", "door_RAL7004", "louvre_RAL9016", "void_dark"]
prof = json.load(open(surface_json, encoding="utf-8"))["profiles"]
S = np.load(samples_npz)
names = [str(x) for x in S["class_names"]]
C = {n: names.index(n) for n in names}
body = json.load(open(body_json, encoding="utf-8"))["meshes"][0]


class Mesh:
    def __init__(self, name):
        self.name, self.v, self.f, self.m, self.lookup = name, [], [], [], {}

    def face(self, pts, normal, mat):
        q = np.array(pts, float)
        if np.dot(np.cross(q[1] - q[0], q[2] - q[0]), normal) < 0:
            q = q[::-1]
        idx = []
        for p in q:
            k = tuple(np.round(p, 6))
            if k not in self.lookup:
                self.lookup[k] = len(self.v); self.v.append(p.tolist())
            idx.append(self.lookup[k])
        self.f.append(idx); self.m.append(mat)

    def dump(self):
        return {"name": self.name, "vertices": self.v, "faces": self.f, "materials": self.m}


def cluster_map(values, anchors, span=CLUSTER):
    groups = []
    for v in sorted(set(values) | set(anchors)):
        if groups and v - groups[-1][-1] < span:
            groups[-1].append(v)
        else:
            groups.append([v])
    mp = {}
    for g in groups:
        fixed = [v for v in g if v in anchors]
        rep = fixed[0] if fixed else float(np.median(g))
        mp.update({v: rep for v in g})
    return mp


records, npm_meshes, vpm_meshes, rows = [], [], [], []
for pi, oi in S["index"]:
    p = prof[pi]; key = f"{pi}_{oi}"
    a, u_ax, plane = p["axis"], p["along_axis"], p["plane"]
    outward = np.array(p["outward"] + [0.0])
    u0, z0, u1, z1 = p["openings"][oi]["bounds_uz"]
    cls, dep, us, zs = S["cls_" + key], S["depth_" + key], S["us_" + key], S["zs_" + key]
    hits = cls > 0
    share = {n: float((cls == C[n]).sum()) / cls.size for n in names}
    doorish = share["door"] + share["other"]
    if share["none"] > 0.9:
        kind = "void"
    elif share["glass"] >= 0.3:
        kind = "window"
    elif doorish >= 0.5:
        kind = "door"
    elif share["louvre"] >= 0.3:
        kind = "louvre"
    else:
        kind = "door"
    frame_like = np.isin(cls, [C["frame"], C["door"], C["other"], C["louvre"]])
    d_f = float(np.nanmedian(dep[frame_like])) if frame_like.any() else (float(np.nanmedian(dep[hits])) if hits.any() else 0.2)
    d_f = float(np.clip(d_f, 0.02, SHELL - 0.05))
    glass = cls == C["glass"]
    d_g = float(np.nanmedian(dep[glass])) if glass.any() else d_f
    d_g = float(np.clip(max(d_g, d_f + 0.02), 0.03, SHELL - 0.02))

    def P(u, z, d):
        q = [0.0, 0.0, z]; q[u_ax] = u; q[a] = plane - outward[a] * d
        return q

    outline = (u0 - EMBED, z0 - EMBED, u1 + EMBED, z1 + EMBED)
    mat_fill = {"window": 1, "door": 2, "louvre": 3, "void": 4}[kind]
    # NPM: a single plane
    npm = Mesh(f"NPM_{key}")
    npm.face([P(outline[0], outline[1], d_f), P(outline[2], outline[1], d_f), P(outline[2], outline[3], d_f),
              P(outline[0], outline[3], d_f)], outward, 0 if kind == "window" else mat_fill)
    # VPM: panes from glass cells (greedy rectangles)
    step = float(S["step"])
    seen = np.zeros_like(glass); panes = []
    for i in range(len(us)):
        for j in range(len(zs)):
            if not glass[i, j] or seen[i, j]:
                continue
            j1 = j
            while j1 + 1 < len(zs) and glass[i, j1 + 1] and not seen[i, j1 + 1]:
                j1 += 1
            i1 = i
            while i1 + 1 < len(us) and glass[i1 + 1, j:j1 + 1].all() and not seen[i1 + 1, j:j1 + 1].any():
                i1 += 1
            seen[i:i1 + 1, j:j1 + 1] = True
            panes.append([us[i] - step / 2, zs[j] - step / 2, us[i1] + step / 2, zs[j1] + step / 2])
    su, sz = S["snapu_" + key], S["snapz_" + key]

    def snap(v, pool):
        if len(pool):
            k = pool[np.argmin(abs(pool - v))]
            if abs(k - v) <= SNAP:
                return float(k)
        return float(v)

    panes = [[snap(r[0], su), snap(r[1], sz), snap(r[2], su), snap(r[3], sz)] for r in panes]
    panes = [[max(r[0], u0 + BAND), max(r[1], z0 + BAND), min(r[2], u1 - BAND), min(r[3], z1 - BAND)] for r in panes]
    panes = [r for r in panes if r[2] - r[0] >= MIN_PANE and r[3] - r[1] >= MIN_PANE]
    umap = cluster_map([v for r in panes for v in (r[0], r[2])], {outline[0], outline[2]})
    zmap = cluster_map([v for r in panes for v in (r[1], r[3])], {outline[1], outline[3]})
    panes = [[umap[r[0]], zmap[r[1]], umap[r[2]], zmap[r[3]]] for r in panes]
    panes = [r for r in panes if r[2] - r[0] >= MIN_PANE and r[3] - r[1] >= MIN_PANE]
    # drop overlapping panes (greedy order keeps the first)
    kept = []
    for r in sorted(panes, key=lambda r: -(r[2] - r[0]) * (r[3] - r[1])):
        if all(box(*r).intersection(box(*k)).area < 1e-9 for k in kept):
            kept.append(r)
    panes = kept

    def glass_cover(r):
        iu = (us > r[0]) & (us < r[2]); iz = (zs > r[1]) & (zs < r[3])
        cells = glass[np.ix_(iu, iz)]
        return float(cells.mean()) if cells.size else 0.0

    # panes closer than MIN_MULLION: merge when the union is glass, else open a MIN_MULLION gap
    changed = True
    while changed:
        changed = False
        for x in panes:
            for y in panes:
                if x is y:
                    continue
                gap_u = max(x[0], y[0]) - min(x[2], y[2]); gap_z = max(x[1], y[1]) - min(x[3], y[3])
                ov_u = min(x[2], y[2]) - max(x[0], y[0]); ov_z = min(x[3], y[3]) - max(x[1], y[1])
                close = (0 <= gap_u < MIN_MULLION and ov_z > 0) or (0 <= gap_z < MIN_MULLION and ov_u > 0) or (ov_u > 0 and ov_z > 0)
                if not close:
                    continue
                u = [min(x[0], y[0]), min(x[1], y[1]), max(x[2], y[2]), max(x[3], y[3])]
                if glass_cover(u) >= 0.9 and all(box(*u).intersection(box(*k)).area < 1e-9 for k in panes if k is not x and k is not y):
                    x[:] = u; panes.remove(y)
                elif 0 <= gap_u < MIN_MULLION and ov_z > 0:
                    if x[0] < y[0]: y[0] = x[2] + MIN_MULLION
                    else: x[0] = y[2] + MIN_MULLION
                elif 0 <= gap_z < MIN_MULLION and ov_u > 0:
                    if x[1] < y[1]: y[1] = x[3] + MIN_MULLION
                    else: x[1] = y[3] + MIN_MULLION
                else:
                    panes.remove(y)
                changed = True
                break
            if changed:
                break
    panes = [r for r in panes if r[2] - r[0] >= MIN_PANE and r[3] - r[1] >= MIN_PANE]
    vpm = Mesh(f"VPM_{key}")
    frame = box(*outline).difference(unary_union([box(*r) for r in panes])) if panes else box(*outline)
    ucut = sorted({outline[0], outline[2], *[v for r in panes for v in (r[0], r[2])]})
    zcut = sorted({outline[1], outline[3], *[v for r in panes for v in (r[1], r[3])]})
    for ua, ub in zip(ucut, ucut[1:]):
        for za, zb in zip(zcut, zcut[1:]):
            if frame.contains(Point((ua + ub) / 2, (za + zb) / 2)):
                vpm.face([P(ua, za, d_f), P(ub, za, d_f), P(ub, zb, d_f), P(ua, zb, d_f)], outward, mat_fill)
    for r in panes:
        pu = [u for u in ucut if r[0] - 1e-9 <= u <= r[2] + 1e-9]; pz = [z for z in zcut if r[1] - 1e-9 <= z <= r[3] + 1e-9]
        for ua, ub in zip(pu, pu[1:]):
            for za, zb in zip(pz, pz[1:]):
                vpm.face([P(ua, za, d_g), P(ub, za, d_g), P(ub, zb, d_g), P(ua, zb, d_g)], outward, 0)
        if d_g - d_f > 1e-6:
            for zc0, zc1 in zip([z for z in zcut if r[1] - 1e-9 <= z <= r[3] + 1e-9], [z for z in zcut if r[1] - 1e-9 <= z <= r[3] + 1e-9][1:]):
                for uu, sg in ((r[0], +1), (r[2], -1)):
                    nn = np.zeros(3); nn[u_ax] = sg
                    vpm.face([P(uu, zc0, d_f), P(uu, zc1, d_f), P(uu, zc1, d_g), P(uu, zc0, d_g)], nn, mat_fill)
            ucs = [u for u in ucut if r[0] - 1e-9 <= u <= r[2] + 1e-9]
            for uc0, uc1 in zip(ucs, ucs[1:]):
                for zz, sg in ((r[1], +1), (r[3], -1)):
                    vpm.face([P(uc0, zz, d_f), P(uc1, zz, d_f), P(uc1, zz, d_g), P(uc0, zz, d_g)], [0, 0, sg], mat_fill)
    rec = {"id": f"S3-fill-{key}", "profile": int(pi), "opening": int(oi), "kind": kind, "axis": a, "along_axis": u_ax,
           "outward_sign": float(outward[a]), "facade_plane": plane, "opening_bounds": [u0, z0, u1, z1],
           "frame_plane": float(plane - outward[a] * d_f), "recess_m": d_f, "lateral_embed_m": EMBED, "frame_depth_m": round(d_f, 4), "glass_depth_m": round(d_g, 4),
           "panes": len(panes), "share": {k: round(v, 3) for k, v in share.items() if v > 0}}
    records.append(rec); npm_meshes.append(npm.dump()); vpm_meshes.append(vpm.dump())

out.mkdir(parents=True, exist_ok=False)
results = {}
for variant, meshes in (("npm", npm_meshes), ("vpm", vpm_meshes)):
    q = audit({"angle": 0.0, "windows": records, "meshes": [body] + meshes})
    results[variant] = {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in q.items() if k != "scope"}
    merged = {"name": f"WINDOWS_{variant.upper()}", "vertices": [], "faces": [], "materials": []}
    for m in meshes:
        n = len(merged["vertices"])
        merged["vertices"] += m["vertices"]; merged["faces"] += [[i + n for i in f] for f in m["faces"]]
        merged["materials"] += m["materials"]
    (out / f"windows-{variant}.json").write_text(json.dumps({"mesh": merged, "material_names": MATERIALS, "audit": results[variant]},
                                                            ensure_ascii=False), encoding="utf-8")
(out / "openings.json").write_text(json.dumps({"records": records, "audit": results}, ensure_ascii=False, indent=1), encoding="utf-8")
from collections import Counter
print(json.dumps({"openings": len(records), "kinds": Counter(r["kind"] for r in records),
                  "panes": sum(r["panes"] for r in records),
                  "npm_quads": sum(len(m["faces"]) for m in npm_meshes), "vpm_quads": sum(len(m["faces"]) for m in vpm_meshes),
                  "audit_npm": results["npm"], "audit_vpm": results["vpm"]}, default=str))

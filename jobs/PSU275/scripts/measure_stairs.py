"""Measure external steel stairs in S3: clusters of decking/stringer faces outside or on top of the masses.

    blender --background --factory-startup --python jobs/PSU275/scripts/measure_stairs.py -- <S3.fbx> <masses.json> <out.json>

Per cluster (connected in plan within 0.6 m): bbox, horizontal decking levels (landings: z, area,
extent), sloped faces (flights: slope direction, z range, plan extent), ladder hints (narrow tall
clusters). Decking: 'Настил рифленый'; frames/stringers: 'Синий (RAL 5015)'; handrails: 'Желтый RAL 1021'.
Only geometry outside the masses or above their tops is considered (roof ladders included).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import bpy
import numpy as np

src, masses_json, out = sys.argv[sys.argv.index("--") + 1:]
S3_TO_RVT, CENTRE_RVT = (204.86, 142.55), (37.17, 54.00)
masses = json.loads(Path(masses_json).read_text(encoding="utf-8"))["masses"]
KEYS = {"deck": "Настил рифленый", "frame": "Синий (RAL 5015)", "rail": "Желтый RAL 1021", "ladder": "1021"}
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
rows = []
for o in bpy.context.scene.objects:
    if o.type != "MESH" or not o.data.polygons:
        continue
    kind = next((k for k, s in KEYS.items() if s in o.name), None)
    if kind is None or "00" in o.name[-3:] or "1022" in o.name:
        continue
    me = o.data; n = len(me.polygons)
    c = np.empty(n * 3); me.polygons.foreach_get("center", c); c = c.reshape(-1, 3)
    nr = np.empty(n * 3); me.polygons.foreach_get("normal", nr); nr = nr.reshape(-1, 3)
    a = np.empty(n); me.polygons.foreach_get("area", a)
    M = np.array(o.matrix_world); c = c @ M[:3, :3].T + M[:3, 3]; nr = nr @ M[:3, :3].T
    loc = np.stack([S3_TO_RVT[0] - c[:, 1] - CENTRE_RVT[0], c[:, 0] - S3_TO_RVT[1] - CENTRE_RVT[1], c[:, 2]], 1)
    nl = np.stack([-nr[:, 1], nr[:, 0], nr[:, 2]], 1)
    nl = nl / np.maximum(np.linalg.norm(nl, axis=1)[:, None], 1e-12)  # object matrices may carry scale
    outside = np.ones(n, bool)
    for m in masses:
        outside &= ~((loc[:, 0] > m["x"][0] + 0.05) & (loc[:, 0] < m["x"][1] - 0.05) &
                     (loc[:, 1] > m["y"][0] + 0.05) & (loc[:, 1] < m["y"][1] - 0.05) & (loc[:, 2] < m["top"] + 0.05))
    keep = outside & (loc[:, 2] > -0.5) & (loc[:, 2] < 70)
    # per-face vertex bounds (plan) for landing/tread extents
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    co = np.stack([S3_TO_RVT[0] - co[:, 1] - CENTRE_RVT[0], co[:, 0] - S3_TO_RVT[1] - CENTRE_RVT[1], co[:, 2]], 1)
    lv = np.empty(len(me.loops), int); me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(n, int); me.polygons.foreach_get("loop_start", ls)
    vlo = np.minimum.reduceat(co[lv], ls, axis=0); vhi = np.maximum.reduceat(co[lv], ls, axis=0)
    for i in np.nonzero(keep)[0]:
        rows.append((kind, loc[i], nl[i], a[i], vlo[i], vhi[i]))
P = np.array([r[1] for r in rows])
# plan clustering on a 0.3 m grid
S = 0.3
ij = np.floor(P[:, :2] / S).astype(int)
cell = defaultdict(list)
for k, (i, j) in enumerate(ij):
    cell[(i, j)].append(k)
lab = {}
cur = 0
for key in cell:
    if key in lab:
        continue
    stack = [key]; lab[key] = cur
    while stack:
        i, j = stack.pop()
        for di in (-2, -1, 0, 1, 2):
            for dj in (-2, -1, 0, 1, 2):
                nb = (i + di, j + dj)
                if nb in cell and nb not in lab:
                    lab[nb] = cur; stack.append(nb)
    cur += 1
clusters = defaultdict(list)
for key, ks in cell.items():
    clusters[lab[key]].extend(ks)
res = []
for cid, ks in clusters.items():
    ks = np.array(ks)
    pts = P[ks]
    area = sum(rows[k][3] for k in ks)
    if area < 2.0:
        continue
    kinds = defaultdict(float)
    for k in ks:
        kinds[rows[k][0]] += rows[k][3]
    deck_h = defaultdict(lambda: [0.0, [1e9, 1e9], [-1e9, -1e9]])
    slopes = []
    for k in ks:
        kind, p, n, a, vlo, vhi = rows[k]
        if kind == "deck" and n[2] > 0.99:
            z = round(float(p[2]), 2); d = deck_h[z]; d[0] += a
            d[1] = [min(d[1][0], vlo[0]), min(d[1][1], vlo[1])]; d[2] = [max(d[2][0], vhi[0]), max(d[2][1], vhi[1])]
        if kind in ("deck", "frame") and 0.3 < n[2] < 0.95 and a > 0.05:
            slopes.append((p, n, a))
    landings = sorted(([z, round(v[0], 2), [round(x, 2) for x in v[1]], [round(x, 2) for x in v[2]]]
                       for z, v in deck_h.items() if v[0] > 0.3), key=lambda r: r[0])
    flights = []
    if slopes:
        sn = np.array([s[1] for s in slopes]); sp = np.array([s[0] for s in slopes])
        dirs = np.round(sn[:, :2] / np.linalg.norm(sn[:, :2], axis=1)[:, None], 1) + 0.0
        for d in {tuple(x) for x in dirs if np.all(np.isfinite(x))}:
            m = np.all(np.isclose(dirs, d), axis=1)
            if not m.any():
                continue
            flights.append({"down_dir_xy": d, "faces": int(m.sum()), "z": [round(float(sp[m, 2].min()), 2), round(float(sp[m, 2].max()), 2)],
                            "lo": sp[m, :2].min(0).round(2).tolist(), "hi": sp[m, :2].max(0).round(2).tolist(),
                            "slope_deg": round(float(np.degrees(np.arccos(np.clip(np.median(sn[m, 2]), -1, 1)))), 1)})
    res.append({"cluster": cid, "lo": pts.min(0).round(2).tolist(), "hi": pts.max(0).round(2).tolist(),
                "area_by_kind": {k: round(v, 1) for k, v in kinds.items()}, "landings": landings, "flights": flights})
res.sort(key=lambda r: (r["lo"][0], r["lo"][1]))
Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("DONE clusters", len(res))

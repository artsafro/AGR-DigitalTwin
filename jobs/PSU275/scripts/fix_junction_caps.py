"""Resolve cap overlaps at mass junctions in a shell output, keeping every rim (no holes).

    uv run python jobs/PSU275/scripts/fix_junction_caps.py <shell_dir> <new_dir> [--roofs masses.json]

--roofs: first drop step-bottom rims lying at a mass roof level (with wells in BODY the step wall
reaches the lower roof, whose membrane continues the plane; a down-facing rim there only touches it).

At a junction a lower mass's parapet cap and the bottom rim of the upper step wall share a corner
vertex; the shell mitres both, so they overlap in a 0.4 x 0.4 m corner square (coplanar overlap).
For each overlapping rim pair: the rim that is NOT a step bottom (the lower parapet cap) gets its
mitred inner corner moved back to a pure normal offset (no mitre). The step-bottom rim stays and
covers the corner. The moved vertex then lies on the step rim edge (a T-junction between two caps),
which the stage-5 seal splits. Replaces drop_step_bottom_rims.py, which left 0.4 m slots.
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point, Polygon, shape

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from check_shell_windows import audit  # noqa: E402

data = json.loads((src / "body-shell.json").read_text(encoding="utf-8"))
mesh, sources = data["meshes"][0], data["face_sources"]
inputs = json.loads((src / "inputs.json").read_text(encoding="utf-8"))
profiles = json.loads(Path(next(k for k in inputs["sha256"] if k.endswith("exterior-surface.json"))).read_text(encoding="utf-8"))["profiles"]
v_in = np.load(next(k for k in inputs["sha256"] if k.endswith("exterior-surface.npz")))["vertices"]
polys = [shape(json.loads(p["profile_geojson"])) for p in profiles]
T = float(data.get("thickness_m", 0.4))
V = np.array(mesh["vertices"], dtype=float)


def profile_of(s):
    return int(s["source_ref"].rsplit("/", 1)[1])


def is_step_bottom(s):
    i, j = s["source_edge"]
    a, b = v_in[i], v_in[j]
    if abs(a[2] - b[2]) > 1e-9 or a[2] < 1e-6:
        return False
    k = profile_of(s); p, poly = profiles[k], polys[k]
    u = p["along_axis"]; mid = ((a[u] + b[u]) / 2, a[2])
    outer = Polygon(poly.exterior)
    return LineString(poly.exterior.coords).distance(Point(mid)) < 1e-7 and \
        not outer.contains(Point(mid[0], a[2] - 1e-3)) and outer.contains(Point(mid[0], a[2] + 1e-3))


dropped = []
if "--roofs" in sys.argv:
    ms = json.loads(Path(sys.argv[sys.argv.index("--roofs") + 1]).read_text(encoding="utf-8"))["masses"]
    roofs = {m["roof"] for m in ms}
    bands = {(m["roof"], m["top"]) for m in ms if m["roof"] < m["top"]}
    keep = []
    for k, s in enumerate(sources):
        za, zb = sorted((v_in[s["source_edge"][0]][2], v_in[s["source_edge"][1]][2])) if s["role"] == "rim" else (0, 0)
        same_xy = s["role"] == "rim" and np.allclose(v_in[s["source_edge"][0]][:2], v_in[s["source_edge"][1]][:2])
        band_end = same_xy and any(abs(za - r) < 1e-6 and abs(zb - t) < 1e-6 for r, t in bands)
        if s["role"] == "rim" and ((is_step_bottom(s) and any(abs(za - r) < 1e-6 for r in roofs)) or band_end):
            dropped.append(k)  # roof-level step bottoms and well-band end rims (hidden, coplanar with parapet inner faces)
        else:
            keep.append(k)
    faces0 = [mesh["faces"][k] for k in keep]
    used = sorted({i for f in faces0 for i in f}); remap = {o: n for n, o in enumerate(used)}
    mesh = {**mesh, "vertices": [mesh["vertices"][i] for i in used], "faces": [[remap[i] for i in f] for f in faces0],
            "materials": [mesh["materials"][k] for k in keep]}
    sources = [sources[k] for k in keep]
    data = {**data, "face_sources": sources}
    V = np.array(mesh["vertices"], dtype=float)
q0 = audit({"angle": 0.0, "windows": [], "meshes": [mesh]})
moved = []
for fi, fj, area, _, _ in q0["coplanar_overlaps"]:
    si, sj = sources[fi], sources[fj]
    if si["role"] != "rim" or sj["role"] != "rim":
        continue
    cap_k = fj if is_step_bottom(si) and not is_step_bottom(sj) else fi if is_step_bottom(sj) and not is_step_bottom(si) else None
    if cap_k is None:
        continue
    s = sources[cap_k]
    a, b = v_in[s["source_edge"][0]], v_in[s["source_edge"][1]]
    normal = np.array(profiles[profile_of(s)]["outward"] + [0.0])
    face = mesh["faces"][cap_k]
    for vid in face:
        p = V[vid]
        if np.allclose(p, a) or np.allclose(p, b):
            continue  # outer corners stay
        base = a if np.linalg.norm(p - a) < np.linalg.norm(p - b) else b
        target = base - normal * T
        if np.linalg.norm(p - target) > 1e-6:
            moved.append({"face": cap_k, "vertex": vid, "from": p.round(4).tolist(), "to": target.round(4).tolist()})
            V[vid] = target
# moving a shared inner vertex also moves it for the neighbouring cap of the same edge chain; give
# the moved corner its own vertex only in the overlapping cap
faces = [list(f) for f in mesh["faces"]]
verts = mesh["vertices"][:]
for mv in moved:
    k, vid = mv["face"], mv["vertex"]
    verts.append(mv["to"]); faces[k] = [len(verts) - 1 if x == vid else x for x in faces[k]]
    V[vid] = mesh["vertices"][vid]  # restore the shared original for other faces
mesh2 = {**mesh, "vertices": verts, "faces": faces}
q = audit({"angle": 0.0, "windows": [], "meshes": [mesh2]})
dst.mkdir(parents=True, exist_ok=False)
shutil.copy(src / "inputs.json", dst / "inputs.json")
(dst / "body-shell.json").write_text(json.dumps({**data, "meshes": [mesh2],
                                                 "postprocess": {"script": "fix_junction_caps.py", "source": str(src),
                                                                 "moved_cap_corners": moved, "dropped_roof_level_step_rims": len(dropped)}}), encoding="utf-8")
(dst / "qa.json").write_text(json.dumps(q, indent=1), encoding="utf-8")
print(json.dumps({"dropped": len(dropped), "overlaps_before": len(q0["coplanar_overlaps"]), "moved": len(moved), "quads": len(faces),
                  **{k: (len(x) if isinstance(x, (list, dict)) else x) for k, x in q.items() if k != "scope"}}))

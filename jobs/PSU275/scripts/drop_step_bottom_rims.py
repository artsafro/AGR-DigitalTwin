"""Drop downward rims under step faces (walls standing on a lower mass) from a shell output.

    uv run python jobs/PSU275/scripts/drop_step_bottom_rims.py <shell_dir> <new_dir>

A rim built on a horizontal source edge (z > 0) that lies on the outer ring of its facade
profile with the profile above it is the underside of an upper wall resting on a lower mass.
Opening heads lie on hole rings and are kept. At a junction corner it overlaps the
lower mass's parapet cap (0.4 x 0.4 m). The roof/parapet stage closes this zone. Writes a new
output directory; the input is untouched.
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
v = np.array(mesh["vertices"])
inputs = json.loads((src / "inputs.json").read_text(encoding="utf-8"))
profiles_path = next(k for k in inputs["sha256"] if k.endswith("exterior-surface.json"))
profiles = json.loads(Path(profiles_path).read_text(encoding="utf-8"))["profiles"]
# source_edge indices refer to the INPUT surface vertices, not to the shell mesh vertex order
surface_path = next(k for k in inputs["sha256"] if k.endswith("exterior-surface.npz"))
v_in = np.load(surface_path)["vertices"]


polys = [shape(json.loads(p["profile_geojson"])) for p in profiles]


def is_step_bottom(ref, a, b):
    k = int(ref.rsplit("/", 1)[1])
    p, poly = profiles[k], polys[k]
    u = p["along_axis"]
    (u0, z0), (u1, z1) = (a[u], a[2]), (b[u], b[2])
    mid = ((u0 + u1) / 2, z0)
    on_outer = LineString(poly.exterior.coords).distance(Point(mid)) < 1e-7
    return on_outer and not Polygon(poly.exterior).contains(Point(mid[0], z0 - 1e-3))         and Polygon(poly.exterior).contains(Point(mid[0], z0 + 1e-3))


keep, dropped = [], []
for k, (face, s) in enumerate(zip(mesh["faces"], sources)):
    if s["role"] == "rim":
        i, j = s["source_edge"]
        z = v_in[[i, j]][:, 2]
        if abs(z[0] - z[1]) < 1e-9 and z[0] > 1e-6 and is_step_bottom(s["source_ref"], v_in[i], v_in[j]):
            dropped.append(k)
            continue
    keep.append(k)
faces = [mesh["faces"][k] for k in keep]
used = sorted({i for f in faces for i in f})
remap = {old: new for new, old in enumerate(used)}
mesh2 = {**mesh, "vertices": [mesh["vertices"][i] for i in used], "faces": [[remap[i] for i in f] for f in faces],
         "materials": [mesh["materials"][k] for k in keep]}
scene = {"angle": data["angle"], "windows": [], "meshes": [mesh2]}
qa = audit(scene)
dst.mkdir(parents=True, exist_ok=False)
shutil.copy(src / "inputs.json", dst / "inputs.json")
(dst / "body-shell.json").write_text(json.dumps({**data, "meshes": [mesh2], "face_sources": [sources[k] for k in keep],
                                                 "postprocess": {"script": "drop_step_bottom_rims.py", "source": str(src),
                                                                 "dropped_rims": len(dropped)}}), encoding="utf-8")
(dst / "qa.json").write_text(json.dumps(qa, indent=1), encoding="utf-8")
print(json.dumps({"dropped_rims": len(dropped), "quads": len(faces),
                  **{k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in qa.items()}}))

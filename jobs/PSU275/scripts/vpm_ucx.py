"""PSU275 UCX collision boxes (VPM), added to a stage-5 master -> stage-6 blend.

    blender --background --factory-startup <stage5.blend> --python jobs/PSU275/scripts/vpm_ucx.py -- \
        <masses.json> <portals.json> <out.blend>

One convex closed box per mass (plan extents, z from the mass below to the parapet top) and one per
portal (outer plane to the facade); every box is shrunk by GAP/2 on each side, so neighbours keep a
2 mm gap (reg p.36-37 §13, KPP1 v005 practice). Triangulated, no UV, no materials,
named UCX_SM_<Address>_Main_NNN. Simplifications: parapet wells are filled (box to the parapet top),
window/portal details and stairs have no collision.
"""
import json
import sys
from pathlib import Path

import bmesh
import bpy

masses_json, portals_json, out_blend = sys.argv[sys.argv.index("--") + 1:]
GAP = 0.002
main = next(o for o in bpy.context.scene.objects if o.name.startswith("SM_") and o.name.endswith("_Main"))
address = main.name[3:-5]
boxes = []
masses = json.loads(Path(masses_json).read_text(encoding="utf-8"))["masses"]
for m in masses:
    below = max([n["top"] for n in masses if n is not m and n["top"] < m["top"]
                 and n["x"][0] <= m["x"][0] and m["x"][1] <= n["x"][1] and n["y"][0] <= m["y"][0] and m["y"][1] <= n["y"][1]],
                default=0.0)
    boxes.append((m["name"], (m["x"][0], m["y"][0], below), (m["x"][1], m["y"][1], m["top"])))
for p in json.loads(Path(portals_json).read_text(encoding="utf-8"))["portals"]:
    a = 0 if p["facade_axis"] == "x" else 1
    u0, z0, u1, z1 = p["bounds_uz"]
    lo, hi = [0.0, 0.0, z0 if z0 > 0.05 else 0.0], [0.0, 0.0, z1]
    lo[a], hi[a] = sorted((p["facade_plane"], p["outer_plane"]))
    lo[1 - a], hi[1 - a] = u0, u1
    boxes.append(("portal_" + p["name"], tuple(lo), tuple(hi)))
rows = []
for k, (name, lo, hi) in enumerate(boxes, 1):
    lo = [c + GAP / 2 for c in lo]; hi = [c - GAP / 2 for c in hi]
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = [lo[i] if v.co[i] < 0 else hi[i] for i in range(3)]
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(f"UCX_SM_{address}_Main_{k:03d}")
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(me.name, me)
    bpy.context.scene.collection.objects.link(ob)
    rows.append({"object": ob.name, "source": name, "lo": [round(c, 4) for c in lo], "hi": [round(c, 4) for c in hi]})
# overlap check between boxes (closed intervals with the gap)
clash = [(a["object"], b["object"]) for i, a in enumerate(rows) for b in rows[i + 1:]
         if all(a["lo"][d] < b["hi"][d] and b["lo"][d] < a["hi"][d] for d in range(3))]
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
Path(out_blend[:-6] + ".ucx.json").write_text(json.dumps({"boxes": rows, "intersections": clash, "gap_m": GAP}, indent=1), encoding="utf-8")
print("UCX", len(rows), "intersections", len(clash))

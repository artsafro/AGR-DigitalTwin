"""Clip the PSU275 main building (S3 FBX) to the first-floor band and save a versioned .blend.

    blender --background --factory-startup --python-exit-code 1 \
        --python jobs/PSU275/scripts/clip_floor1.py -- <S3.fbx> <out.blend> <report.json> [z_lo z_hi]

Read-only on the source. Main building = mesh objects whose XY bounds lie inside the
building footprint box; everything else (chimney, transformer, pipes, site) is dropped.
Default band: ground -0.150 .. +13.060 (docs/sources/psu275.md); pass z_lo z_hi to override.
"""
import json
import sys
from pathlib import Path

import bmesh
import bpy

Z_LO, Z_HI = -0.150, 13.060
FOOT = ((136.0, 106.0), (256.0, 228.0))  # S3 main-building XY box with margin, metres

args = sys.argv[sys.argv.index("--") + 1:]
src, out_blend, out_json = args[:3]
if len(args) == 5:
    Z_LO, Z_HI = float(args[3]), float(args[4])
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.import_scene.fbx(filepath=src)

def world_bounds(o):
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]

kept, dropped, emptied = [], [], []
for o in list(bpy.data.objects):
    if o.type != "MESH" or not o.data.vertices:
        continue
    lo, hi = world_bounds(o)
    inside = FOOT[0][0] <= lo[0] and hi[0] <= FOOT[1][0] and FOOT[0][1] <= lo[1] and hi[1] <= FOOT[1][1]
    if not inside or hi[2] <= Z_LO or lo[2] >= Z_HI:
        dropped.append(o.name)
        bpy.data.objects.remove(o)
        continue
    # bake transform so the cut planes are in world space
    o.data = o.data.copy()
    o.data.transform(o.matrix_world)
    o.matrix_world.identity()
    bm = bmesh.new()
    bm.from_mesh(o.data)
    for z, clear_outer, clear_inner in ((Z_HI, True, False), (Z_LO, False, True)):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, z), plane_no=(0, 0, 1),
                               clear_outer=clear_outer, clear_inner=clear_inner)
    bm.to_mesh(o.data)
    bm.free()
    if not o.data.polygons:
        emptied.append(o.name)
        bpy.data.objects.remove(o)
        continue
    kept.append(o)

for o in list(bpy.data.objects):
    if o.type == "EMPTY" and not o.children:
        bpy.data.objects.remove(o)

rows, tot = [], 0
gmin, gmax = [1e9] * 3, [-1e9] * 3
for o in kept:
    lo, hi = world_bounds(o)
    t = sum(len(p.vertices) - 2 for p in o.data.polygons)
    tot += t
    for i in range(3):
        gmin[i] = min(gmin[i], lo[i]); gmax[i] = max(gmax[i], hi[i])
    rows.append({"name": o.name, "tris": t, "lo": [round(x, 3) for x in lo], "hi": [round(x, 3) for x in hi]})

bpy.ops.wm.save_as_mainfile(filepath=out_blend)
Path(out_json).write_text(json.dumps({
    "source": src, "band_m": [Z_LO, Z_HI], "footprint_box": FOOT,
    "kept": len(kept), "dropped": len(dropped), "emptied_by_cut": len(emptied),
    "total_tris": tot, "bounds_m": [[round(x, 3) for x in gmin], [round(x, 3) for x in gmax]],
    "objects": sorted(rows, key=lambda r: -r["tris"]), "dropped_names": dropped,
}, ensure_ascii=False, indent=1), encoding="utf-8")
print("DONE kept", len(kept), "tris", tot, "bounds", gmin, gmax)

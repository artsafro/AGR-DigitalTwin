"""Dump vertices and triangles (local frame) of selected S3 objects to npz, one key per object.

    blender --background --factory-startup --python jobs/PSU275/scripts/dump_points.py -- <S3.fbx> <out.npz> <name-substring> [...]
"""
import sys

import bmesh
import bpy
import numpy as np

args = sys.argv[sys.argv.index("--") + 1:]
src, out, keys = args[0], args[1], args[2:]
S3_TO_RVT, CENTRE_RVT = (204.86, 142.55), (37.17, 54.00)
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
arrays = {}
for o in bpy.context.scene.objects:
    if o.type != "MESH" or not any(k in o.name for k in keys):
        continue
    bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    co = np.array([tuple(v.co) for v in bm.verts])
    loc = np.stack([S3_TO_RVT[0] - co[:, 1] - CENTRE_RVT[0], co[:, 0] - S3_TO_RVT[1] - CENTRE_RVT[1], co[:, 2]], 1)
    bm.verts.index_update()
    tri = np.array([[v.index for v in f.verts] for f in bm.faces], dtype=np.int32)
    key = "".join(ch if ch.isalnum() else "_" for ch in o.name.encode("ascii", "ignore").decode() or "obj") + f"_{len(arrays)}"
    arrays[key + "_v"] = loc; arrays[key + "_f"] = tri
    print("OBJ", key, o.name, len(loc), len(tri))
    bm.free()
np.savez_compressed(out, **arrays)
print("DONE")

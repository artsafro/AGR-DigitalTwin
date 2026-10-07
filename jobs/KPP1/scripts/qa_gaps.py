"""Diagnostic: classify open edges and T-junctions of SM_Kpp_1_Main by adjacent finish and orientation."""
import bpy, bmesh, collections, sys
from mathutils.bvhtree import BVHTree
o = bpy.data.objects["SM_Kpp_1_Main"]; me = o.data
bm = bmesh.new(); bm.from_mesh(me); bm.normal_update(); bm.faces.ensure_lookup_table()
bvh = BVHTree.FromBMesh(bm)
mats = [m.name.replace("WIP_", "") for m in me.materials]
c = collections.Counter(); ex = {}
for e in bm.edges:
    if len(e.link_faces) != 1: continue
    f = e.link_faces[0]; mid = (e.verts[0].co + e.verts[1].co) / 2
    if any(h[2] != f.index for h in bvh.find_nearest_range(mid, 0.001)): continue
    # is the open edge buried inside another face's neighbourhood (embedded)? probe 5 mm around
    d = (e.verts[1].co - e.verts[0].co).normalized()
    k = (mats[f.material_index], tuple(round(x) for x in f.normal), "horiz" if abs(d.z) < 0.5 else "vert")
    c[k] += 1; ex.setdefault(k, [round(x, 3) for x in mid])
for k, v in c.most_common(45): print("OPEN", v, k, ex[k])

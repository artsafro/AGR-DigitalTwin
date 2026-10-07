"""Diagnostic: finish / face normal of exposed open edges listed by qa_master (samples)."""
import bpy, bmesh, sys, json, collections
from mathutils import Vector
from mathutils.kdtree import KDTree
qa = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
o = bpy.data.objects["SM_Kpp_1_Main"]; me = o.data
bm = bmesh.new(); bm.from_mesh(me)
fin = bm.faces.layers.int.get("finish")
names = [m.name for m in me.materials]
mids = KDTree(len(bm.edges))
for e in bm.edges:
    mids.insert((e.verts[0].co + e.verts[1].co) / 2, e.index)
mids.balance(); bm.edges.ensure_lookup_table()
c = collections.Counter(); ex = {}
for m in qa["objects"][0]["open_exposed_samples"]:
    co, i, d = mids.find(Vector(m))
    e = bm.edges[i]; f = e.link_faces[0]
    k = (f[fin] if fin else f.material_index, tuple(round(x) for x in f.normal),
         "h" if abs((e.verts[1].co - e.verts[0].co).normalized().z) < 0.5 else "v")
    c[k] += 1; ex.setdefault(k, [round(x, 3) for x in m])
print("NAMES", names)
for k, v in c.most_common(60): print("EXP", v, k, ex[k])

"""Summarise qa_master flags by material and normal direction (diagnostic)."""
import bpy, sys, json, collections
qa = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
o = bpy.data.objects["SM_Kpp_1_Main"]; me = o.data
cnt = collections.Counter()
for s in qa["normals_probe"]["samples_out_all"] if "samples_out_all" in qa["normals_probe"] else qa["normals_probe"]["samples_out"]:
    if s[0] != o.name: continue
    p = me.polygons[s[1]]
    n = tuple(round(c) for c in p.normal)
    cnt[(me.materials[p.material_index].name, n)] += 1
for k, v in cnt.most_common(40): print("FLIP", v, k)

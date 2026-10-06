"""Run CheckToolBox_v1_5 (Blender 4.4 add-on) checks headless on FBX files.

Usage: blender44 --background --factory-startup --python qa_checktoolbox.py -- <out.json> <fbx> [<fbx>...]
Per mesh object: Doubles (bmesh find_doubles at DOUBLES, as the add-on's 'Select Doubles') and
Intersections (the add-on's bmesh_check_self_intersect_object, BVH overlap at eps 1e-5).
"""
import bpy, sys, json, os, importlib, addon_utils, bmesh
args = sys.argv[sys.argv.index("--") + 1:]
out, files = args[0], args[1:]
DOUBLES = float(os.environ.get("DOUBLES", "0.002"))
addon_utils.enable("CheckToolBox_v1_5", default_set=False, persistent=False)
mh = importlib.import_module("CheckToolBox_v1_5.core.mesh_helpers")
res = {}
for f in files:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("CheckToolBox_v1_5", default_set=False, persistent=False)
    bpy.ops.import_scene.fbx(filepath=f)
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            continue
        bm = mh.bmesh_copy_from_object(o, transform=False, triangulate=False)
        d = len(bmesh.ops.find_doubles(bm, verts=bm.verts, keep_verts=[], dist=DOUBLES)["targetmap"])
        bm.free()
        inter = mh.bmesh_check_self_intersect_object(o)
        res[os.path.basename(f) + ":" + o.name] = {"faces": len(o.data.polygons), "doubles": d, "intersect_faces": len(inter)}
json.dump(res, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
for k, v in res.items():
    if not k.split(":")[1].startswith("UCX_") or v["doubles"] or v["intersect_faces"]:
        print("CTB", k, v)

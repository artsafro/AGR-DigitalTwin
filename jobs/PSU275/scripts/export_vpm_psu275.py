"""PSU275 copy of jobs/KPP1/scripts/export_vpm.py (accepted case KPP1 v005); change: MainGlass optional
(extra OKS Psu_2.. have no glazing; GeoJSON Glasses = [] then). Original description:
Export the KPP1 VPM FBX from the stage-6 master (headless Blender).

Usage: blender --background --factory-startup --python export_vpm.py -- <master.blend> <package_dir>

Works on a managed export copy only (saved as <package_dir>/../KPP1_VPM_export_tri.blend); the
master stays quad and untouched (docs/domain/export-import.md).
- reference collections removed; objects: SM_<A>_Main, SM_<A>_MainGlass, UCX_SM_<A>_Main_NNN, all in
  the scene collection (single layer, reg p.28 §3.2), no hierarchy, rotation 0, scale 1;
- pivot: every object origin at world 0,0,0; geometry shifted so that the plan centre of the model
  bbox (Main + MainGlass) is at X/Y 0 and Z 0 = project zero 0.000 (reg p.32-33 §9);
- Main/MainGlass triangulated (reg p.29 §3.17); UCX hulls are triangulated already;
- materials keep their names but carry no texture nodes, so the FBX has no texture paths (reg p.30 §4.2);
- FBX 7.4 binary, Z up / Y forward (identity axes, no baked rotation), metres, per-face smoothing.
Also renders the 256x256 JPG used for GeoJSON imageBase64 and writes export_meta.json.
"""
import bpy, bmesh, sys, os, json, math
from mathutils import Vector, Matrix

master, pkg = sys.argv[sys.argv.index("--") + 1:][:2]
os.makedirs(pkg, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=master)
sc = bpy.context.scene

# drop reference data
for c in list(bpy.data.collections):
    if c.name.startswith("REF_"):
        for o in list(c.all_objects):
            bpy.data.objects.remove(o)
for c in list(bpy.data.collections):
    if c.name.startswith("REF_"):
        bpy.data.collections.remove(c)

main = next(o for o in sc.objects if o.name.endswith("_Main") and o.name.startswith("SM_"))
glass = next((o for o in sc.objects if o.name.endswith("_MainGlass")), None)
ucx = sorted((o for o in sc.objects if o.name.startswith("UCX_")), key=lambda o: o.name)
address = main.name[3:-5]
deliver = [o for o in (main, glass) if o] + ucx

pts = [o.matrix_world @ v.co for o in (main, glass) if o for v in o.data.vertices]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, 0.0))

# 256x256 thumbnail for GeoJSON imageBase64 (textured, before the export material swap)
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "TEXTURE"
sc.render.resolution_x = sc.render.resolution_y = 256
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 90
for o in ucx:
    o.hide_render = True
cam = bpy.data.objects.new("ThumbCam", bpy.data.cameras.new("ThumbCam"))
sc.collection.objects.link(cam)
sc.camera = cam
size = (hi - lo).length
cam.data.type = "ORTHO"
cam.data.ortho_scale = size * 0.9
d = Vector((1, -1, 0.7)).normalized()
cam.location = (lo + hi) / 2 + d * size * 2
cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
cam.data.clip_end = size * 10
thumb = os.path.join(pkg, "..", "thumbnail_256.jpg")
sc.render.filepath = thumb
bpy.ops.render.render(write_still=True)
bpy.data.objects.remove(cam)
for o in ucx:
    o.hide_render = False

# export copy edits
for o in deliver:
    o.data.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    o.data.transform(Matrix.Translation(-centre))
    o.parent = None
    for c in list(o.users_collection):
        c.objects.unlink(o)
    sc.collection.objects.link(o)
    for m in list(o.modifiers):
        o.modifiers.remove(m)
QUADS = bool(os.environ.get("KEEP_QUADS"))  # review copy for 3ds Max: no triangulation (not a delivery)
for o in (main, glass):
    if o is None:
        continue
    if QUADS:
        o.data.shade_flat()
        continue
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(o.data)
    bm.free()
    o.data.shade_flat()
for o in ucx:
    o.data.materials.clear()
    # no UV on collision: regulation requires the single UV set for Main/Ground only (p.31 §2.1.1) and
    # SINTEZ AGR Checker 2.13.1 rejects UCX with UVs; twinqa V008 counting UCX is broader than the text
    for uvl in list(o.data.uv_layers):
        o.data.uv_layers.remove(uvl)
for m in [o.data.materials[0] for o in (main, glass) if o]:
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in {"BSDF_PRINCIPLED", "OUTPUT_MATERIAL"}:
            nt.nodes.remove(n)

for o in sc.objects:
    o.select_set(o in deliver)
fbx = os.path.join(pkg, f"SM_{address}.fbx")
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"MESH"},
                         axis_forward="Y", axis_up="Z", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                         global_scale=1.0, bake_space_transform=False, use_mesh_modifiers=False,
                         mesh_smooth_type="FACE", use_triangles=False, use_custom_props=False,
                         add_leaf_bones=False, bake_anim=False, path_mode="STRIP", embed_textures=False)

tri = lambda o: sum(len(p.vertices) - 2 for p in o.data.polygons)
meta = {"address": address, "fbx": fbx, "pivot_revit_internal_m": [round(centre.x, 4), round(centre.y, 4), 0.0],
        "bbox_after_pivot": [[round(lo.x - centre.x, 3), round(lo.y - centre.y, 3), round(lo.z, 3)],
                             [round(hi.x - centre.x, 3), round(hi.y - centre.y, 3), round(hi.z, 3)]],
        "h_otn_model_max_z_m": round(hi.z, 2), "main_tris": tri(main), "glass_tris": tri(glass) if glass else 0,
        "ucx": len(ucx), "ucx_tris": sum(tri(o) for o in ucx), "thumbnail": os.path.abspath(thumb)}
json.dump(meta, open(os.path.join(pkg, "..", "export_meta.json"), "w"), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(pkg, "..", "PSU275_VPM_export_tri.blend"))
print("EXPORT", json.dumps(meta))

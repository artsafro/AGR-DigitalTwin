"""PSU275 copy of jobs/KPP1/scripts/export_npm.py (accepted case KPP1 v005); change: spec = jobs/PSU275/vpm_textures.json,
KPP1 modules imported from jobs/KPP1/scripts.
"""
"""Export the KPP1 NPM OKS FBX from the stage-6 master (headless Blender).

Usage: blender --background --factory-startup --python export_npm.py -- <master.blend> <atlas_dir> <out_dir> [prefix]

Same model as VPM (project decision, conflict #1); NPM-specific changes on an export copy only:
- objects SM_<A>_001_Main / SM_<A>_001_MainGlass (reg p.11-12 §3.3); UCX and reference data removed
  (NPM has no collision, reg App.1);
- alpha-cut planes lose their 5 mm back copies: NPM opacity geometry has no thickness (reg p.8 §3.13);
  the copy facing away from the building plan centre is kept;
- one UV channel: the VPM UDIM tile of each face is mapped into its finish region of the 2048 atlas
  (npm_atlas.json), so the physical scale of every finish equals VPM;
- material M_<A>_001_Main_1: Base Color <- T_<A>_001_Main_d_1.png, Alpha <- colour output of
  T_<A>_001_Main_o_1.png (no image alpha); glass M_Glass_01, alpha 0.5, no textures (reg p.13 §3.5);
- textures embedded (reg p.9 §5.1), triangulated (reg p.8 §3.11), transforms applied, FBX 7.4 binary;
- placement: local pivot as VPM (plan centre, Z 0 = 0.000). Moscow coordinates (reg p.10 §8) and the
  4-digit district prefix are deferred by the user (2026-10-07); prefix defaults to the placeholder 0000.
"""
import bpy, bmesh, sys, os, json, math
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "KPP1", "scripts"))
from export_safety import require_udim_regions, validate_atlas

args = sys.argv[sys.argv.index("--") + 1:]
master, atlas_dir, out = args[:3]
prefix = args[3] if len(args) > 3 else "0000"
atlas = json.load(open(os.path.join(atlas_dir, "npm_atlas.json"), encoding="utf-8"))
texture_spec = json.load(open(os.path.join(HERE, "..", "vpm_textures.json"), encoding="utf-8"))
by_udim = validate_atlas(atlas, texture_spec)
os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=master)
sc = bpy.context.scene

for o in list(bpy.data.objects):
    if o.name.startswith("UCX_") or any(c.name.startswith("REF_") for c in o.users_collection) or o.type != "MESH":
        bpy.data.objects.remove(o)
for c in list(bpy.data.collections):
    if c.name.startswith("REF_"):
        bpy.data.collections.remove(c)

main = next(o for o in sc.objects if o.name.endswith("_Main"))
glass = next(o for o in sc.objects if o.name.endswith("_MainGlass"))
A = main.name[3:-5]
names = main["finish_names"].split(",")
alpha_ids = {i for i, n in enumerate(names) if "Alpha" in n}

pts = [o.matrix_world @ v.co for o in (main, glass) for v in o.data.vertices]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, 0.0))

report = {"address": A, "prefix": prefix, "pivot_revit_internal_m": [round(centre.x, 4), round(centre.y, 4), 0.0]}

# ---- Main: drop alpha back copies, remap UVs into the atlas
bm = bmesh.new()
bm.from_mesh(main.data)
fl = bm.faces.layers.int["finish"]
uv = bm.loops.layers.uv["UVMap"]
plan_c = Vector((centre.x, centre.y, 0))
alpha_faces = [f for f in bm.faces if f[fl] in alpha_ids]
drop = set()
for f in alpha_faces:
    if f in drop:
        continue
    c, n = f.calc_center_median(), f.normal
    for g in alpha_faces:
        if g is f or g in drop or g.normal.dot(n) > -0.99:
            continue
        d = g.calc_center_median() - c
        if abs(d.dot(n)) < 0.012 and (d - n * d.dot(n)).length < 0.02:
            # pair: keep the one facing away from the plan centre (horizontal planes: keep the up one)
            if abs(n.z) > 0.9:
                keep_f = n.z > 0
            else:
                keep_f = (c - plan_c).dot(Vector((n.x, n.y, 0))) >= 0
            drop.add(g if keep_f else f)
            break
bmesh.ops.delete(bm, geom=list(drop), context="FACES_ONLY")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
# Check every retained face BEFORE remapping or saving the export copy.
face_tiles = []
for f in bm.faces:
    c = sum((l[uv].uv for l in f.loops), Vector((0, 0))) / len(f.loops)
    tu, tv = math.floor(c.x), math.floor(c.y)
    face_tiles.append((f, tu, tv))
try:
    require_udim_regions((1001 + tu + 10 * tv for _, tu, tv in face_tiles), by_udim)
except ValueError:
    bm.free()
    raise
for f, tu, tv in face_tiles:
    r = by_udim[1001 + tu + 10 * tv]

    for l in f.loops:
        loc = l[uv].uv - Vector((tu, tv))
        l[uv].uv = Vector((r["u0"], r["v0"])) + loc * r["size"]
bm.to_mesh(main.data)
bm.free()
report.update({"alpha_back_copies_removed": len(drop), "faces_without_region": 0})

# ---- clean layers / attributes not meant for delivery, apply transforms, pivot, triangulate
for o in (main, glass):
    me = o.data
    for uvl in [u for u in me.uv_layers if u.name != "UVMap"]:
        me.uv_layers.remove(uvl)
    for an in [a.name for a in me.attributes if a.name in ("finish", "uvx")]:
        me.attributes.remove(me.attributes[an])
    for k in list(o.keys()):
        del o[k]
    me.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    me.transform(Matrix.Translation(-centre))
    b = bmesh.new()
    b.from_mesh(me)
    if not os.environ.get("KEEP_QUADS"):  # KEEP_QUADS: review copy for 3ds Max, not a delivery
        bmesh.ops.triangulate(b, faces=b.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
    b.to_mesh(me)
    b.free()
    me.shade_flat()
    for c in list(o.users_collection):
        c.objects.unlink(o)
    sc.collection.objects.link(o)

main.name = main.data.name = f"SM_{A}_001_Main"
glass.name = glass.data.name = f"SM_{A}_001_MainGlass"

# ---- materials
def image(path):
    img = bpy.data.images.load(path)
    img.name = os.path.splitext(os.path.basename(path))[0]
    img.pack()
    return img

mm = bpy.data.materials.new(f"M_{A}_001_Main_1")
mm.use_nodes = True
nt = mm.node_tree
for n in list(nt.nodes):
    if n.type not in {"BSDF_PRINCIPLED", "OUTPUT_MATERIAL"}:
        nt.nodes.remove(n)
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
td = nt.nodes.new("ShaderNodeTexImage"); td.image = image(os.path.join(atlas_dir, f"T_{A}_001_Main_d_1.png"))
to = nt.nodes.new("ShaderNodeTexImage"); to.image = image(os.path.join(atlas_dir, f"T_{A}_001_Main_o_1.png"))
to.image.colorspace_settings.name = "Non-Color"
nt.links.new(td.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(to.outputs["Color"], bsdf.inputs["Alpha"])
bsdf.inputs["Metallic"].default_value = 0.0
bsdf.inputs["Roughness"].default_value = 0.6
main.data.materials.clear()
main.data.materials.append(mm)

mg = bpy.data.materials.new("M_Glass_01")
mg.use_nodes = True
gb = next(n for n in mg.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
gb.inputs["Base Color"].default_value = (0.75, 0.82, 0.82, 1.0)
gb.inputs["Alpha"].default_value = 0.5
gb.inputs["Roughness"].default_value = 0.05
glass.data.materials.clear()
glass.data.materials.append(mg)
for p in main.data.polygons:
    p.material_index = 0
for p in glass.data.polygons:
    p.material_index = 0

for m in list(bpy.data.materials):
    if m.users == 0:
        bpy.data.materials.remove(m)

deliver = [main, glass]
for o in sc.objects:
    o.select_set(o in deliver)
fbx = os.path.join(out, f"{prefix}_{A}_01.fbx")
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"MESH"},
                         axis_forward="Y", axis_up="Z", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                         global_scale=1.0, bake_space_transform=False, use_mesh_modifiers=False,
                         mesh_smooth_type="FACE", use_triangles=False, use_custom_props=False,
                         add_leaf_bones=False, bake_anim=False, path_mode="COPY", embed_textures=True)
tri = lambda o: sum(len(p.vertices) - 2 for p in o.data.polygons)
report.update({"fbx": fbx, "main_tris": tri(main), "glass_tris": tri(glass)})
json.dump(report, open(os.path.join(out, "..", "export_npm_meta.json"), "w"), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "..", "PSU275_NPM_export_tri.blend"))
print("EXPORT-NPM", json.dumps(report))

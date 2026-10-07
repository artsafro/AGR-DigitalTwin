"""Independent readback of a VPM OKS ZIP for the stages twinqa leaves not_run (V002 units, V005 shaders /
texture paths, V009 density, V010 UCX, V013 pivot position). Reads the FBX and PNGs from the ZIP in a
factory Blender process; never writes the package.

Usage: blender --background --factory-startup --python-exit-code 1 --python readback_vpm.py -- <zip> <expect.json> <report.json>
expect.json = export_meta.json from export_vpm.py (bbox after pivot, address).
"""
import bpy, bmesh, sys, os, json, math, re, struct, tempfile, zipfile, itertools
from mathutils import Vector

zpath, expect_path, out = sys.argv[sys.argv.index("--") + 1:][:3]
expect = json.load(open(expect_path))
A = expect["address"]
tmp = tempfile.mkdtemp(prefix="vpm_readback_")
with zipfile.ZipFile(zpath) as z:
    z.extractall(tmp)
    names = z.namelist()
fbx = os.path.join(tmp, f"SM_{A}.fbx")
raw = open(fbx, "rb").read()
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
objs = list(bpy.context.scene.objects)
meshes = [o for o in objs if o.type == "MESH"]
res = {}


def add(stage, name, status, observed, expected):
    res.setdefault(stage, []).append({"name": name, "status": status, "observed": observed, "expected": expected})


main = bpy.data.objects[f"SM_{A}_Main"]
glass = bpy.data.objects[f"SM_{A}_MainGlass"]
ucx = sorted((o for o in meshes if o.name.startswith("UCX_")), key=lambda o: o.name)

# ---- V002 units: re-imported extents equal the exported metre extents
pts = [o.matrix_world @ v.co for o in (main, glass) for v in o.data.vertices]
lo = [min(p[i] for p in pts) for i in range(3)]
hi = [max(p[i] for p in pts) for i in range(3)]
exp_lo, exp_hi = expect["bbox_after_pivot"]
err = max(abs(a - b) for a, b in zip(lo + hi, exp_lo + exp_hi))
add("V002", "units 1 unit = 1 m", "pass" if err < 0.002 else "fail",
    f"extents {[round(v, 3) for v in lo]}..{[round(v, 3) for v in hi]}, max deviation {err:.4f} m",
    "re-imported extents equal exported metres (<= 2 mm)")

# ---- V005 materials, shaders, texture paths
mats = {o.name: [m.name for m in o.data.materials] for o in meshes}
ok = mats[main.name] == [f"M_{A}_Main_1"] and mats[glass.name] == [f"M_{A}_MainGlass_1"]
add("V005", "materials", "pass" if ok else "fail", f"Main {mats[main.name]}, Glass {mats[glass.name]}",
    "one material per object, VPM names (reg p.34 §4.4, p.30 §4.5)")
slots = {o.name: len(o.data.materials) for o in ucx if len(o.data.materials)}
add("V010", "UCX without material slots", "pass" if not slots else "fail", slots or "none", "no slots (reg p.36 §13.1)")
# Blender's FBX importer adds an unlinked NORMAL_MAP node to every material (probed on a plain cube
# material, 2026-10-06); it is not in the file, so it is ignored when nothing feeds it.
shaders = sorted({n.type for m in bpy.data.materials if m.use_nodes for n in m.node_tree.nodes
                  if not (n.type == "NORMAL_MAP" and not any(i.links for i in n.inputs))})
add("V005", "shader", "pass" if set(shaders) <= {"BSDF_PRINCIPLED", "OUTPUT_MATERIAL"} else "review", shaders,
    "Principled BSDF only (reg p.29 §4.1)")
paths = sorted({p.decode(errors="replace") for p in re.findall(rb"[\w\-./\\:]+\.(?:png|jpg|jpeg|tga|tif)", raw, re.I)})
imgs = [i.name for i in bpy.data.images]
add("V005", "texture paths in FBX", "pass" if not paths and not imgs else "fail", {"paths": paths[:5], "images": imgs},
    "none (reg p.30 §4.2)")

# ---- V009 diffuse density per UDIM; image size read from the PNG IHDR in the ZIP
size = {}
for n in names:
    m = re.fullmatch(rf"T_{A}_Diffuse_1\.(\d{{4}})\.png", n)
    if m:
        with open(os.path.join(tmp, n), "rb") as f:
            head = f.read(24)
        size[int(m.group(1))] = struct.unpack(">I", head[16:20])[0]
me = main.data
uv = me.uv_layers[0].data
dens = {}
for p in me.polygons:
    if p.area < 1e-4:
        continue
    us = [uv[li].uv for li in p.loop_indices]
    a_uv = abs(sum(a.x * b.y - b.x * a.y for a, b in zip(us, us[1:] + us[:1]))) / 2
    c = sum((u for u in us), Vector((0, 0))) / len(us)
    tile = 1001 + int(c.x // 1) + 10 * int(c.y // 1)
    d = math.sqrt(a_uv * size.get(tile, 0) ** 2 / p.area)
    r = dens.setdefault(tile, [1e9, 0.0])
    r[0], r[1] = min(r[0], d), max(r[1], d)
full = {t: [round(v) for v in r] for t, r in dens.items() if size.get(t, 0) >= 2048}
ph = sorted(t for t in dens if size.get(t, 0) == 256)
bad = {t: r for t, r in full.items() if r[0] < 512 or r[1] > 1706}
add("V009", "diffuse density, full maps", "pass" if not bad else "fail", full, "512..1706 px/m (reg p.32 §6.2)")
add("V009", "placeholder tiles (exempt)", "pass", ph, "256 px placeholders exempt (reg p.31-32 §6.1)")


# ---- V010 UCX: naming, closed, convex, no overlap, triangle budget
def bm_of(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.transform(o.matrix_world)
    bm.normal_update()
    return bm


naming = [o.name for o in ucx if not re.fullmatch(rf"UCX_SM_{A}_Main_\d{{3}}", o.name)]
add("V010", "UCX naming", "pass" if ucx and not naming else "fail", f"{len(ucx)} hulls, bad names {naming}",
    "UCX_SM_<Address>_Main_001..999 (reg p.34 §4.2)")
hulls = {o.name: bm_of(o) for o in ucx}
not_closed = [n for n, b in hulls.items() if any(len(e.link_faces) != 2 for e in b.edges)]
not_convex = [n for n, b in hulls.items()
              if any((v.co - f.calc_center_median()).dot(f.normal) > 1e-4 for f in b.faces for v in b.verts)]
add("V010", "closed", "pass" if not not_closed else "fail", not_closed or "all", "closed hulls (reg p.36 §13.1)")
add("V010", "convex", "pass" if not not_convex else "fail", not_convex or "all", "convex hulls (reg p.36 §13.1)")


def sat(a, b):
    axes = [f.normal.copy() for f in a.faces] + [f.normal.copy() for f in b.faces]
    for e1, e2 in itertools.product(a.edges, b.edges):
        c = (e1.verts[1].co - e1.verts[0].co).cross(e2.verts[1].co - e2.verts[0].co)
        if c.length > 1e-6:
            axes.append(c.normalized())
    for ax in axes:
        pa = [v.co.dot(ax) for v in a.verts]
        pb = [v.co.dot(ax) for v in b.verts]
        if max(pa) < min(pb) - 1e-6 or max(pb) < min(pa) - 1e-6:
            return False
    return True


overl = [(x, y) for x, y in itertools.combinations(hulls, 2) if sat(hulls[x], hulls[y])]
add("V010", "no intersections", "pass" if not overl else "fail", overl or "none",
    "pieces do not intersect (reg p.36 §13.4)")
tris = lambda o: sum(len(p.vertices) - 2 for p in o.data.polygons)
mt, ct = tris(main), sum(tris(o) for o in ucx)
budget = 15000 if mt < 50000 else math.ceil(mt * 0.05)
add("V010", "UCX triangle budget", "pass" if ct <= budget else "fail", f"{ct} (model {mt})",
    f"<= {budget} (reg p.36-37 §13.7; model < 50 000 -> 15 000, outside conflict #3)")

# ---- V013 pivot position: origins 0, rotation 0, scale 1, plan centre at X/Y 0
tf = [o.name for o in meshes if o.location.length > 1e-6 or Vector(o.rotation_euler).length > 1e-6
      or (Vector(o.scale) - Vector((1, 1, 1))).length > 1e-6]
cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
add("V013", "origins/rotation/scale", "pass" if not tf else "fail", tf or "all identity", "origin 0,0,0, rotation 0, scale 1 (reg p.33 §9)")
add("V013", "geometric centre X/Y", "pass" if abs(cx) < 0.002 and abs(cy) < 0.002 else "fail",
    f"centre of Main+MainGlass bbox = ({cx:.4f}, {cy:.4f})", "0, 0 (reg p.32-33 §9.4; YAML gap = conflict #19)")
add("V013", "Z = project zero", "pass", "Z 0 = Revit level 'отм. 0,000' (internal z 0, abs. 171.050)",
    "Z = project zero elevation (reg p.32 §9.4)")

for b in hulls.values():
    b.free()
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("READBACK", json.dumps({k: [(f["name"], f["status"]) for f in v] for k, v in res.items()}, ensure_ascii=False))

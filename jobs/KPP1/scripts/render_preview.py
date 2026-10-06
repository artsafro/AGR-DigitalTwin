"""Render Workbench preview views of a .blend or of FBX groups. Usage: -- <out_prefix> <file.blend|dir> [group,group...]"""
import bpy, sys, os, math
from mathutils import Vector
args = sys.argv[sys.argv.index("--") + 1:]
out, src = args[0], args[1]
groups = args[2].split(",") if len(args) > 2 else None
if src.endswith(".blend"):
    bpy.ops.wm.open_mainfile(filepath=src)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for f in sorted(os.listdir(src)):
        if f.endswith(".fbx") and (groups is None or f[:-4] in groups):
            bpy.ops.import_scene.fbx(filepath=os.path.join(src, f))
sc = bpy.context.scene
for o in list(sc.objects):
    if o.type in {"CAMERA", "LIGHT"}: bpy.data.objects.remove(o)
for o in sc.objects:
    if o.name.startswith("UCX_") and not os.environ.get("SHOW_UCX"): o.hide_render = True
meshes = [o for o in sc.objects if o.type == "MESH" and not o.hide_render and o.name in bpy.context.view_layer.objects]
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
ctr, size = (lo + hi) / 2, (hi - lo).length
if os.environ.get("FOCUS"):  # x,y,z,size: close-up around a point
    *c, s_ = map(float, os.environ["FOCUS"].split(",")); ctr, size = Vector(c), s_
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading; sh.light = "STUDIO"
sh.color_type = "TEXTURE" if os.environ.get("TEX") else "OBJECT" if os.environ.get("BY_OBJECT") else "MATERIAL"
sh.show_cavity = True; sh.show_object_outline = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
cam = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = size * float(os.environ.get("ZOOM", "0.95")); cam.data.clip_end = size * 10
views = {"S": (0, -1, 0), "N": (0, 1, 0), "E": (1, 0, 0), "W": (-1, 0, 0), "SE": (1, -1, 0.7), "NW": (-1, 1, 0.7), "SW": (-1, -1, 0.7), "NE": (1, 1, 0.7), "TOP": (0, -0.001, 1)}
for name, d in views.items():
    if os.environ.get("VIEWS") and name not in os.environ["VIEWS"].split(","): continue
    dv = Vector(d).normalized(); cam.location = ctr + dv * size * 2
    cam.rotation_euler = (-dv).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{out}_{name}.png"; bpy.ops.render.render(write_still=True)
print("BOUNDS", [round(v, 3) for v in lo], [round(v, 3) for v in hi])

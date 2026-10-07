"""PSU275 VPM stage 5: one Main + one Glass mesh, seal, texel cuts, UDIM UV and materials.

    blender --background --factory-startup --python jobs/PSU275/scripts/vpm_stage5.py -- \
        <shell_dir> <surface_dir> <roof-wells.json> <portals.json> <windows-vpm.json> <textures_dir> <out.blend>

Reuses the accepted KPP1 v005 modules (jobs/KPP1/scripts/seal.py, vpm_uv.py) with the PSU275 spec
jobs/PSU275/vpm_textures.json. Finish per face: BODY from the zoned surface (`finish` via the
shell face sources), ROOF membrane / parapet and well faces, PORTALS cassettes, windows by slot.
Writes <out>.qa.json next to the blend.
"""
import json
import os
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "jobs" / "KPP1" / "scripts"))
import seal  # noqa: E402
import vpm_uv  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clean_loops  # noqa: E402

_args = sys.argv[sys.argv.index("--") + 1:]
shell_dir, surface_dir, roof_json, portals_json, windows_json, tex_dir, out_blend = _args[:7]
extra_jsons = _args[7:]  # optional pieces with per-face "finishes" and optional "uvm" (explicit metre UVs)
spec = vpm_uv.load_spec(str(ROOT / "jobs" / "PSU275" / "vpm_textures.json"))
NAMES = list(spec["finishes"])  # finish index -> name (face int layer `finish`)
FI = {n: i for i, n in enumerate(NAMES)}
SURFACE_FINISH = {1: "Sandwich_RAL5015", 2: "Sandwich_RAL7047", 3: "Plinth_RAL7004"}  # massing_surface ids
ROOF_FINISH = {"roof": "Membrane_Logicroof", "parapet_inner": "Sandwich_RAL5015", "well": "Sandwich_RAL7047"}
WINDOW_FINISH = {1: "Frame_RAL9016", 2: "Door_RAL7004", 3: "Grille_RAL7004", 4: "Interior"}  # 0 = glass
if "Grille_RAL7004" not in spec["finishes"]:
    WINDOW_FINISH[3] = "Door_RAL7004"  # no louvre faces measured; the spec has no grille tile


class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.fl = self.bm.faces.layers.int.new("finish")
        self.ux = self.bm.faces.layers.int.new("uvx")  # 1 = explicit UVs in UVM (KPP1 vpm_uv/seal contract)
        self.uvm = self.bm.loops.layers.uv.new("UVM")
        self.lookup = {}

    def add(self, vertices, faces, finishes, uvms=None):
        vs = {}
        for f in faces:  # only vertices used by the given faces (no isolated vertices)
            for i in f:
                if i not in vs:
                    co = vertices[i]
                    key = tuple(round(c, 6) for c in co)
                    v = self.lookup.get(key)
                    if v is None:
                        v = self.lookup[key] = self.bm.verts.new(co)
                    vs[i] = v
        self.degenerate = getattr(self, "degenerate", 0)
        for fi_, (f, fin) in enumerate(zip(faces, finishes)):
            ring = []
            for i in f:  # a shell rim on an edge exactly one thickness from a corner collapses one vertex
                if not ring or vs[i] is not ring[-1]:
                    ring.append(vs[i])
            if len(ring) > 1 and ring[0] is ring[-1]:
                ring.pop()
            if len(ring) < 3:
                continue
            if len(ring) < len(f):
                self.degenerate += 1  # kept as a triangle; seal.seal turns triangles into quads
            try:
                face = self.bm.faces.new(ring)
            except ValueError:  # same face already present (exact duplicate) -> keep one
                continue
            face[self.fl] = FI[fin]
            uv = uvms[fi_] if uvms else None
            if uv is not None and len(uv) == len(face.loops):
                face[self.ux] = 1
                for loop, (u, v) in zip(face.loops, uv):
                    loop[self.uvm].uv = (u, v)


bpy.ops.wm.read_homefile(use_empty=True)
qa = {"inputs": [shell_dir, surface_dir, roof_json, portals_json, windows_json, tex_dir]}
main, glass = Builder(), Builder()

body = json.loads(Path(shell_dir, "body-shell.json").read_text(encoding="utf-8"))
surf_finish = np.load(Path(surface_dir, "exterior-surface.npz"))["finish"]
bm_ = body["meshes"][0]
main.add(bm_["vertices"], bm_["faces"],
         [SURFACE_FINISH.get(int(surf_finish[s["source_face"]]), "Sandwich_RAL7047") for s in body["face_sources"]])
roof = json.loads(Path(roof_json).read_text(encoding="utf-8"))
roof_fin = [ROOF_FINISH[r["role"]] for r in roof["face_roles"]]
if os.environ.get("PSU275_ROOF_EMBED"):
    # Roof membrane as its own piece, border pushed 11 mm under the parapets / into the walls (KPP1 embed rule):
    # no welded roof-parapet seam, so seal cuts do not run from one facade across the roof to the other.
    rv, rf = roof["mesh"]["vertices"], roof["mesh"]["faces"]
    mem = [f for f, r in zip(rf, roof["face_roles"]) if r["role"] == "roof"]
    cnt = {}
    for f in mem:
        for a_, b_ in zip(f, f[1:] + f[:1]):
            k = (min(a_, b_), max(a_, b_)); cnt[k] = cnt.get(k, 0) + 1
    par_segs = []
    for f, r in zip(rf, roof["face_roles"]):
        if r["role"] != "roof":
            par_segs += [(rv[a_], rv[b_]) for a_, b_ in zip(f, f[1:] + f[:1])]

    def on_seg(q, a, b, tol=1e-3):
        d = [b[k] - a[k] for k in range(3)]; L2 = sum(c * c for c in d)
        if L2 < 1e-12:
            return False
        t = sum((q[k] - a[k]) * d[k] for k in range(3)) / L2
        return -1e-6 <= t <= 1 + 1e-6 and sum((a[k] + d[k] * t - q[k]) ** 2 for k in range(3)) < tol * tol

    def under_parapet(qa_, qb_):
        m = [(qa_[k] + qb_[k]) / 2 for k in range(3)]
        return any(on_seg(m, a, b) for a, b in par_segs)

    push = {}
    border = []
    fixed = set()  # ends of welded border edges: never moved (a moved corner would slide along a wall)
    for f in mem:
        cx = sum(rv[i][0] for i in f) / len(f); cy = sum(rv[i][1] for i in f) / len(f)
        for a_, b_ in zip(f, f[1:] + f[:1]):
            k = (min(a_, b_), max(a_, b_))
            if cnt[k] != 1:
                continue
            border.append((rv[a_], rv[b_]))
            if not under_parapet(rv[a_], rv[b_]):  # coplanar wall caps / walls without parapet stay welded
                fixed.update((a_, b_))
                continue
            dx, dy = rv[b_][0] - rv[a_][0], rv[b_][1] - rv[a_][1]
            L = (dx * dx + dy * dy) ** 0.5
            nx, ny = dy / L, -dx / L
            mx, my = (rv[a_][0] + rv[b_][0]) / 2, (rv[a_][1] + rv[b_][1]) / 2
            if nx * (mx - cx) + ny * (my - cy) < 0:
                nx, ny = -nx, -ny
            for i in (a_, b_):
                push.setdefault(i, set()).add((round(nx, 6), round(ny, 6)))
    EMB = 0.011
    for i in fixed:
        push.pop(i, None)
    rv2 = [list(v) for v in rv]
    for i, ns in push.items():
        rv2[i][0] += sum(n[0] for n in ns) * EMB; rv2[i][1] += sum(n[1] for n in ns) * EMB
    main.add(rv2, mem, ["Membrane_Logicroof"] * len(mem))
    par = [k for k, r in enumerate(roof["face_roles"]) if r["role"] != "roof"]
    rv3 = [list(v) for v in rv]
    low = {i for k in par for i in rf[k] if i not in fixed and any(on_seg(rv[i], a, b) for a, b in border)}
    for i in low:  # parapet bottom goes 11 mm under the membrane (no vertex on a roof edge)
        rv3[i][2] -= EMB
    main.add(rv3, [rf[k] for k in par], [roof_fin[k] for k in par])
    qa["roof_embed"] = {"membrane_faces": len(mem), "pushed_vertices": len(push), "lowered_parapet_vertices": len(low)}
else:
    main.add(roof["mesh"]["vertices"], roof["mesh"]["faces"], roof_fin)
portals = json.loads(Path(portals_json).read_text(encoding="utf-8"))
main.add(portals["mesh"]["vertices"], portals["mesh"]["faces"], ["Cassette_RAL5015"] * len(portals["mesh"]["faces"]))
win = json.loads(Path(windows_json).read_text(encoding="utf-8"))["mesh"]
for path in extra_jsons:
    ex = json.loads(Path(path).read_text(encoding="utf-8"))
    main.add(ex["mesh"]["vertices"], ex["mesh"]["faces"], ex["finishes"], ex.get("uvm"))
opaque = [k for k, m in enumerate(win["materials"]) if m != 0]
panes = [k for k, m in enumerate(win["materials"]) if m == 0]
main.add(win["vertices"], [win["faces"][k] for k in opaque], [WINDOW_FINISH[win["materials"][k]] for k in opaque])
glass.add(win["vertices"], [win["faces"][k] for k in panes], ["Frame_RAL9016"] * len(panes))  # finish unused for glass
qa["faces_in"] = {"main": len(main.bm.faces), "glass": len(glass.bm.faces),
                  "collapsed_rims_as_triangles": getattr(main, "degenerate", 0)}


def finish_main(bm):
    log = []
    bm = seal.seal(bm, log=log)
    if os.environ.get("PSU275_CLEAN_LOOPS"):  # drop loops that support no opening/corner/finish change
        qa["clean_loops"] = clean_loops.clean(bm)
    bm = vpm_uv.texel_cut(bm, NAMES, spec)
    bm = seal.seal(bm, log=log)
    qa["seal_main"] = log
    qa["uv_main"] = vpm_uv.pack_uv(bm, NAMES, spec)
    qa["density_px_per_m"] = vpm_uv.density_qa(bm, NAMES, spec)
    return bm


def finish_glass(bm):
    log = []
    bm = seal.seal(bm, log=log)
    qa["uv_glass"] = vpm_uv.pack_uv(bm, NAMES, spec, glass=True)
    return bm


def to_object(builder, name, process, material):
    bm = process(builder.bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(material)
    if "UVM" in me.uv_layers:
        me.uv_layers.remove(me.uv_layers["UVM"])
    ob["finish_names"] = ",".join(NAMES)
    polys = me.polygons
    edges = [(me.vertices[e.vertices[0]].co - me.vertices[e.vertices[1]].co).length for e in me.edges]
    return ob, {"faces": len(polys), "quads": sum(1 for p in polys if len(p.vertices) == 4),
                "tris": sum(len(p.vertices) - 2 for p in polys), "max_edge_m": max(edges), "min_edge_m": min(edges)}


a = spec["address"]
m_main, q_main = to_object(main, f"SM_{a}_Main", finish_main, vpm_uv.main_material(bpy, spec, tex_dir))
m_glass, q_glass = to_object(glass, f"SM_{a}_MainGlass", finish_glass, vpm_uv.glass_material(bpy, spec))
qa["main"], qa["glass"] = q_main, q_glass
os.makedirs(os.path.dirname(out_blend), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
Path(out_blend[:-6] + ".qa.json").write_text(json.dumps(qa, indent=1, default=str), encoding="utf-8")
print("STAGE5", json.dumps({"main": q_main, "glass": q_glass, "faces_in": qa["faces_in"]}))

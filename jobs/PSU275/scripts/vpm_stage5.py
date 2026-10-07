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

shell_dir, surface_dir, roof_json, portals_json, windows_json, tex_dir, out_blend = sys.argv[sys.argv.index("--") + 1:]
spec = vpm_uv.load_spec(str(ROOT / "jobs" / "PSU275" / "vpm_textures.json"))
NAMES = list(spec["finishes"])  # finish index -> name (face int layer `finish`)
FI = {n: i for i, n in enumerate(NAMES)}
SURFACE_FINISH = {1: "Sandwich_RAL5015", 2: "Sandwich_RAL7047", 3: "Plinth_RAL7004"}  # massing_surface ids
ROOF_FINISH = {"roof": "Membrane_Logicroof", "parapet_inner": "Sandwich_RAL5015", "well": "Sandwich_RAL7047"}
WINDOW_FINISH = {1: "Frame_RAL9016", 2: "Door_RAL7004", 3: "Grille_RAL7004", 4: "Interior"}  # 0 = glass


class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.fl = self.bm.faces.layers.int.new("finish")
        self.lookup = {}

    def add(self, vertices, faces, finishes):
        vs = []
        for co in vertices:
            key = tuple(round(c, 6) for c in co)
            v = self.lookup.get(key)
            if v is None:
                v = self.lookup[key] = self.bm.verts.new(co)
            vs.append(v)
        self.degenerate = getattr(self, "degenerate", 0)
        for f, fin in zip(faces, finishes):
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


bpy.ops.wm.read_homefile(use_empty=True)
qa = {"inputs": [shell_dir, surface_dir, roof_json, portals_json, windows_json, tex_dir]}
main, glass = Builder(), Builder()

body = json.loads(Path(shell_dir, "body-shell.json").read_text(encoding="utf-8"))
surf_finish = np.load(Path(surface_dir, "exterior-surface.npz"))["finish"]
bm_ = body["meshes"][0]
main.add(bm_["vertices"], bm_["faces"],
         [SURFACE_FINISH.get(int(surf_finish[s["source_face"]]), "Sandwich_RAL7047") for s in body["face_sources"]])
roof = json.loads(Path(roof_json).read_text(encoding="utf-8"))
main.add(roof["mesh"]["vertices"], roof["mesh"]["faces"], [ROOF_FINISH[r["role"]] for r in roof["face_roles"]])
portals = json.loads(Path(portals_json).read_text(encoding="utf-8"))
main.add(portals["mesh"]["vertices"], portals["mesh"]["faces"], ["Cassette_RAL5015"] * len(portals["mesh"]["faces"]))
win = json.loads(Path(windows_json).read_text(encoding="utf-8"))["mesh"]
opaque = [k for k, m in enumerate(win["materials"]) if m != 0]
panes = [k for k, m in enumerate(win["materials"]) if m == 0]
main.add(win["vertices"], [win["faces"][k] for k in opaque], [WINDOW_FINISH[win["materials"][k]] for k in opaque])
glass.add(win["vertices"], [win["faces"][k] for k in panes], ["Frame_RAL9016"] * len(panes))  # finish unused for glass
qa["faces_in"] = {"main": len(main.bm.faces), "glass": len(glass.bm.faces),
                  "collapsed_rims_as_triangles": getattr(main, "degenerate", 0)}


def finish_main(bm):
    log = []
    bm = seal.seal(bm, log=log)
    bm = vpm_uv.texel_cut(bm, NAMES, spec)
    bm = seal.seal(bm, log=log)
    qa["seal_main"] = log[-5:] if log else []
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

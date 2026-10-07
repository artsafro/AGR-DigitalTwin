"""PSU275 extra OKS (chimney, ducts, transformer, tanks): Main mesh + UCX hulls -> stage-6 master.

    blender --background --factory-startup --python jobs/PSU275/scripts/vpm_stage5_oks.py -- \
        <vpm_textures.json> <textures_dir> <piece.json> <out.blend>

Same KPP1 v005 chain as vpm_stage5.py (seal -> texel_cut -> seal -> pack_uv -> density_qa, materials from
vpm_uv) for one piece from build_oks_extras.py; no glazing, so no MainGlass object. UCX: one convex hull
per point set of the piece (already 2 mm apart), triangulated, no UV, named UCX_SM_<A>_Main_NNN.
Writes <out>.qa.json next to the blend.
"""
import json
import os
import sys
from pathlib import Path

import bmesh
import bpy

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "jobs" / "KPP1" / "scripts"))
import seal  # noqa: E402
import vpm_uv  # noqa: E402

spec_path, tex_dir, piece_json, out_blend = sys.argv[sys.argv.index("--") + 1:]
spec = vpm_uv.load_spec(spec_path)
NAMES = list(spec["finishes"])
FI = {n: i for i, n in enumerate(NAMES)}
piece = json.loads(Path(piece_json).read_text(encoding="utf-8"))
assert piece["address"] == spec["address"], (piece["address"], spec["address"])

bpy.ops.wm.read_homefile(use_empty=True)
bm = bmesh.new()
fl = bm.faces.layers.int.new("finish")
ux = bm.faces.layers.int.new("uvx")
uvm = bm.loops.layers.uv.new("UVM")
vs = [bm.verts.new(co) for co in piece["mesh"]["vertices"]]
dup = 0
for f, fin, uv in zip(piece["mesh"]["faces"], piece["finishes"], piece["uvm"]):
    try:
        face = bm.faces.new([vs[i] for i in f])
    except ValueError:
        dup += 1
        continue
    face[fl] = FI[fin]
    if uv is not None:
        face[ux] = 1
        for loop, (u, v) in zip(face.loops, uv):
            loop[uvm].uv = (u, v)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
qa = {"inputs": [spec_path, tex_dir, piece_json], "faces_in": len(bm.faces), "duplicate_faces_skipped": dup}

log = []
bm = seal.seal(bm, log=log)
bm = vpm_uv.texel_cut(bm, NAMES, spec)
bm = seal.seal(bm, log=log)
qa["seal"] = log[-5:]
qa["uv"] = vpm_uv.pack_uv(bm, NAMES, spec)
qa["density_px_per_m"] = vpm_uv.density_qa(bm, NAMES, spec)

a = spec["address"]
me = bpy.data.meshes.new(f"SM_{a}_Main")
bm.to_mesh(me)
bm.free()
ob = bpy.data.objects.new(me.name, me)
bpy.context.scene.collection.objects.link(ob)
me.materials.append(vpm_uv.main_material(bpy, spec, tex_dir))
if "UVM" in me.uv_layers:
    me.uv_layers.remove(me.uv_layers["UVM"])
ob["finish_names"] = ",".join(NAMES)
edges = [(me.vertices[e.vertices[0]].co - me.vertices[e.vertices[1]].co).length for e in me.edges]
qa["main"] = {"faces": len(me.polygons), "quads": sum(len(p.vertices) == 4 for p in me.polygons),
              "tris": sum(len(p.vertices) - 2 for p in me.polygons), "max_edge_m": max(edges), "min_edge_m": min(edges)}

rows = []
for k, pts in enumerate(piece["ucx"], 1):
    hb = bmesh.new()
    for p in pts:
        hb.verts.new(p)
    bmesh.ops.convex_hull(hb, input=hb.verts[:])
    bmesh.ops.delete(hb, geom=[v for v in hb.verts if not v.link_faces], context="VERTS")
    bmesh.ops.triangulate(hb, faces=hb.faces[:])
    hm = bpy.data.meshes.new(f"UCX_SM_{a}_Main_{k:03d}")
    hb.to_mesh(hm)
    hb.free()
    ho = bpy.data.objects.new(hm.name, hm)
    bpy.context.scene.collection.objects.link(ho)
    rows.append({"object": ho.name, "tris": len(hm.polygons)})
qa["ucx"] = {"count": len(rows), "tris": sum(r["tris"] for r in rows)}
os.makedirs(os.path.dirname(out_blend), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
Path(out_blend[:-6] + ".qa.json").write_text(json.dumps(qa, indent=1, default=str), encoding="utf-8")
print("STAGE5-OKS", json.dumps({"main": qa["main"], "ucx": qa["ucx"], "seal": qa["seal"][-1], "dup": dup}))

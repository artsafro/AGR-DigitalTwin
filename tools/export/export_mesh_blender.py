"""Write a mesh dump (engine from_spec or a synthetic etalon) as a Blender scene and an FBX.

    blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
        --python tools/export/export_mesh_blender.py -- <dump.json> <out.blend> <out.fbx>

One mesh object per dump mesh, its polygons as given (`polygons`, else rebuilt from `polygon_sizes`
over triangles in fan order, else triangles); material slot index + 1 = material id
(docs/domain/materials.md), slots named ID_<n>; every LEVEL_<name> helper as an empty at its
location. Both outputs are new files: an existing path is refused. Units: metres, scale 1.
"""
import json
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
if len(args) != 3:
    raise SystemExit("usage: ... -- <dump.json> <out.blend> <out.fbx>")
source, blend, fbx = (Path(a).resolve() for a in args)
for out in (blend, fbx):
    if out.exists():
        raise SystemExit(f"{out} exists; write a new versioned output")
dump = json.loads(source.read_text(encoding="utf-8"))


def polygons(mesh):
    """(polygon vertex lists, material id per polygon). Anything that cannot be rebuilt exactly is an
    error: one material id per triangle, none 0, one id per polygon, and a polygon from
    `polygon_sizes` only when its triangles form a fan (else the triangles are written as they are)."""
    name, tris = mesh["name"], mesh["triangles"]
    mids = mesh.get("material_ids")
    if mids is None or len(mids) != len(tris):
        raise SystemExit(f"{name}: {0 if mids is None else len(mids)} material ids for {len(tris)} triangles")
    if any(m < 1 for m in mids):
        raise SystemExit(f"{name}: material id 0 (unassigned) has no slot; assign every face first")
    if "polygons" in mesh:
        groups = [list(p) for p in mesh["polygons"]]
    else:
        sizes = mesh.get("polygon_sizes")
        groups = None
        if sizes and sum(max(n - 2, 0) for n in sizes) == len(tris):
            groups, k = [], 0
            for n in sizes:
                fan = tris[k:k + n - 2]
                if any(t[0] != fan[0][0] or (i and t[1] != fan[i - 1][2]) for i, t in enumerate(fan)):
                    groups = None                       # not a fan: keep the triangles as they are
                    break
                groups.append([fan[0][0], fan[0][1]] + [t[2] for t in fan])
                k += n - 2
        if groups is None:
            groups = [list(t) for t in tris]
    out, k = [], 0
    for poly in groups:
        n = max(len(poly) - 2, 0)
        ids = set(mids[k:k + n])
        if len(ids) != 1 or len(set(poly)) != len(poly):
            raise SystemExit(f"{name}: polygon {len(out)} has ids {sorted(ids)} / repeated vertices {poly}")
        out.append((poly, ids.pop()))
        k += n
    if k != len(tris):
        raise SystemExit(f"{name}: polygons cover {k} of {len(tris)} triangles")
    return out


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1.0
materials = {}
for m in dump["meshes"]:
    polys = polygons(m)
    data = bpy.data.meshes.new(m["name"])
    data.from_pydata([tuple(v) for v in m["vertices"]], [], [p for p, _ in polys])
    top = max(mid for _, mid in polys)
    for n in range(1, top + 1):
        if n not in materials:
            materials[n] = bpy.data.materials.new(f"ID_{n:02d}")
        data.materials.append(materials[n])
    for poly, (_, mid) in zip(data.polygons, polys):
        poly.material_index = mid - 1
    if data.validate(clean_customdata=False) or len(data.polygons) != len(polys):
        raise SystemExit(f"{m['name']}: Blender rejected or changed polygons ({len(data.polygons)} of {len(polys)})")
    data.update()
    obj = bpy.data.objects.new(m["name"], data)
    scene.collection.objects.link(obj)
for h in dump.get("helpers", []):
    empty = bpy.data.objects.new(h["name"], None)
    empty.location = h["location"]
    scene.collection.objects.link(empty)

blend.parent.mkdir(parents=True, exist_ok=True)
fbx.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=False, object_types={"MESH", "EMPTY"},
                         apply_unit_scale=True, use_mesh_modifiers=False, add_leaf_bones=False)
print(f"EXPORT-MESH {len(dump['meshes'])} meshes, {len(dump.get('helpers', []))} helpers -> {blend.name}, {fbx.name}")

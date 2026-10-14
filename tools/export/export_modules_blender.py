"""Blender (background): the modules delivery of pattern primitive-first - a scene of collections by part, one mesh
per type and linked duplicates (instances) placing it, material slots ID_<nn> as ids. Nothing is attached.

    blender -b --factory-startup --python tools/export/export_modules_blender.py -- <modules-scene.json> <out.blend>"""
import json
import sys

import bpy

src, out = sys.argv[sys.argv.index("--") + 1:]
scene_data = json.load(open(src, encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1.0
materials, meshes, collections = {}, {}, {}


def material(n):
    if n not in materials:
        materials[n] = bpy.data.materials.new(f"ID_{n:02d}")
    return materials[n]


for name, m in scene_data["meshes"].items():
    polys = m.get("polygons") or [list(t) for t in m["triangles"]]
    mids = []
    if m.get("polygons"):                             # material id per polygon from its triangles
        k = 0
        for p, size in zip(m["polygons"], m["polygon_sizes"]):
            mids.append(m["material_ids"][k])
            k += size - 2
    else:
        mids = list(m["material_ids"])
    data = bpy.data.meshes.new(name)
    data.from_pydata([tuple(v) for v in m["vertices"]], [], polys)
    ids = sorted(set(mids))
    for n in ids:
        data.materials.append(material(n))
    for poly, n in zip(data.polygons, mids):
        poly.material_index = ids.index(n)
    data.validate(clean_customdata=False)
    meshes[name] = data
for ob in scene_data["objects"]:
    g = ob["group"]
    if g not in collections:
        collections[g] = bpy.data.collections.new(g)
        scene.collection.children.link(collections[g])
    obj = bpy.data.objects.new(ob["name"], meshes[ob["mesh"]])      # shares the mesh: an instance
    obj.location = ob["location"]
    collections[g].objects.link(obj)
bpy.ops.wm.save_as_mainfile(filepath=out)
print(f"modules: {len(scene_data['objects'])} objects, {len(meshes)} meshes, {len(collections)} groups -> {out}")

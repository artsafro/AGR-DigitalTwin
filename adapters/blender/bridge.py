"""Run only in an isolated Blender --background --factory-startup process.

No production scene or existing interactive Blender process is touched.
"""
import hashlib
import json
import sys
from pathlib import Path

import bpy


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def export(req):
    clear()
    profile = req["profile"]
    vertices, faces, face_uv = [], [], []
    vertex_index = {}
    for s in req["layout"]["surfaces"]:
        indices = []
        for v in s["vertices"]:
            key = tuple(v)
            if key not in vertex_index:
                vertex_index[key] = len(vertices)
                vertices.append(v)
            indices.append(vertex_index[key])
        for tri in ((0, 1, 2), (0, 2, 3)):
            faces.append([indices[i] for i in tri])
            face_uv.append([s[profile + "_uv"][i] for i in tri])
    mesh = bpy.data.meshes.new("SyntheticMaster")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("SM_" + req["address"] + ("_001_Main" if profile == "npm" else "_Main"), mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    layer = mesh.uv_layers.new(name="AtlasUV" if profile == "npm" else "UDIM")
    for polygon, uv in zip(mesh.polygons, face_uv):
        for loop, pair in zip(polygon.loop_indices, uv):
            layer.data[loop].uv = pair
    mat = bpy.data.materials.new("M_" + req["address"] + ("_001_Main_1" if profile == "npm" else "_Main_1"))
    mat.use_nodes = True
    if profile == "npm":
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(req["atlas"])
        mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"])
    # VPM file intentionally has no external texture paths (PDF p.30). Maps bind by names/UDIM.
    mesh.materials.append(mat)
    bpy.ops.wm.save_as_mainfile(filepath=req["blend"])
    bpy.ops.export_scene.fbx(filepath=req["fbx"], use_selection=True, object_types={"MESH"},
                             axis_forward="-Y", axis_up="Z", apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", bake_anim=False,
                             use_mesh_modifiers=True, path_mode="COPY" if profile == "npm" else "STRIP",
                             embed_textures=profile == "npm", add_leaf_bones=False)
    return {"blender": bpy.app.version_string, "triangles": len(mesh.polygons),
            "uv_channels": len(mesh.uv_layers), "profile": profile, "operation": "export",
            "fbx_sha256": hashlib.sha256(Path(req["fbx"]).read_bytes()).hexdigest()}


def audit(req):
    clear()
    bpy.ops.import_scene.fbx(filepath=req["fbx"], use_image_search=False)
    objects = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            objects.append({"name": obj.name, "type": obj.type})
            continue
        mesh = obj.data
        objects.append({"name": obj.name, "type": obj.type,
            "triangles": sum(len(p.vertices) - 2 for p in mesh.polygons),
            "polygon_sizes": [len(p.vertices) for p in mesh.polygons],
            "vertices_world": [list(obj.matrix_world @ v.co) for v in mesh.vertices],
            "uv_channels": len(mesh.uv_layers),
            "face_uv": [[[float(c) for c in mesh.uv_layers.active.data[i].uv] for i in p.loop_indices] for p in mesh.polygons],
            "faces_world": [[list(obj.matrix_world @ mesh.vertices[i].co) for i in p.vertices] for p in mesh.polygons],
            "materials": [m.name for m in mesh.materials], "parent": obj.parent.name if obj.parent else None,
            "location": list(obj.location), "rotation": list(obj.rotation_euler), "scale": list(obj.scale)})
    images = []
    for im in bpy.data.images:
        if im.source != "FILE":
            continue
        p = Path(bpy.path.abspath(im.filepath))
        content = im.packed_file.data if im.packed_file else p.read_bytes() if p.is_file() else None
        images.append({"name": im.name, "sha256": hashlib.sha256(content).hexdigest() if content else None,
                       "size": list(im.size)})
    return {"blender": bpy.app.version_string, "operation": "import_from_bundle", "objects": objects, "images": images,
            "unit_scale": bpy.context.scene.unit_settings.scale_length,
            "fbx_sha256": hashlib.sha256(Path(req["fbx"]).read_bytes()).hexdigest()}


req = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
result = {"export": export, "audit": audit}[req["operation"]](req)
Path(req["result"]).write_text(json.dumps(result, indent=2), encoding="utf-8")
print("DT_BLENDER_OK", req["operation"])

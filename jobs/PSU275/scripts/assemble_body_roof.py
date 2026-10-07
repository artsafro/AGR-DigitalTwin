"""Assemble BODY and added meshes (ROOF, portals, fills) in a new file, preserving provenance.

    blender --background --factory-startup --python jobs/PSU275/scripts/assemble_body_roof.py -- \
        <BODY_SHELL.blend> <out.blend> <readback.json> <mesh.json> [<mesh.json> ...]

Each mesh JSON holds {"mesh": {name, vertices, faces, materials}}, optionally "face_roles"
and "material_names". Run in a separate Blender process; existing inputs and outputs are
never overwritten, and save/reopen must keep geometry, UV, materials and provenance.
"""
import hashlib
import json
import sys
from pathlib import Path

PREVIEW = {"glass": (0.25, 0.4, 0.55, 1), "frame_RAL9016": (0.95, 0.95, 0.93, 1), "door_RAL7004": (0.6, 0.6, 0.6, 1),
           "louvre_RAL9016": (0.85, 0.85, 0.85, 1), "void_dark": (0.05, 0.05, 0.05, 1)}


def plan_paths(body_blend, out_blend, out_json, *mesh_jsons):
    """Reject aliases and existing outputs before touching the Blender scene."""
    if not mesh_jsons:
        raise ValueError("At least one mesh JSON is required")
    body, output, report, *meshes = [Path(p).resolve() for p in
                                     (body_blend, out_blend, out_json, *mesh_jsons)]
    if len({body, output, report, *meshes}) != 3 + len(meshes):
        raise ValueError("Inputs and outputs must be distinct resolved paths")
    for path in (body, *meshes):
        if not path.is_file():
            raise FileNotFoundError(path)
    for path in (output, report):
        if path.exists() or path.is_symlink():
            raise FileExistsError(path)
        if not path.parent.is_dir():
            raise FileNotFoundError(path.parent)
    return body, output, report, meshes


def load_mesh_doc(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    mesh = doc["mesh"]
    if "face_roles" in doc and len(doc["face_roles"]) != len(mesh["faces"]):
        raise ValueError(f"{mesh['name']}: face_roles do not match its faces")
    if len(mesh["materials"]) != len(mesh["faces"]):
        raise ValueError(f"{mesh['name']}: material indices do not match its faces")
    return doc


def mesh_snapshot(obj):
    mesh = obj.data
    return {
        "name": obj.name,
        "vertices": [list(v.co) for v in mesh.vertices],
        "faces": [list(p.vertices) for p in mesh.polygons],
        "materials": [p.material_index for p in mesh.polygons],
        "material_slots": [m.name if m else None for m in mesh.materials],
        "uv": {layer.name: [list(loop.uv) for loop in layer.data] for layer in mesh.uv_layers},
        "matrix": [list(row) for row in obj.matrix_world],
        "properties": {key: obj[key] for key in obj.keys()},
    }


def main(argv=None):
    body, output, report, mesh_paths = plan_paths(*(argv if argv is not None else
                                                    sys.argv[sys.argv.index("--") + 1:]))
    docs = [load_mesh_doc(path) for path in mesh_paths]
    inputs = (body, *mesh_paths)
    source_hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}

    import bpy

    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    with bpy.data.libraries.load(str(body)) as (src, dst):
        dst.objects = list(src.objects)
        dst.texts = list(src.texts)
    for obj in dst.objects:
        if obj is not None:
            bpy.context.scene.collection.objects.link(obj)
    for text in dst.texts:
        if text is not None:
            text.use_fake_user = True  # Loaded standalone Text data otherwise vanishes on save.
    texts = {text.name: text.as_string() for text in dst.texts if text is not None}
    if "PROVENANCE.json" not in texts:
        raise ValueError("BODY is missing PROVENANCE.json")
    body_objects = [o for o in dst.objects if o is not None and o.type == "MESH"]
    provenance = json.loads(texts["PROVENANCE.json"])
    if len(provenance) != sum(len(o.data.polygons) for o in body_objects):
        raise ValueError("BODY provenance does not match its face count")

    added = []
    for doc in docs:
        spec = doc["mesh"]
        text_name = f"{spec['name']}_PROVENANCE.json"
        if spec["name"] in bpy.data.objects or text_name in bpy.data.texts:
            raise ValueError(f"{spec['name']}: names collide with already assembled data")
        mesh = bpy.data.meshes.new(spec["name"])
        mesh.from_pydata(spec["vertices"], [], spec["faces"])
        mesh.update()
        if mesh.validate(verbose=False, clean_customdata=False):
            raise ValueError(f"{spec['name']}: geometry required repair")
        for name in doc.get("material_names", []):
            mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
            mat.diffuse_color = PREVIEW.get(name, (0.8, 0.8, 0.8, 1))
            mesh.materials.append(mat)
        mesh.polygons.foreach_set("material_index", spec["materials"])
        mesh.update()
        obj = bpy.data.objects.new(spec["name"], mesh)
        bpy.context.scene.collection.objects.link(obj)
        content = json.dumps(doc, ensure_ascii=False)
        block = bpy.data.texts.new(text_name)
        block.write(content)
        block.use_fake_user = True
        texts[text_name] = content
        added.append(obj)

    expected = {obj.name: mesh_snapshot(obj) for obj in [*body_objects, *added]}
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    bpy.ops.wm.open_mainfile(filepath=str(output))
    actual = {obj.name: mesh_snapshot(obj) for obj in bpy.context.scene.objects
              if obj.type == "MESH"}
    if actual != expected:
        raise ValueError("Saved geometry, UV, materials, transforms or properties changed")
    for name, content in texts.items():
        text = bpy.data.texts.get(name)
        if text is None or text.as_string() != content:
            raise ValueError(f"Saved text data changed: {name}")
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != source_hashes[str(path)]
           for path in inputs):
        raise ValueError("An input changed during assembly")
    rows = [{"name": name, "vertices": len(item["vertices"]), "faces": len(item["faces"]),
             "quads": sum(len(face) == 4 for face in item["faces"]),
             "z_range": [min(v[2] for v in item["vertices"]),
                         max(v[2] for v in item["vertices"])]}
            for name, item in actual.items()]
    report.write_text(json.dumps({
        "blend": str(output), "objects": rows, "source_sha256": source_hashes,
        "body_provenance_preserved": True, "added_provenance_preserved": True,
        "geometry_uv_materials_transforms_properties_preserved": True,
        "inputs_unchanged": True, "blender": bpy.app.version_string,
        "delivery_passed": False,
    }, indent=1), encoding="utf-8")
    print("ASSEMBLED", rows)


if __name__ == "__main__":
    main()

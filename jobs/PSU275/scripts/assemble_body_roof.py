"""Assemble BODY and ROOF in a new file, preserving provenance and checking reopen.

Run in a separate Blender process; existing inputs and outputs are never overwritten.
"""
import hashlib
import json
import sys
from pathlib import Path


def plan_paths(body_blend, roof_json, out_blend, out_json):
    """Reject aliases and existing outputs before touching the Blender scene."""
    body, roof, output, report = [Path(p).resolve() for p in
                                  (body_blend, roof_json, out_blend, out_json)]
    if len({body, roof, output, report}) != 4:
        raise ValueError("Inputs and outputs must be distinct resolved paths")
    for path in (body, roof):
        if not path.is_file():
            raise FileNotFoundError(path)
    for path in (output, report):
        if path.exists() or path.is_symlink():
            raise FileExistsError(path)
        if not path.parent.is_dir():
            raise FileNotFoundError(path.parent)
    return body, roof, output, report


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
    paths = plan_paths(*(argv if argv is not None else
                         sys.argv[sys.argv.index("--") + 1:]))
    body, roof_path, output, report = paths
    roof_data = json.loads(roof_path.read_text(encoding="utf-8"))
    roof = roof_data["mesh"]
    if len(roof_data["face_roles"]) != len(roof["faces"]):
        raise ValueError("ROOF face_roles do not match its faces")
    if len(roof["materials"]) != len(roof["faces"]):
        raise ValueError("ROOF material indices do not match its faces")
    source_hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in (body, roof_path)}

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
    if roof["name"] in bpy.data.objects or "ROOF_PROVENANCE.json" in bpy.data.texts:
        raise ValueError("ROOF names collide with BODY data")

    mesh = bpy.data.meshes.new(roof["name"])
    mesh.from_pydata(roof["vertices"], [], roof["faces"])
    mesh.update()
    if mesh.validate(verbose=False, clean_customdata=False):
        raise ValueError("ROOF geometry required repair")
    for polygon, material_index in zip(mesh.polygons, roof["materials"]):
        polygon.material_index = material_index
    roof_obj = bpy.data.objects.new(roof["name"], mesh)
    bpy.context.scene.collection.objects.link(roof_obj)
    roof_text = json.dumps(roof_data, ensure_ascii=False)
    roof_block = bpy.data.texts.new("ROOF_PROVENANCE.json")
    roof_block.write(roof_text)
    roof_block.use_fake_user = True
    texts["ROOF_PROVENANCE.json"] = roof_text
    expected = {obj.name: mesh_snapshot(obj) for obj in [*body_objects, roof_obj]}
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
    if json.loads(bpy.data.texts["ROOF_PROVENANCE.json"].as_string()) != roof_data:
        raise ValueError("Saved ROOF provenance changed")
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != source_hashes[str(path)]
           for path in (body, roof_path)):
        raise ValueError("An input changed during assembly")
    rows = [{"name": name, "vertices": len(item["vertices"]), "faces": len(item["faces"]),
             "quads": sum(len(face) == 4 for face in item["faces"]),
             "z_range": [min(v[2] for v in item["vertices"]),
                         max(v[2] for v in item["vertices"])]}
            for name, item in actual.items()]
    report.write_text(json.dumps({
        "blend": str(output), "objects": rows, "source_sha256": source_hashes,
        "body_provenance_preserved": True, "roof_provenance_preserved": True,
        "geometry_uv_materials_transforms_properties_preserved": True,
        "inputs_unchanged": True, "blender": bpy.app.version_string,
        "delivery_passed": False,
    }, indent=1), encoding="utf-8")
    print("ASSEMBLED", rows)


if __name__ == "__main__":
    main()

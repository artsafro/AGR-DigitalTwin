"""Dump a source model's triangles and LEVEL_<name> helpers for the spec extractor.

    blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
        --python tools/source/measure_spec_blender.py -- <source.fbx|.blend> <dump.json>

Blender only reads: world-space vertices and triangles per mesh object, and the world
location of every object named LEVEL_<name>, plus the material id of every triangle (slot index + 1)
and, when the mesh has UVs, the UDIM tile of every triangle.
All geometry logic (sections, contours, parts)
runs outside Blender in dt_ai.spec (`uv run dt spec extract`). The source is never saved.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
if len(args) != 2:
    raise SystemExit("usage: ... -- <source.fbx|.blend> <dump.json>")
source, out = Path(args[0]).resolve(), Path(args[1]).resolve()
if out.exists():
    raise SystemExit(f"refusing to overwrite {out}; use a new versioned path")

if source.suffix.lower() == ".blend":
    bpy.ops.wm.open_mainfile(filepath=str(source))
elif source.suffix.lower() == ".fbx":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(source))
else:
    raise SystemExit(f"unsupported source {source.suffix}")

meshes, helpers = [], []
depsgraph = bpy.context.evaluated_depsgraph_get()
for obj in bpy.context.scene.objects:
    if obj.name.startswith("LEVEL_"):
        helpers.append({"name": obj.name, "location": list(obj.matrix_world.translation)})
        continue
    if obj.type != "MESH":
        continue
    mesh = obj.evaluated_get(depsgraph).to_mesh()
    mesh.calc_loop_triangles()
    uv = mesh.uv_layers.active.data if mesh.uv_layers.active else None

    def udim(t, uv=uv):
        u = sum(uv[i].uv[0] for i in t.loops) / 3
        v = sum(uv[i].uv[1] for i in t.loops) / 3
        return 1001 + int(math.floor(u)) + 10 * int(math.floor(v))
    mw = obj.matrix_world
    meshes.append({"name": obj.name,
                   "vertices": [list(mw @ v.co) for v in mesh.vertices],
                   "triangles": [list(t.vertices) for t in mesh.loop_triangles],
                   # material id = slot index + 1 = 3ds Max material id (docs/domain/materials.md)
                   "material_ids": [t.material_index + 1 for t in mesh.loop_triangles],
                   # vertex count of every source polygon: n-gon check of the benchmark (twinqa.geometry)
                   "polygon_sizes": [len(p.vertices) for p in mesh.polygons],
                   # UDIM tile of every triangle (its UV centre, active layer): a source whose finishes are
                   # tiles, not slots, gets its material ids from an object table (K01, user 2026-10-11)
                   **({"udim_tiles": [udim(t) for t in mesh.loop_triangles]} if uv else {})})
    obj.evaluated_get(depsgraph).to_mesh_clear()

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({
    "source": source.name,
    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "blender": bpy.app.version_string,
    "units": "m",
    "meshes": meshes,
    "helpers": helpers,
}), encoding="utf-8")
print(f"MEASURE-SPEC {len(meshes)} meshes, {len(helpers)} level helpers -> {out}")

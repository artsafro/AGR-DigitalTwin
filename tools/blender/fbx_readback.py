# Ported from AGR max/AGR_Workbench/check_fbx.py (sha256 e8c032b17279) and
# tools/profile_snapshot_common.py (sha256 cbb176e2b241) object/image facts on 2026-10-06; changes: one standalone
# script, no RunRecord/config files, adds triangles, polygon degrees, UV channels, UDIM tiles,
# mirrored UV triangles, transforms and embedded image facts for the V002-V013 scene stages.
"""Structural FBX readback in an isolated factory Blender process.

    blender --background --factory-startup --python-exit-code 1 \
        --python tools/blender/fbx_readback.py -- <model.fbx> <report.json>

Readback facts only; it does not judge the delivery (twinqa.scene does) and never writes
the source. Exit 2 when the file imports but holds no non-empty mesh.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
if len(args) != 2:
    raise SystemExit("usage: ... -- <model.fbx> <report.json>")
source, out = Path(args[0]).resolve(), Path(args[1]).resolve()


def udim(u, v):
    return 1001 + int(math.floor(u)) + 10 * int(math.floor(v)) if 0 <= u < 10 and v >= 0 else None


def mesh_facts(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    world = [obj.matrix_world @ v.co for v in mesh.vertices]
    if any(not math.isfinite(c) for p in world for c in p):
        raise ValueError("non-finite vertex coordinates: " + obj.name)
    degrees = {}
    for poly in mesh.polygons:
        degrees[len(poly.vertices)] = degrees.get(len(poly.vertices), 0) + 1
    facts = {
        "name": obj.name,
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "triangles": len(mesh.loop_triangles),
        "polygon_degrees": {str(k): v for k, v in sorted(degrees.items())},
        "bounds_m": [[min(p[i] for p in world) for i in range(3)],
                     [max(p[i] for p in world) for i in range(3)]] if world else None,
        "location": list(obj.location),
        "rotation_euler_deg": [math.degrees(a) for a in obj.rotation_euler],
        "scale": list(obj.scale),
        "parent": obj.parent.name if obj.parent else None,
        "uv_channels": len(mesh.uv_layers),
        "materials": [s.material.name if s.material else None for s in obj.material_slots],
        "udim_tiles": [],
        "mirrored_uv_triangles": 0,
    }
    uv = mesh.uv_layers.active
    if uv:
        tiles, mirrored = set(), 0
        for tri in mesh.loop_triangles:
            a, b, c = (uv.data[i].uv for i in tri.loops)
            area = (b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)
            mirrored += area < 0  # negative winding in UV = mirrored island (reg p.31)
            tiles.add(udim((a.x + b.x + c.x) / 3, (a.y + b.y + c.y) / 3))
        facts["udim_tiles"] = sorted(t for t in tiles if t is not None)
        facts["uv_outside_udim_grid"] = None in tiles
        facts["mirrored_uv_triangles"] = mirrored
    return facts


def image_facts():
    images = []
    for image in bpy.data.images:
        if image.type != "IMAGE":
            continue
        packed = bytes(image.packed_file.data) if image.packed_file else None
        images.append({"name": image.name, "size": list(image.size), "packed": packed is not None,
                       "packed_bytes": len(packed) if packed else 0,
                       "packed_sha256": hashlib.sha256(packed).hexdigest() if packed else None,
                       "filepath": image.filepath})
    return images


report = {"source": str(source), "readback_ok": False, "blender": bpy.app.version_string,
          "scope": "structural readback only; not a delivery verdict", "meshes": [], "other_objects": []}
try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(source))
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            report["meshes"].append(mesh_facts(obj))
        else:
            report["other_objects"].append({"name": obj.name, "type": obj.type})
    report["images"] = image_facts()
    report["readback_ok"] = bool(report["meshes"]) and all(m["polygons"] > 0 for m in report["meshes"])
    if not report["readback_ok"]:
        report["error"] = "no non-empty meshes"
except Exception as exc:  # report, never hide
    report["error"] = f"{type(exc).__name__}: {exc}"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("TWINQA_READBACK", report["readback_ok"])
if not report["readback_ok"]:
    sys.exit(2)

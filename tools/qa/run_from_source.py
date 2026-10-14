"""Build a model by source modules and check it: source dump -> dt_ai.geometry.from_source (model dump, spec by
modules) -> tools/export/export_mesh_blender.py -> FBX readback -> the same checkers as the spec path.

    uv run python tools/qa/run_from_source.py --dump <source dump> --modules jobs/<OBJ>/modules/modules.json
        --object jobs/<OBJ>/object.json --tolerances jobs/<OBJ>/tolerances.json --output <new run folder>

The etalon of the checks is the source without the modules built as `skip` (interior, texture, attachments).
Writes model-dump.json, spec.json, modules-report.json, model.blend / model.fbx, model-readback.json,
check.json and summary.json into the run folder (it must not exist)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from dt_ai.geometry import from_source as fs  # noqa: E402
from dt_ai.spec.model import Spec  # noqa: E402
from run_benchmark import EXPORT, MEASURE, blender_run, produced, write  # noqa: E402
from twinqa.geometry import checks  # noqa: E402
from twinqa.geometry.mesh import from_dump  # noqa: E402
from twinqa.io import read_json  # noqa: E402
from twinqa.scene import find_blender  # noqa: E402


def etalon_of(dump: dict, modules: dict) -> dict:
    """The source without the module parts built as skip."""
    drop = {}
    for mod in modules["modules"]:
        if mod.get("build_as") == "skip":
            for p in mod["parts"]:
                drop.setdefault(p["object"], set()).add(p["slot"])
    meshes = []
    for m in dump["meshes"]:
        if m["name"] in drop:
            if None in drop[m["name"]]:
                continue
            t = np.asarray(m["triangles"]).reshape(-1, 3)
            mid = np.asarray(m["material_ids"])
            keep = ~np.isin(mid, list(drop[m["name"]]))
            m = {**m, "triangles": t[keep].tolist(), "material_ids": mid[keep].tolist(), "polygon_sizes": [3] * int(keep.sum())}
            m.pop("udim_tiles", None)
        meshes.append(m)
    return {**dump, "meshes": meshes}


def run(dump_p: Path, modules_p: Path, obj_p: Path, tol_p: Path, out: Path, blender: str) -> dict:
    dump, modules = read_json(dump_p.read_bytes()), read_json(modules_p.read_bytes())
    obj, tol = read_json(obj_p.read_bytes()), read_json(tol_p.read_bytes())
    inputs = fs.Inputs(levels=[(lv["name"], float(lv["elev_m"])) for lv in obj["levels"]],
                       opening_depth_m=obj.get("opening_depth_default_m", 0.4), weld_m=obj.get("weld_m", 0.003))
    model, spec_doc, report = fs.build_from_modules(dump, modules, obj["id"], inputs)
    spec = Spec.model_validate(spec_doc)
    out.mkdir(parents=True)
    write(out / "model-dump.json", model)
    write(out / "spec.json", spec_doc)
    write(out / "modules-report.json", report)
    blender_run(blender, EXPORT, out / "model-dump.json", out / "model.blend", out / "model.fbx", timeout=3600)
    produced(out / "model.blend", out / "model.fbx")
    blender_run(blender, MEASURE, out / "model.fbx", out / "model-readback.json", timeout=3600)
    produced(out / "model-readback.json")
    etalon = from_dump(etalon_of(dump, modules))
    etalon.levels = {lv.name: lv.elev_m for lv in spec.levels}
    readback = from_dump(read_json((out / "model-readback.json").read_bytes()))
    if not readback.levels:
        readback.levels = etalon.levels
    check = checks.run(readback, etalon, spec, tol["geometry"], source_class=obj.get("source_class"))
    write(out / "check.json", check)
    summary = {"triangles": report["triangles"], "passed": check["passed"], "failed": check["failed"],
               "not_measured": check["not_measured"]}
    write(out / "summary.json", summary)
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for a in ("--dump", "--modules", "--object", "--tolerances", "--output"):
        ap.add_argument(a, type=Path, required=True)
    ap.add_argument("--blender", help="default: TWINQA_BLENDER, PATH, newest Program Files install")
    args = ap.parse_args(argv)
    blender = args.blender or find_blender()
    if not blender:
        print("Error: Blender not found (set TWINQA_BLENDER)", file=sys.stderr)
        return 2
    if args.output.exists():
        print(f"Error: {args.output} exists; write a new versioned run", file=sys.stderr)
        return 2
    summary = run(args.dump, args.modules, args.object, args.tolerances, args.output, blender)
    print(json.dumps(summary))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

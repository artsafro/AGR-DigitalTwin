"""Run one benchmark end to end: etalon FBX -> spec -> engine model -> FBX -> checker report.

    uv run python tools/qa/run_benchmark.py --etalon <etalon.fbx|.blend> --object <object.json> \
        --tolerances benchmark/<bench-id>/tolerances.json --output <new run folder> [--blender <exe>]

Steps (docs/HARNESS_PLAN.md §5, §8, §9), every output in the new run folder:
1. etalon-dump.json   tools/source/measure_spec_blender.py on the etalon
2. spec.json          dt_ai.spec.extract_spec (+ spec.report.json; questions stop nothing, they are reported)
3. model-dump.json    dt_ai.geometry.from_spec.build with the `build` block of object.json
4. model.blend/.fbx   tools/export/export_mesh_blender.py
5. model-readback.json  measure_spec_blender.py on model.fbx: the checks read the exported file, not memory
   etalon-self.json   right after step 2: the checks of the etalon against itself (a failure here is the
                      etalon's or a threshold's); written even when the engine cannot build the spec
6. report.json        the checks of the model readback against the etalon
summary.json holds every step's status. Pattern: none — benchmark tooling, not a building node
(REVIEW_CHECKLIST Q1: new-case). Exit 0 both reports pass; 1 a check fails (a failure is a definite
result, so it wins over a check left unmeasured elsewhere); 2 a step stops, no check fails but one is
not measured, or the input is wrong. The run folder must not exist (never overwritten).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dt_ai.geometry.from_spec import BuildError, BuildInputs, build  # noqa: E402
from dt_ai.spec import SpecError, extract_spec  # noqa: E402
from dt_ai.spec.model import Spec  # noqa: E402
from twinqa.geometry import checks  # noqa: E402
from twinqa.geometry.mesh import from_dump  # noqa: E402
from twinqa.io import read_json  # noqa: E402
from twinqa.scene import find_blender  # noqa: E402

MEASURE = ROOT / "tools/source/measure_spec_blender.py"
EXPORT = ROOT / "tools/export/export_mesh_blender.py"


def blender_run(blender, script, *args, timeout=900):
    cmd = [blender, "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1",
           "--python", str(script), "--", *map(str, args)]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if done.returncode != 0:
        raise RuntimeError(f"{script.name} exit {done.returncode}: {(done.stderr or done.stdout)[-800:]}")


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def produced(*paths):
    """A step is done only when every file it promised exists and is not empty."""
    missing = [p.name for p in paths if not p.is_file() or p.stat().st_size == 0]
    if missing:
        raise RuntimeError(f"step reported success but left no {', '.join(missing)}")


def run(etalon, obj_path, tol_path, out, blender):
    summary = {"etalon": str(etalon), "object": str(obj_path), "tolerances": str(tol_path), "steps": {}}
    steps = summary["steps"]
    try:
        obj, tolerances = read_json(obj_path.read_bytes()), read_json(tol_path.read_bytes())
        for name, value in (("object.json", obj), ("tolerances.json", tolerances)):
            if not isinstance(value, dict):
                raise ValueError(f"{name} must be a JSON object, got {type(value).__name__}")
        geometry = tolerances["geometry"]
        if not isinstance(geometry, dict):
            raise ValueError("tolerances.json geometry must be a JSON object")
        blender_run(blender, MEASURE, etalon, out / "etalon-dump.json")
        produced(out / "etalon-dump.json")
        etalon_dump = read_json((out / "etalon-dump.json").read_bytes())
        steps["etalon_dump"] = "done"
        spec, report = extract_spec(etalon_dump, obj, tolerances.get("profile", "npm_min"), tolerances.get("spec_extract"))
        write(out / "spec.json", spec.model_dump(exclude_none=True))
        write(out / "spec.report.json", report)
        steps["spec"] = {"status": "done", "questions": len(report["questions"])}
        etalon_soup = from_dump(etalon_dump, spec.frame.to_object)
        self_check = checks.run(etalon_soup, etalon_soup, spec, geometry)   # before the engine: an etalon is
        write(out / "etalon-self.json", self_check)                        # checked even when it cannot be built
        steps["etalon_self"] = {k: self_check[k] for k in ("passed", "failed", "not_measured")}
        model_dump = build(Spec.model_validate(spec.model_dump()), BuildInputs.from_object(obj))
        write(out / "model-dump.json", model_dump)
        steps["model"] = "done"
        blender_run(blender, EXPORT, out / "model-dump.json", out / "model.blend", out / "model.fbx")
        produced(out / "model.blend", out / "model.fbx")
        steps["export"] = "done"
        blender_run(blender, MEASURE, out / "model.fbx", out / "model-readback.json")
        produced(out / "model-readback.json")
        readback = read_json((out / "model-readback.json").read_bytes())
        steps["readback"] = "done"
        model_check = checks.run(from_dump(readback), etalon_soup, spec, geometry)
    except (SpecError, BuildError, RuntimeError, subprocess.TimeoutExpired, OSError, ValueError, KeyError,
            TypeError) as exc:
        summary["stopped"] = f"{type(exc).__name__}: {exc}"
        return summary
    write(out / "report.json", model_check)
    steps["model_check"] = {k: model_check[k] for k in ("passed", "failed", "not_measured")}
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--etalon", type=Path, required=True)
    ap.add_argument("--object", type=Path, required=True)
    ap.add_argument("--tolerances", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--blender", help="default: TWINQA_BLENDER, PATH, newest Program Files install")
    args = ap.parse_args(argv)
    blender = args.blender or find_blender()
    if args.output.exists():
        print(f"Error: {args.output} exists; use a new versioned run folder", file=sys.stderr)
        return 2
    if not blender or not args.etalon.is_file():
        print("Error: " + ("Blender not found (set TWINQA_BLENDER)" if not blender else f"{args.etalon} does not exist"),
              file=sys.stderr)
        return 2
    args.output.mkdir(parents=True)
    summary = run(args.etalon.resolve(), args.object, args.tolerances, args.output.resolve(), blender)
    write(args.output / "summary.json", summary)
    print(json.dumps(summary["steps"], ensure_ascii=False))
    if "stopped" in summary:
        print(f"Stopped: {summary['stopped']}", file=sys.stderr)
        return 2
    results = [summary["steps"]["etalon_self"], summary["steps"]["model_check"]]
    if all(r["passed"] for r in results):
        return 0
    return 1 if any(r["failed"] for r in results) else 2


if __name__ == "__main__":
    sys.exit(main())

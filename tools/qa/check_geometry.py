"""Geometry of a model against a benchmark etalon (docs/HARNESS_PLAN.md §5).

    uv run python tools/qa/check_geometry.py <model-dump.json> <etalon-dump.json> --spec <spec.json> \
        --tolerances benchmark/<bench-id>/tolerances.json --output <report.json>

Dumps come from tools/source/measure_spec_blender.py. The etalon dump is moved into the object
system by the spec's frame; the model dump is taken as already in it unless --model-frame gives
a JSON file with a 4x4 `to_object`. Exit 0 all checks pass, 1 a check fails, 2 a check is not
measured or the input is wrong. The report is never overwritten.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from dt_ai.spec.model import Spec  # noqa: E402
from twinqa.geometry import checks  # noqa: E402
from twinqa.geometry.mesh import from_dump  # noqa: E402
from twinqa.io import read_json  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("model", type=Path)
    ap.add_argument("etalon", type=Path)
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--tolerances", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--model-frame", type=Path)
    args = ap.parse_args(argv)
    if args.output.exists():
        print(f"Error: {args.output} exists; write a new versioned report", file=sys.stderr)
        return 2
    try:
        spec = Spec.model_validate(read_json(args.spec.read_bytes()))
        tol = read_json(args.tolerances.read_bytes())["geometry"]
        frame = read_json(args.model_frame.read_bytes())["to_object"] if args.model_frame else None
        model = from_dump(read_json(args.model.read_bytes()), frame)
        etalon = from_dump(read_json(args.etalon.read_bytes()), spec.frame.to_object)
    except (OSError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    report = checks.run(model, etalon, spec, tol)
    report = {**report, "model": str(args.model), "etalon": str(args.etalon), "spec": str(args.spec),
              "tolerances": str(args.tolerances)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("passed", "failed", "not_measured")}))
    return 0 if report["passed"] else (1 if report["failed"] else 2)


if __name__ == "__main__":
    sys.exit(main())

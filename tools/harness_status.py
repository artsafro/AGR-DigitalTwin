"""Inspect existing RunRecord evidence without commands, mutations or DCC access."""
import argparse
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dt_ai.core.io import json_bytes
from dt_ai.core.run_inspection import inspect_run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--required-check", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        result = inspect_run(args.run, args.manifest, args.report, args.required_check)
        print(json_bytes(result).decode())
        return 1 if result["errors_total"] else 0
    except (ValueError, OSError, RuntimeError) as error:
        print(json_bytes({"error": str(error), "delivery_passed": False}).decode())
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

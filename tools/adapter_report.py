"""Validate an existing report; print bounded summary, never the mesh/log payload."""
import argparse
import json
import sys
from pathlib import Path
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dt_ai.core.adapter_report import AdapterReport
from dt_ai.core.io import read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        report = AdapterReport.model_validate(read_json(args.report.read_bytes()))
    except ValidationError as exc:
        print(json.dumps({"error": "invalid_report", "errors_total": exc.error_count()}),
              file=sys.stderr)
        return 1
    except (ValueError, OSError):
        print(json.dumps({"error": "unreadable_or_invalid_json"}), file=sys.stderr)
        return 1
    print(json.dumps({**report.summary(), "full_report": str(args.report.resolve())},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


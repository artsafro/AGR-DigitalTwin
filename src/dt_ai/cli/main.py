import argparse
import os
import sys
from pathlib import Path

from dt_ai.core.build import build
from dt_ai.core.io import json_bytes, read_json, repo_root, write_json
from dt_ai.core.models import BuildJob, MaterialRegistry, SCHEMAS
from dt_ai.core.profiles import load_profiles
from dt_ai.drawing.index import index_pdf
from dt_ai.materials.registry import merge_proposals
from dt_ai.validate.bundle import validate


def parser():
    p = argparse.ArgumentParser(prog="dt", description="Digital Twin AI - synthetic NPM/VPM vertical slice")
    sub = p.add_subparsers(dest="command", required=True)
    profiles = sub.add_parser("profiles", help="Verify original profiles, source hashes and traceability")
    profiles.add_argument("action", choices=["check"])
    schemas = sub.add_parser("schemas", help="Export or compare versioned JSON Schema contracts")
    schemas.add_argument("--check", action="store_true")
    inspect = sub.add_parser("inspect", help="Read a job contract without modifying it")
    inspect.add_argument("--manifest", type=Path, required=True)
    index = sub.add_parser("index-pdf", help="Index all pages and embedded images; no OCR inference")
    index.add_argument("--source", type=Path, required=True)
    index.add_argument("--output", type=Path, required=True)
    reg = sub.add_parser("registry", help="Merge proposals while preserving approved decisions")
    reg.add_argument("action", choices=["merge"])
    reg.add_argument("--current", type=Path, required=True)
    reg.add_argument("--proposal", type=Path, required=True)
    reg.add_argument("--output", type=Path, required=True)
    for name in ("build", "validate"):
        item = sub.add_parser(name, help="Build/check a labelled development bundle; never certify delivery")
        item.add_argument("--job" if name == "build" else "--archive", type=Path, required=True)
        item.add_argument("--output", type=Path)
        item.add_argument("--blender", default=os.environ.get("DT_BLENDER"), help="Path to Blender; runs isolated background processes")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        root = repo_root()
        if args.command == "profiles":
            data = load_profiles(root)
            print(f"OK: {len(data)} profiles, source hash, traceability pages")
        elif args.command == "schemas":
            for name, model in SCHEMAS.items():
                path = root / "schemas" / (name + ".schema.json")
                data = json_bytes(model.model_json_schema())
                if args.check:
                    if not path.exists() or path.read_bytes() != data:
                        raise ValueError(f"Schema drift: {path.name}")
                else:
                    path.write_bytes(data)
            print(f"OK: {len(SCHEMAS)} schemas")
        elif args.command == "inspect":
            job = BuildJob.model_validate(read_json(args.manifest.read_bytes()))
            print(json_bytes({"project_id": job.project.project_id, "synthetic": job.project.synthetic,
                              "materials": len(job.registry.materials), "surfaces": len(job.master.surfaces)}).decode())
        elif args.command == "index-pdf":
            result = index_pdf(args.source, args.output)
            print(f"Indexed {len(result['pages'])} pages: {args.output / 'index.json'}")
        elif args.command == "registry":
            current = MaterialRegistry.model_validate(read_json(args.current.read_bytes()))
            proposal = MaterialRegistry.model_validate(read_json(args.proposal.read_bytes()))
            merged, conflicts = merge_proposals(current, proposal)
            write_json(args.output, merged.model_dump())
            write_json(args.output.with_suffix(".conflicts.json"), conflicts)
            print(f"Merged; {len(conflicts)} conflicts preserved separately")
        else:
            output = args.output or (args.job.parent / "outputs" if args.command == "build" else args.archive.parent / "validation")
            archive = build(root, args.job, output, args.blender) if args.command == "build" else args.archive
            report = validate(root, archive, output, args.blender)
            print(f"Report: {output / 'report.json'}; development_checks_passed={report.development_checks_passed}; delivery_passed=False")
            if any(c.status == "fail" for c in report.checks):
                return 1
            if args.command == "validate" and not report.development_checks_passed:
                return 2
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

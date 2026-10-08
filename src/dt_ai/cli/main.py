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
from dt_ai.spec import extract_spec
from dt_ai.spec.compare import compare_specs, markdown as spec_compare_markdown
from dt_ai.spec import revit_twin
from dt_ai.spec.mesh import questions_markdown
from dt_ai.spec.questions_file import merge as merge_questions
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
    spec = sub.add_parser("spec", help="Extract spec.json from a mesh dump; merge its questions; compare two specs")
    spec.add_argument("action", choices=["extract", "merge-questions", "compare"])
    spec.add_argument("--dump", type=Path, help="extract: dump of tools/source/measure_spec_blender.py")
    spec.add_argument("--object", type=Path, help="extract: object.json with id and frame")
    spec.add_argument("--output", type=Path, help="extract: new spec.json; report and questions beside it")
    spec.add_argument("--profile", choices=["npm_min", "mid"], default="npm_min")
    spec.add_argument("--report", type=Path, help="merge-questions: <spec>.report.json of one version")
    spec.add_argument("--version", help="merge-questions: the spec version, e.g. v002")
    spec.add_argument("--into", type=Path, help="merge-questions: the object's questions.md (created if missing)")
    spec.add_argument("--a", type=Path, help="compare: first spec.json (its <spec>.report.json beside it)")
    spec.add_argument("--b", type=Path, help="compare: second spec.json (its <spec>.report.json beside it)")
    spec.add_argument("--tolerances", type=Path, help="compare: benchmark tolerances.json")
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
        elif args.command == "spec" and args.action == "merge-questions":
            if not (args.report and args.version and args.into):
                raise ValueError("merge-questions needs --report, --version and --into")
            report = read_json(args.report.read_bytes())
            spec_doc = read_json(args.report.with_name(args.report.name.replace(".report.json", ".json")).read_bytes())
            old = args.into.read_text(encoding="utf-8") if args.into.exists() else None
            text = merge_questions(old, spec_doc["id"], args.version, report.get("questions"))
            args.into.parent.mkdir(parents=True, exist_ok=True)
            tmp = args.into.with_suffix(".md.tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(args.into)
            print(f"Questions: {args.into}; {len(report['questions'])} from {args.version}")
        elif args.command == "spec" and args.action == "compare":
            if not (args.a and args.b and args.tolerances and args.output):
                raise ValueError("compare needs --a, --b, --tolerances and --output")
            md = args.output.with_suffix(".md")
            for path in (args.output, md):
                if path.exists():
                    raise ValueError(f"{path} exists; write a new versioned comparison")
            docs = [read_json(x.read_bytes()) for x in (args.a, args.b)]
            reports = [read_json(x.with_name(x.name.replace(".json", ".report.json")).read_bytes()) for x in (args.a, args.b)]
            result = compare_specs(*docs, *reports, read_json(args.tolerances.read_bytes()),
                                   names=tuple(d["frame"]["source"] for d in docs))
            result["inputs"] = {"a": str(args.a), "b": str(args.b), "tolerances": str(args.tolerances)}
            write_json(args.output, result)
            md.write_text(spec_compare_markdown(result), encoding="utf-8")
            print(f"Compare: {args.output}; verdict {result['verdict']}; {len(result['failing'])} criteria outside: "
                  f"{', '.join(result['failing']) or 'none'}")
        elif args.command == "spec":
            if not (args.dump and args.object and args.output):
                raise ValueError("extract needs --dump, --object and --output")
            outputs = [args.output.with_suffix(s) for s in (".json", ".report.json", ".questions.md")]
            for path in [args.output] + outputs[1:]:
                if path.exists():
                    raise ValueError(f"{path} exists; write a new versioned spec")
            dump = read_json(args.dump.read_bytes())
            if dump.get("kind") == "revit-twin":         # band folders beside the index (#29)
                dump = revit_twin.load(args.dump)
            result, report = extract_spec(dump, read_json(args.object.read_bytes()), args.profile)
            write_json(args.output, result.model_dump(exclude_none=True))
            write_json(outputs[1], report)
            if report["questions"]:
                outputs[2].write_text(questions_markdown(result.id, report["questions"]), encoding="utf-8")
            print(f"Spec: {args.output}; {len(result.expanded_floors())} floors ({len(result.floors)} written), "
                  f"{report['parts']} parts "
                  f"({report['attachment_parts_ignored']} attachments ignored), {len(report['questions'])} questions")
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

"""Check an intake folder (docs/HARNESS_PLAN.md §15): `dt intake check --dir jobs/<JOB>/intake`.

The four files and their rules (user decisions 2026-10-11):
- sources.json (dt_ai.intake.model.SourcesFile): every file, what was read, units, frame, version, what did
  not open and why; one primary source - the best-ranked with geometry or dimensions.
- picture.md: a "## Facts" table | Fact | Value | Source | Confidence | and a "## Contradictions" table
  | Fact | Source A | Value A | Source B | Value B | Status |; every source a path of sources.json
  (optionally "#locator"); contradictions are never resolved by the agent (Status "open", or the user's
  "answered: ...").
- questions.md: the questions-file format (dt_ai.spec.questions_file).
- spec-draft.json (dt_ai.intake.model.SpecDraft): null without a source, a confidence per block.

Confidence: `measured` needs a source read for geometry; `read_from_drawing` one read for dimensions;
anything taken from images only is at most `estimated`; while an anchor is needed and not confirmed,
nothing is measured or read from a drawing and no spec is built. The draft is buildable only when every
required block is filled and the assembled spec validates — the engine runs on nothing less.
"""
import json
import re
from pathlib import Path

from pydantic import ValidationError

from dt_ai.intake.model import BLOCKS, REQUIRED, SourcesFile, SpecDraft
from dt_ai.spec import questions_file
from dt_ai.spec.model import Spec

CONFIDENCE = ("measured", "read_from_drawing", "estimated", "unknown")
_SPLIT = re.compile(r"(?<!\\)\|")


def _table(text, heading):
    """Rows (dicts) of the first Markdown table under '## <heading>'."""
    part = re.split(r"^##\s+" + re.escape(heading) + r"\s*$", text, flags=re.M)
    if len(part) < 2:
        return None
    rows, header = [], None
    for line in part[1].splitlines():
        body = line.strip()
        if body.startswith("## "):
            break
        if not body.startswith("|"):
            if header is not None and rows:
                break
            continue
        cells = [c.strip() for c in _SPLIT.split(body.strip("|"))]
        if header is None:
            header = cells
        elif all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        else:
            rows.append(dict(zip(header, cells)))
    return rows if header is not None else None


def _paths(cell):
    return [p.strip().split("#")[0].strip() for p in cell.split(",") if p.strip() and p.strip() != "—"]


def _confidence_errors(where, confidence, sources, by_path, anchor_open):
    errors = []
    reads = set()
    for p in sources:
        if p not in by_path:
            errors.append(f"{where}: source {p!r} is not in sources.json")
        else:
            reads |= set(by_path[p].reads)
    if confidence not in CONFIDENCE:
        errors.append(f"{where}: confidence {confidence!r} is none of {CONFIDENCE}")
    elif confidence == "measured" and "geometry" not in reads:
        errors.append(f"{where}: measured needs a source read for geometry")
    elif confidence == "read_from_drawing" and not {"dimensions", "geometry"} & reads:
        errors.append(f"{where}: read_from_drawing needs a source read for dimensions")
    if confidence in ("measured", "read_from_drawing") and anchor_open:
        errors.append(f"{where}: {confidence} while the scale anchor is not confirmed (§15)")
    return errors


def check(folder):
    """Report of an intake folder: errors (rule breaches), and whether spec-draft.json is buildable."""
    folder = Path(folder)
    errors, report = [], {"folder": str(folder)}

    def load(name, model):
        path = folder / name
        if not path.exists():
            errors.append(f"{name} missing")
            return None
        try:
            return model.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValidationError, ValueError) as exc:
            errors.append(f"{name}: {str(exc).splitlines()[0] if isinstance(exc, ValueError) and not isinstance(exc, ValidationError) else exc}")
            return None

    sources = load("sources.json", SourcesFile)
    draft = load("spec-draft.json", SpecDraft)
    by_path = {f.path: f for f in sources.files} if sources else {}
    shaped = [f for f in by_path.values() if f.opened and {"geometry", "dimensions"} & set(f.reads)]
    if draft is not None and sources is not None and not shaped and not draft.anchor.needed:
        errors.append("spec-draft.json: only images / sources without dimensions, yet no scale anchor needed (§15)")
    anchor_open = bool(draft and draft.anchor.needed and not draft.anchor.confirmed)

    picture = folder / "picture.md"
    if not picture.exists():
        errors.append("picture.md missing")
    else:
        text = picture.read_text(encoding="utf-8")
        facts, contra = _table(text, "Facts"), _table(text, "Contradictions")
        if facts is None:
            errors.append("picture.md: no '## Facts' table")
        if contra is None:
            errors.append("picture.md: no '## Contradictions' table (write it empty when there is none)")
        for k, row in enumerate(facts or [], 1):
            where = f"picture.md fact {k} ({row.get('Fact', '?')})"
            if set(row) != {"Fact", "Value", "Source", "Confidence"}:
                errors.append(f"{where}: columns must be Fact | Value | Source | Confidence")
                continue
            if row["Confidence"] != "unknown" and not _paths(row["Source"]):
                errors.append(f"{where}: no source")
            errors += _confidence_errors(where, row["Confidence"], _paths(row["Source"]), by_path, anchor_open)
        for k, row in enumerate(contra or [], 1):
            where = f"picture.md contradiction {k} ({row.get('Fact', '?')})"
            status = row.get("Status", "")
            if not (status == "open" or status.startswith("answered")):
                errors.append(f"{where}: status is 'open' until the user answers; the agent does not resolve it")
            for p in _paths(row.get("Source A", "")) + _paths(row.get("Source B", "")):
                if p not in by_path:
                    errors.append(f"{where}: source {p!r} is not in sources.json")
        report["facts"], report["contradictions"] = len(facts or []), len(contra or [])

    questions = folder / "questions.md"
    if not questions.exists():
        errors.append("questions.md missing")
    else:
        try:
            _, rows = questions_file.parse(questions.read_text(encoding="utf-8"))
            report["questions"] = len(rows)
        except ValueError as exc:
            errors.append(f"questions.md: {exc}")

    buildable, why = False, []
    if draft is not None:
        for name, block in draft.blocks.items():
            errors += _confidence_errors(f"spec-draft.json {name}", block.confidence, [p.split("#")[0] for p in block.sources],
                                         by_path, anchor_open)
        why += [f"{b} is null" for b in REQUIRED if draft.blocks[b].value is None]
        if anchor_open:
            why.append("the scale anchor is not confirmed")
        if not why and not errors:
            data = {"id": draft.object, "profile": draft.profile or "npm_min",
                    **({"spec_version": draft.spec_version} if draft.spec_version else {}),
                    **{b: draft.blocks[b].value for b in BLOCKS if b in draft.blocks and draft.blocks[b].value is not None}}
            try:
                Spec.model_validate(data)
                buildable = True
            except ValidationError as exc:
                why.append(f"the assembled spec does not validate: {exc.errors()[0]['msg']}")
        report["confidence"] = {name: block.confidence for name, block in draft.blocks.items()}
    report.update({"errors": errors, "ok": not errors, "buildable": buildable, "not_buildable_because": why})
    return report

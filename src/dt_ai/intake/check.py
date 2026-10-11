"""Check an intake folder (docs/HARNESS_PLAN.md §15): `dt intake check --dir jobs/<JOB>/intake`.

The four files and their rules (user decisions 2026-10-11):
- sources.json (dt_ai.intake.model.SourcesFile): every file, what was read (only what its format can
  give), units, frame, version, what did not open and why; the primary source is the best-ranked one with
  geometry or dimensions.
- picture.md: a "## Facts" table | Fact | Value | Source | Confidence | and a "## Contradictions" table
  | Fact | Source A | Value A | Source B | Value B | Status |, exactly these columns, every row as long;
  every stated value names its sources (paths of sources.json, optionally "#locator"); contradictions are
  never resolved by the agent: Status "open", or "answered: Q<n>" once the user answered Q<n> in
  questions.md.
- questions.md: the questions-file format of this object (dt_ai.spec.questions_file); the anchor question
  is one of its rows.
- spec-draft.json (dt_ai.intake.model.SpecDraft): null without a source, a confidence per block.

Confidence: `measured` needs a source read for geometry; `read_from_drawing` one read for dimensions;
anything taken from images only is at most `estimated`; while an anchor is needed and not confirmed,
nothing is measured or read from a drawing and no spec is built. The draft is buildable only when every
required block is filled, no block is null, every filled block cites the primary source (when there is
one) and the assembled spec validates — the engine runs on nothing less. Blocks the draft leaves out take
the spec's documented defaults, listed in the report.
Pattern: none — intake code (REVIEW_CHECKLIST Q1: new-case, HARNESS_PLAN §15).
"""
import json
import re
from pathlib import Path

from pydantic import ValidationError

from dt_ai.intake.model import BLOCKS, REQUIRED, SourcesFile, SpecDraft
from dt_ai.spec import questions_file
from dt_ai.spec.model import Spec

CONFIDENCE = ("measured", "read_from_drawing", "estimated", "unknown")
FACTS = ("Fact", "Value", "Source", "Confidence")
CONTRADICTIONS = ("Fact", "Source A", "Value A", "Source B", "Value B", "Status")
_SPLIT = re.compile(r"(?<!\\)\|")


def _table(text, heading, columns, errors):
    """Rows (dicts) of the first Markdown table under '## <heading>'; its header must be exactly `columns`
    and every row as long (review 1 of PR #71). None when the heading is missing."""
    part = re.split(r"^##\s+" + re.escape(heading) + r"\s*$", text, flags=re.M)
    if len(part) < 2:
        return None
    rows, header, delimited, ended = [], None, False, False
    for line in part[1].splitlines():
        body = line.strip()
        if body.startswith("## "):
            break
        if not body.startswith("|"):
            ended = ended or header is not None
            continue
        if ended:                                       # one table per section (review 3 of PR #71)
            errors.append(f"picture.md {heading}: more than one table; one table per section")
            return []
        cells = [c.strip() for c in _SPLIT.split(body.strip("|"))]
        if header is None:
            header = cells
            if header != list(columns):
                errors.append(f"picture.md {heading}: columns must be {' | '.join(columns)}")
                return []
        elif not delimited:                             # the delimiter row right under the header
            if len(cells) != len(header) or not all(re.fullmatch(r":?-+:?", c) for c in cells):
                errors.append(f"picture.md {heading}: no delimiter row (|---|...) under the header")
                return []
            delimited = True
        elif len(cells) != len(header):
            errors.append(f"picture.md {heading}: a row with {len(cells)} cells under {len(header)} columns")
        else:
            rows.append(dict(zip(header, cells)))
    if header is None:
        errors.append(f"picture.md {heading}: no table (write its header even when it is empty)")
        return []
    if not delimited:
        errors.append(f"picture.md {heading}: no delimiter row (|---|...) under the header")
        return []
    return rows


def _paths(cell):
    return [p.strip().split("#")[0].strip() for p in cell.split(",") if p.strip() and p.strip() != "—"]


def _confidence_errors(where, confidence, sources, by_path, anchor_open, capable=None):
    """capable: the paths whose reads may carry the confidence (a draft block: the primary sources only, so a
    lower-ranked source never lends it its capability, review 2 of PR #71); None = every cited source."""
    errors = []
    reads = set()
    for p in sources:
        if p not in by_path:
            errors.append(f"{where}: source {p!r} is not in sources.json")
        elif not by_path[p].opened:
            errors.append(f"{where}: source {p!r} did not open; it is no evidence")
        elif capable is None or p in capable:
            reads |= set(by_path[p].reads)
    if confidence not in CONFIDENCE:
        errors.append(f"{where}: confidence {confidence!r} is none of {CONFIDENCE}")
    elif confidence == "measured" and "geometry" not in reads:
        errors.append(f"{where}: measured needs a source read for geometry")
    elif confidence == "read_from_drawing" and "dimensions" not in reads:
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
        except ValidationError as exc:
            errors.append(f"{name}: {exc}")
        except ValueError as exc:
            errors.append(f"{name}: {exc}")
        return None

    sources = load("sources.json", SourcesFile)
    draft = load("spec-draft.json", SpecDraft)
    by_path = {f.path: f for f in sources.files} if sources else {}
    shaped = [f for f in by_path.values() if f.opened and {"geometry", "dimensions"} & set(f.reads)]
    if draft is not None and sources is not None and not shaped and not draft.anchor.needed:
        errors.append("spec-draft.json: only images / sources without dimensions, yet no scale anchor needed (§15)")
    anchor_open = bool(draft and draft.anchor.needed and not draft.anchor.confirmed)

    answers = {}
    questions = folder / "questions.md"
    if not questions.exists():
        errors.append("questions.md missing")
    else:
        try:
            title, rows = questions_file.parse(questions.read_text(encoding="utf-8"))
            if title is None or (sources is not None and title != sources.object):
                errors.append("questions.md: no '# Questions — <object>' title of this object (questions-file format)")
            ids = [r["ID"] for r in rows]
            twice = sorted({i for i in ids if ids.count(i) > 1})
            if twice:                                    # one answer per question (review 2 of PR #71)
                errors.append(f"questions.md: question ids {twice} given more than once")
            answers = {r["ID"]: r["Answer"] for r in rows if r["ID"] not in twice}
            report["questions"] = len(rows)
        except ValueError as exc:
            errors.append(f"questions.md: {exc}")
    if draft is not None and draft.anchor.question and draft.anchor.question not in answers:
        errors.append(f"spec-draft.json: the anchor question {draft.anchor.question} is not in questions.md")
    elif draft is not None and draft.anchor.confirmed and not answers.get(draft.anchor.question, "").strip():
        errors.append(f"spec-draft.json: the anchor is confirmed only by the user's answer to "
                      f"{draft.anchor.question} in questions.md (review 2 of PR #71)")
    if draft is not None and sources is not None and draft.object != sources.object:
        errors.append(f"spec-draft.json: object {draft.object!r} is not the inventory's {sources.object!r}")

    picture = folder / "picture.md"
    if not picture.exists():
        errors.append("picture.md missing")
    else:
        text = picture.read_text(encoding="utf-8")
        for heading in ("Facts", "Contradictions"):       # one section each (review 2 of PR #71)
            if len(re.findall(r"^##\s+" + heading + r"\s*$", text, flags=re.M)) > 1:
                errors.append(f"picture.md: more than one '## {heading}' section")
        facts = _table(text, "Facts", FACTS, errors)
        contra = _table(text, "Contradictions", CONTRADICTIONS, errors)
        if facts is None:
            errors.append("picture.md: no '## Facts' table")
        if contra is None:
            errors.append("picture.md: no '## Contradictions' table (write it empty when there is none)")
        for k, row in enumerate(facts or [], 1):
            where = f"picture.md fact {k} ({row['Fact']})"
            stated = row["Value"] not in ("", "—")
            if row["Confidence"] == "unknown" and stated:
                errors.append(f"{where}: a stated value with confidence unknown")
            if (row["Confidence"] != "unknown" or stated) and not _paths(row["Source"]):
                errors.append(f"{where}: no source")
            errors += _confidence_errors(where, row["Confidence"], _paths(row["Source"]), by_path, anchor_open)
        for k, row in enumerate(contra or [], 1):
            where = f"picture.md contradiction {k} ({row['Fact']})"
            linked = re.fullmatch(r"answered:\s*(Q\d+)", row["Status"])
            if not (row["Status"] == "open" or (linked and answers.get(linked.group(1), "").strip())):
                errors.append(f"{where}: status is 'open' until the user answers its question ('answered: Q<n>' with "
                              "that answer in questions.md); the agent does not resolve it")
            if not _paths(row["Source A"]) or not _paths(row["Source B"]):
                errors.append(f"{where}: both sides name their sources")
            for p in _paths(row["Source A"]) + _paths(row["Source B"]):
                if p not in by_path:
                    errors.append(f"{where}: source {p!r} is not in sources.json")
                elif not by_path[p].opened:                     # review 3 of PR #71
                    errors.append(f"{where}: source {p!r} did not open; it is no evidence")
        report["facts"], report["contradictions"] = len(facts or []), len(contra or [])

    buildable, why = False, []
    if draft is not None:
        primary = {f.path for f in by_path.values() if f.role == "primary"}
        for name, block in draft.blocks.items():
            cited = [p.split("#")[0] for p in block.sources]
            errors += _confidence_errors(f"spec-draft.json {name}", block.confidence, cited, by_path, anchor_open,
                                         capable=primary or None)
            if block.value is not None and primary and not set(cited) & primary:
                errors.append(f"spec-draft.json {name}: cites no primary source {sorted(primary)}; lower-ranked "
                              "sources only check it or give materials (§15)")
        why += [f"{b} is null" for b in BLOCKS if b in draft.blocks and draft.blocks[b].value is None]
        if anchor_open:
            why.append("the scale anchor is not confirmed")
        if not why and not errors:
            data = {"id": draft.object, "profile": draft.profile or "npm_min",
                    **({"spec_version": draft.spec_version} if draft.spec_version else {}),
                    **{b: draft.blocks[b].value for b in BLOCKS if b in draft.blocks}}
            try:
                Spec.model_validate(data)
                buildable = True
                report["defaults_used"] = [b for b in BLOCKS if b not in draft.blocks]
            except ValidationError as exc:
                why.append(f"the assembled spec does not validate: {exc.errors()[0]['msg']}")
        report["confidence"] = {name: block.confidence for name, block in draft.blocks.items()}
    report.update({"errors": errors, "ok": not errors, "buildable": buildable, "not_buildable_because": why})
    return report

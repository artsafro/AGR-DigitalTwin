"""Intake folder checks (docs/HARNESS_PLAN.md §15, IN1). Synthetic folders built from the B01 fixture spec;
not a real object."""
import json
from pathlib import Path

import pytest

from dt_ai.cli.main import main
from dt_ai.intake.check import check
from dt_ai.spec import questions_file

ROOT = Path(__file__).resolve().parents[1]
B01 = json.loads((ROOT / "tests/fixtures/spec-b01-v0.3.json").read_text(encoding="utf-8"))

FBX = {"path": "etalon.fbx", "format": "fbx", "reads": ["geometry", "materials"], "units": "m", "frame": "Z up",
       "opened": True, "role": "primary"}
PDF = {"path": "album.pdf#p3", "format": "pdf", "reads": ["dimensions", "image"], "units": "mm", "opened": True,
       "role": "check"}
PNG = {"path": "view.png", "format": "image", "reads": ["image"], "opened": True, "role": "none"}
FACTS = """# Picture — bench-synth-box

## Facts

| Fact | Value | Source | Confidence |
|---|---|---|---|
| levels | 0 / 3.3 / 6.6 m | etalon.fbx | measured |
| parapet | 0.6 m | etalon.fbx, album.pdf#p3 | measured |
| facade colour | grey | view.png | estimated |

## Contradictions

| Fact | Source A | Value A | Source B | Value B | Status |
|---|---|---|---|---|---|
| parapet | etalon.fbx | 0.60 m | album.pdf#p3 | 0.65 m | open |
"""


def block(value, confidence="measured", sources=("etalon.fbx",)):
    return {"value": value, "confidence": confidence, "sources": list(sources) if value is not None else []}


def folder(tmp_path, files=(FBX, dict(PDF, path="album.pdf"), PNG), facts=FACTS, blocks=None, anchor=None):
    d = tmp_path / "intake"
    d.mkdir(parents=True)
    (d / "sources.json").write_text(json.dumps({"object": "bench-synth-box", "made": "2026-10-11", "files": list(files)}),
                                    encoding="utf-8")
    (d / "picture.md").write_text(facts, encoding="utf-8")
    (d / "questions.md").write_text(questions_file.merge("", "bench-synth-box", "v001", []), encoding="utf-8")
    draft = {"object": "bench-synth-box", "profile": "npm_min", "anchor": anchor or {"needed": False},
             "blocks": blocks or {k: block(B01[k]) for k in ("frame", "levels", "floors", "roof")}}
    (d / "spec-draft.json").write_text(json.dumps(draft), encoding="utf-8")
    return d


def test_a_complete_intake_is_buildable(tmp_path):
    r = check(folder(tmp_path))
    assert r["ok"] and r["buildable"], r["errors"] + r["not_buildable_because"]
    assert (r["facts"], r["contradictions"], r["questions"]) == (3, 1, 0)


def test_a_null_block_is_unknown_and_not_buildable(tmp_path):
    blocks = {k: block(B01[k]) for k in ("frame", "levels", "floors")} | {"roof": block(None, "unknown")}
    r = check(folder(tmp_path, blocks=blocks))
    assert r["ok"] and not r["buildable"] and r["not_buildable_because"] == ["roof is null"]


def test_null_with_a_confidence_is_an_error(tmp_path):
    blocks = {k: block(B01[k]) for k in ("frame", "levels", "floors")} | {"roof": {"value": None, "confidence": "estimated"}}
    r = check(folder(tmp_path, blocks=blocks))
    assert not r["ok"] and any("null exactly when" in e for e in r["errors"])


def test_images_only_need_an_anchor_and_measure_nothing(tmp_path):
    blocks = {k: block(B01[k], "estimated", ("view.png",)) for k in ("frame", "levels", "floors", "roof")}
    r = check(folder(tmp_path, files=(PNG,), facts=FACTS.split("## Facts")[0] + "## Facts\n\n| Fact | Value | Source | Confidence |\n|---|---|---|---|\n| levels | 2 storeys | view.png | estimated |\n\n## Contradictions\n\n| Fact | Source A | Value A | Source B | Value B | Status |\n|---|---|---|---|---|---|\n", blocks=blocks))
    assert not r["ok"] and any("no scale anchor needed" in e for e in r["errors"])
    anchor = {"needed": True, "confirmed": False, "question": "Q001"}
    r = check(folder(tmp_path / "b", files=(PNG,), blocks=blocks, anchor=anchor,
                     facts="## Facts\n\n| Fact | Value | Source | Confidence |\n|---|---|---|---|\n| levels | 6.6 m | view.png | measured |\n\n## Contradictions\n\n| Fact | Source A | Value A | Source B | Value B | Status |\n|---|---|---|---|---|---|\n"))
    assert not r["buildable"] and "the scale anchor is not confirmed" in r["not_buildable_because"]
    assert any("measured needs a source read for geometry" in e for e in r["errors"])
    assert any("while the scale anchor is not confirmed" in e for e in r["errors"])


def test_a_pdf_dimension_is_read_from_a_drawing_not_measured(tmp_path):
    facts = FACTS.replace("| levels | 0 / 3.3 / 6.6 m | etalon.fbx | measured |", "| levels | 0 / 3.3 / 6.6 m | album.pdf#p3 | measured |")
    r = check(folder(tmp_path, facts=facts))
    assert any("measured needs a source read for geometry" in e for e in r["errors"])
    r = check(folder(tmp_path / "b", facts=facts.replace("album.pdf#p3 | measured |", "album.pdf#p3 | read_from_drawing |", 1)))
    assert r["ok"], r["errors"]


def test_the_best_ranked_source_is_primary(tmp_path):
    rvt = {"path": "model.rvt", "format": "rvt", "reads": ["geometry", "dimensions"], "opened": True, "role": "check"}
    r = check(folder(tmp_path, files=(FBX, rvt, dict(PDF, path="album.pdf"), PNG)))
    assert not r["ok"] and any("primary only for the best-ranked source" in e for e in r["errors"])


def test_a_source_that_did_not_open_says_why(tmp_path):
    broken = {"path": "old.skp", "format": "skp", "reads": [], "opened": False, "role": "none"}
    r = check(folder(tmp_path, files=(FBX, dict(PDF, path="album.pdf"), PNG, broken)))
    assert not r["ok"] and any("did not open reads nothing and says why" in e for e in r["errors"])


def test_contradictions_stay_open_and_sources_must_exist(tmp_path):
    r = check(folder(tmp_path, facts=FACTS.replace("| open |", "| resolved: fbx wins |").replace("view.png | estimated", "photo.jpg | estimated")))
    assert any("does not resolve it" in e for e in r["errors"])
    assert any("'photo.jpg' is not in sources.json" in e for e in r["errors"])


def test_cli_fails_on_a_broken_intake(tmp_path):
    good = folder(tmp_path)
    assert main(["intake", "check", "--dir", str(good)]) == 0
    (good / "picture.md").unlink()
    assert main(["intake", "check", "--dir", str(good)]) == 1


@pytest.mark.parametrize("name", ["sources.json", "spec-draft.json", "questions.md"])
def test_every_intake_file_is_required(tmp_path, name):
    d = folder(tmp_path)
    (d / name).unlink()
    r = check(d)
    assert not r["ok"] and f"{name} missing" in r["errors"]


# Codex review 1 of PR #71


def test_an_image_cannot_be_declared_geometry(tmp_path):
    spoof = dict(PNG, reads=["geometry"], role="primary")
    blocks = {k: block(B01[k], "measured", ("view.png",)) for k in ("frame", "levels", "floors", "roof")}
    r = check(folder(tmp_path, files=(spoof,), blocks=blocks))
    assert not r["ok"] and not r["buildable"] and any("cannot give ['geometry']" in e for e in r["errors"])


def test_an_unknown_block_is_never_a_default(tmp_path):
    blocks = {k: block(B01[k]) for k in ("frame", "levels", "floors", "roof")} | {"opening_depth_default_m": block(None, "unknown")}
    r = check(folder(tmp_path, blocks=blocks))
    assert r["ok"] and not r["buildable"] and r["not_buildable_because"] == ["opening_depth_default_m is null"]
    r = check(folder(tmp_path / "b"))
    assert r["buildable"] and "opening_depth_default_m" in r["defaults_used"]


def test_draft_blocks_cite_the_primary_source(tmp_path):
    blocks = {k: block(B01[k], "read_from_drawing", ("album.pdf#p3",)) for k in ("frame", "levels", "floors", "roof")}
    r = check(folder(tmp_path, blocks=blocks))
    assert not r["ok"] and any("cites no primary source" in e for e in r["errors"])


EMPTY_CONTRA = "## Contradictions\n\n| Fact | Source A | Value A | Source B | Value B | Status |\n|---|---|---|---|---|---|\n"


@pytest.mark.parametrize("bad, message", [
    (FACTS.replace("| levels | 0 / 3.3 / 6.6 m | etalon.fbx | measured |", "| levels | 0 / 3.3 / 6.6 m | etalon.fbx | measured | extra |"),
     "a row with 5 cells under 4 columns"),
    ("## Facts\n\n| nonsense |\n|---|\n\n" + EMPTY_CONTRA, "Facts: columns must be"),     # empty, wrong header
])
def test_malformed_tables_fail(tmp_path, bad, message):
    r = check(folder(tmp_path, facts=bad))
    assert not r["ok"] and any(message in e for e in r["errors"]), r["errors"]


def test_a_contradiction_is_answered_only_through_a_users_answer(tmp_path):
    r = check(folder(tmp_path, facts=FACTS.replace("| open |", "| answered_by_agent |")))
    assert any("the agent does not resolve it" in e for e in r["errors"])
    r = check(folder(tmp_path / "b", facts=FACTS.replace("| open |", "| answered: Q001 |")))
    assert any("the agent does not resolve it" in e for e in r["errors"])          # no Q001 answered


def test_questions_file_format_and_the_anchor_question(tmp_path):
    d = folder(tmp_path)
    (d / "questions.md").write_text("this is not a questions file", encoding="utf-8")
    assert any("questions-file format" in e for e in check(d)["errors"])
    blocks = {k: block(B01[k], "estimated", ("view.png",)) for k in ("frame", "levels", "floors", "roof")}
    r = check(folder(tmp_path / "b", files=(PNG,), blocks=blocks, anchor={"needed": True, "question": "Q999"},
                     facts="## Facts\n\n| Fact | Value | Source | Confidence |\n|---|---|---|---|\n\n## Contradictions\n\n"
                           "| Fact | Source A | Value A | Source B | Value B | Status |\n|---|---|---|---|---|---|\n"))
    assert any("anchor question Q999 is not in questions.md" in e for e in r["errors"])


def test_stated_values_and_contradictions_name_their_sources(tmp_path):
    facts = FACTS.replace("| facade colour | grey | view.png | estimated |", "| height | 6.6 | — | unknown |")
    r = check(folder(tmp_path, facts=facts))
    assert any("stated value with confidence unknown" in e for e in r["errors"])
    facts = FACTS.replace("| parapet | etalon.fbx | 0.60 m | album.pdf#p3 | 0.65 m | open |", "| parapet | — | 0.60 m | — | 0.65 m | open |")
    assert any("both sides name their sources" in e for e in check(folder(tmp_path / "b", facts=facts))["errors"])


def test_read_from_drawing_needs_dimensions_not_geometry(tmp_path):
    facts = FACTS.replace("| levels | 0 / 3.3 / 6.6 m | etalon.fbx | measured |", "| levels | 0 / 3.3 / 6.6 m | etalon.fbx | read_from_drawing |")
    r = check(folder(tmp_path, files=(dict(FBX, reads=["geometry"]), dict(PDF, path="album.pdf"), PNG), facts=facts))
    assert any("read_from_drawing needs a source read for dimensions" in e for e in r["errors"])


# Codex review 2 of PR #71


def _questions(d, rows):
    """questions.md of the synthetic object with rows (id, answer)."""
    from dt_ai.spec.questions_file import COLUMNS
    lines = ["# Questions — bench-synth-box", "", "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for qid, answer in rows:
        cells = {c: "—" for c in COLUMNS} | {"ID": qid, "Status": "answered" if answer else "open", "Answer": answer}
        lines.append("| " + " | ".join(cells[c] for c in COLUMNS) + " |")
    (d / "questions.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


IMG_FACTS = ("## Facts\n\n| Fact | Value | Source | Confidence |\n|---|---|---|---|\n"
             "| levels | 2 storeys | view.png | estimated |\n\n" + EMPTY_CONTRA)


@pytest.mark.parametrize("answer, ok", [("", False), ("door height 2.1 m", True)])
def test_an_anchor_is_confirmed_only_by_the_users_answer(tmp_path, answer, ok):
    blocks = {k: block(B01[k], "estimated", ("view.png",)) for k in ("frame", "levels", "floors", "roof")}
    d = folder(tmp_path, files=(PNG,), facts=IMG_FACTS, blocks=blocks,
               anchor={"needed": True, "confirmed": True, "what": "door height 2.1 m", "question": "Q001"})
    _questions(d, [("Q001", answer)])
    r = check(d)
    assert r["ok"] == ok and r["buildable"] == ok, r["errors"]


def test_a_lower_ranked_source_lends_no_confidence_to_a_draft_block(tmp_path):
    blocks = {k: block(B01[k], "read_from_drawing", ("etalon.fbx", "album.pdf#p3")) for k in ("frame", "levels", "floors", "roof")}
    r = check(folder(tmp_path, files=(dict(FBX, reads=["geometry"]), dict(PDF, path="album.pdf"), PNG), blocks=blocks))
    assert any("read_from_drawing needs a source read for dimensions" in e for e in r["errors"])


def test_question_ids_are_unique(tmp_path):
    d = folder(tmp_path, facts=FACTS.replace("| open |", "| answered: Q001 |"))
    _questions(d, [("Q001", ""), ("Q001", "grey")])
    assert any("given more than once" in e for e in check(d)["errors"])


def test_one_facts_section(tmp_path):
    extra = FACTS + "\n## Facts\n\n| Fact | Value | Source | Confidence |\n|---|---|---|---|\n| height | 100 m | absent.fbx | measured |\n"
    assert any("more than one '## Facts' section" in e for e in check(folder(tmp_path, facts=extra))["errors"])


def test_an_unopened_source_is_no_evidence(tmp_path):
    broken = dict(PNG, opened=False, reads=[], not_opened_reason="corrupt")
    r = check(folder(tmp_path, files=(FBX, dict(PDF, path="album.pdf"), broken)))
    assert any("'view.png' did not open; it is no evidence" in e for e in r["errors"])


def test_the_draft_is_of_the_inventorys_object(tmp_path):
    d = folder(tmp_path)
    draft = json.loads((d / "spec-draft.json").read_text(encoding="utf-8"))
    draft["object"] = "wrong-object"
    (d / "spec-draft.json").write_text(json.dumps(draft), encoding="utf-8")
    assert any("is not the inventory's" in e for e in check(d)["errors"])

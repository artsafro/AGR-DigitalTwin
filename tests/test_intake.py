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

"""One questions file per object, merged from versioned spec reports (issue #7, user request 2026-10-08)."""
import json

from dt_ai.cli.main import main
from dt_ai.spec.questions_file import merge, parse
from test_spec_contour_shapes import SQUARE10, at, prism


def q(kind="projection", heights=(0.0, 0.6), x=5.0, depth=0.1):
    return {"priority": "high", "kind": kind, "levels": ["L0"], "wall": 0, "depth_m": depth, "length_m": 10.0,
            "facade_share": 1.0, "heights_m": list(heights), "at": [x, -0.05]}


def test_ids_are_stable_and_answers_survive_new_versions():
    v1 = merge(None, "tec26-kpp1", "v001", [q(), q("recess", (1.0, 1.5), 2.0)])
    _, rows = parse(v1)
    assert [(r["ID"], r["Status"], r["First"]) for r in rows] == [("Q001", "open", "v001"), ("Q002", "open", "v001")]
    answered = v1.replace("| 0.000–0.600 | 5.00, -0.05 |  |", "| 0.000–0.600 | 5.00, -0.05 | plinth: texture only |", 1)
    assert answered != v1
    v2 = merge(answered, "tec26-kpp1", "v002", [q(depth=0.12), q("projection", (3.0, 3.3), 5.0)])
    rows = {r["ID"]: r for r in parse(v2)[1]}
    assert rows["Q001"]["Answer"] == "plinth: texture only" and rows["Q001"]["Status"] == "answered"
    assert rows["Q001"]["Last"] == "v002" and rows["Q001"]["Depth m"] == "0.12"
    assert rows["Q002"]["Status"] == "gone v002"                     # not raised by v002, kept
    assert rows["Q003"]["First"] == "v002" and rows["Q003"]["Status"] == "open"


def test_cli_merges_a_version_into_the_object_file(tmp_path):
    dump, obj = tmp_path / "dump.json", tmp_path / "object.json"
    dump.write_text(json.dumps(prism(SQUARE10, boxes=[(0, 0.0, 10.0, 0.0, 0.6, 0.1)])), encoding="utf-8")
    obj.write_text(json.dumps(at(L0=2.0)), encoding="utf-8")
    spec = tmp_path / "spec-v001.json"
    assert main(["spec", "extract", "--dump", str(dump), "--object", str(obj), "--output", str(spec)]) == 0
    into = tmp_path / "job" / "questions.md"
    args = ["spec", "merge-questions", "--report", str(spec.with_suffix(".report.json")), "--version", "v001",
            "--into", str(into)]
    assert main(args) == 0 and main(args) == 0                       # re-merging the same version is stable
    (row,) = parse(into.read_text(encoding="utf-8"))[1]
    assert (row["ID"], row["Kind"], row["Status"]) == ("Q001", "projection", "open")


# --- regressions from Codex review 1 of PR #20 -------------------------------------------------

import pytest  # noqa: E402


def answered_file():
    text = merge(None, "tec26-kpp1", "v001", [q()])
    return text.replace("| 0.000–0.600 | 5.00, -0.05 |  |", r"| 0.000–0.600 | 5.00, -0.05 | keep a\|b |", 1)


@pytest.mark.parametrize("fmt", ["no-padding", "indent"])
def test_valid_markdown_variants_keep_answers(fmt):
    # F7: rows without spaces around pipes or indented are still rows; escaped pipes stay
    text = answered_file()
    if fmt == "no-padding":
        text = "\n".join(l.replace(" | ", "|") if l.startswith("| Q") else l for l in text.splitlines())
    else:
        text = "\n".join("  " + l if l.startswith("|") else l for l in text.splitlines())
    _, rows = parse(merge(text, "tec26-kpp1", "v002", [q()]))
    assert rows[0]["Answer"] == r"keep a\|b" and rows[0]["Status"] == "answered"


def test_unreadable_rows_are_never_overwritten():
    broken = answered_file().replace("| Q001 |", "| Q001 | extra |")
    with pytest.raises(ValueError, match="not overwriting"):
        merge(broken, "tec26-kpp1", "v002", [q()])


def test_small_drift_keeps_the_answer_on_the_same_question():
    # F8: 0.2 mm in heights or position is the same question
    text = answered_file()
    moved = {**q(), "heights_m": [0.0002, 0.6049], "at": [5.0499, -0.0502]}
    _, rows = parse(merge(text, "tec26-kpp1", "v002", [moved]))
    assert len(rows) == 1 and rows[0]["Answer"] == r"keep a\|b" and rows[0]["Last"] == "v002"


def test_other_object_and_bad_report_are_refused():
    with pytest.raises(ValueError, match="belongs to tec26-kpp1"):
        merge(answered_file(), "tec26-psu275", "v002", [q()])
    with pytest.raises(ValueError, match="no questions list"):
        merge(None, "tec26-kpp1", "v001", None)

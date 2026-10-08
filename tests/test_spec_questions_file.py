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
    rows = parse(v1)
    assert [(r["ID"], r["Status"], r["First"]) for r in rows] == [("Q001", "open", "v001"), ("Q002", "open", "v001")]
    answered = v1.replace("| v001 | v001 | high | projection | L0 | 0 | 0.1 | 10.0 | 100.0% | 0.00–0.60 | 5.0, -0.1 |  |",
                          "| v001 | v001 | high | projection | L0 | 0 | 0.1 | 10.0 | 100.0% | 0.00–0.60 | 5.0, -0.1 | plinth: texture only |")
    assert answered != v1
    v2 = merge(answered, "tec26-kpp1", "v002", [q(depth=0.12), q("projection", (3.0, 3.3), 5.0)])
    rows = {r["ID"]: r for r in parse(v2)}
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
    (row,) = parse(into.read_text(encoding="utf-8"))
    assert (row["ID"], row["Kind"], row["Status"]) == ("Q001", "projection", "open")

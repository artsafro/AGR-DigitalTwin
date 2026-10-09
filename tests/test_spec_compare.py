"""Comparison of two specs (issue #11). Synthetic specs; not a real object."""
import json

import pytest

from dt_ai.cli.main import main
from dt_ai.spec.compare import CompareError, compare_specs

FRAME = {"object": "bench-synth-box", "to_object": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}
TOL = {"spec_compare": {"level_elev_m": 0.03, "contour_area_rel": 0.02, "contour_hausdorff_m": 0.05, "opening_bbox_m": 0.05},
       "reference": {"levels": "revit", "roof": "revit", "parapet": "revit", "contours": None, "openings": None},
       "verdict": {"enabled": True}}
REPORT = {"roof": {"plane_m": 6.6, "parapet_top_m": 7.2}}


def spec(source, contour=((0, 0), (10, 0), (10, 10), (0, 10)), openings=None, roof_elev=6.6, levels=None):
    openings = openings if openings is not None else [{"wall": 0, "x_m": 2.0, "sill_m": 0.9, "w_m": 1.5, "h_m": 1.5, "depth_m": 0.2}]
    return {"id": "bench-synth-box", "profile": "npm_min", "frame": {**FRAME, "source": source},
            "levels": levels or [{"name": "L0", "elev_m": 0.0}, {"name": "roof", "elev_m": roof_elev}],
            "floors": [{"level": "L0", "contour": [list(p) for p in contour], "openings": openings}],
            "roof": {"parapet_h_m": 0.6}}


def test_identical_specs_match():
    out = compare_specs(spec("revit"), spec("mesh"), REPORT, REPORT, TOL, ("revit", "mesh"))
    assert out["verdict"] == "match" and out["failing"] == [] and out["contour_differences"] == []
    assert next(r for r in out["rows"] if r["criterion"] == "level count")["reference"] == "revit"


def test_contour_offset_fails_hausdorff_and_lists_the_region():
    moved = spec("mesh", contour=((0, -0.1), (10, -0.1), (10, 10), (0, 10)))
    out = compare_specs(spec("revit"), moved, REPORT, REPORT, TOL, ("revit", "mesh"))
    assert out["verdict"] == "no match" and "contour Hausdorff, m L0" in out["failing"]
    assert "contour area, m2 (relative) L0" not in out["failing"]          # 1 % < 2 %
    assert out["contour_differences"] == [{"level": "L0", "side": "mesh only", "area_m2": 1.0, "reach_m": 0.1,
                                           "bounds": [0.0, -0.1, 10.0, 0.0]}]


def test_opening_pair_box_is_measured_in_the_object_system():
    # the same window, but the mesh contour starts at another corner: wall 2 instead of wall 0
    other = spec("mesh", contour=((10, 10), (0, 10), (0, 0), (10, 0)),
                 openings=[{"wall": 2, "x_m": 2.03, "sill_m": 0.9, "w_m": 1.5, "h_m": 1.5, "depth_m": 0.2}])
    out = compare_specs(spec("revit"), other, REPORT, REPORT, TOL, ("revit", "mesh"))
    row = next(r for r in out["rows"] if r["criterion"].startswith("opening pair"))
    assert row["b"] == pytest.approx(0.03) and row["within"] and row["pairs"] == 1


def test_level_count_differs_stops_the_comparison():
    three = spec("mesh", levels=[{"name": "L0", "elev_m": 0.0}, {"name": "L1", "elev_m": 3.3}, {"name": "roof", "elev_m": 6.6}])
    out = compare_specs(spec("revit"), three, REPORT, REPORT, TOL, ("revit", "mesh"))
    assert out["failing"] == ["level count"] and len(out["rows"]) == 1 and out["verdict"] == "no match"


def test_verdict_is_deferred_when_tolerances_say_so():
    tol = {**TOL, "verdict": {"enabled": False, "reason": "contours wait for #29"}}
    moved = spec("mesh", contour=((0, -0.1), (10, -0.1), (10, 10), (0, 10)))
    out = compare_specs(spec("revit"), moved, REPORT, REPORT, tol, ("revit", "mesh"))
    assert out["verdict"] == "deferred" and out["verdict_note"] == "contours wait for #29" and out["failing"]


def test_thresholds_come_from_tolerances():
    tol = {**TOL, "spec_compare": {**TOL["spec_compare"], "contour_hausdorff_m": 0.2}}
    moved = spec("mesh", contour=((0, -0.1), (10, -0.1), (10, 10), (0, 10)))
    out = compare_specs(spec("revit"), moved, REPORT, REPORT, tol, ("revit", "mesh"))
    assert "contour Hausdorff, m L0" not in out["failing"]
    assert out["failing"] == ["opening pairs within bbox tolerance, m (worst pair) L0"]       # the window moved 0.1 m with its wall


def test_different_objects_are_refused():
    with pytest.raises(CompareError, match="different objects"):
        compare_specs(spec("revit"), {**spec("mesh"), "id": "other-box"}, REPORT, REPORT, TOL)


def test_cli_writes_json_and_markdown(tmp_path):
    for name, src in (("a", "revit"), ("b", "mesh")):
        (tmp_path / f"{name}.json").write_text(json.dumps(spec(src)), encoding="utf-8")
        (tmp_path / f"{name}.report.json").write_text(json.dumps(REPORT), encoding="utf-8")
    (tmp_path / "tol.json").write_text(json.dumps(TOL), encoding="utf-8")
    out = tmp_path / "cmp.json"
    args = ["spec", "compare", "--a", str(tmp_path / "a.json"), "--b", str(tmp_path / "b.json"),
            "--tolerances", str(tmp_path / "tol.json"), "--output", str(out)]
    assert main(args) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["verdict"] == "match"
    assert "| L0 | contour Hausdorff, m |" in out.with_suffix(".md").read_text(encoding="utf-8")
    assert main(args) != 0                                   # never overwrites a comparison


# PR #32 review 1 regressions

def test_small_outward_bump_is_listed_with_its_reach():
    # a 0.075 x 0.09 m frame profile out of the north wall (0.007 m2): listed, not filtered away
    bump = spec("mesh", contour=((0, 0), (10, 0), (10, 10), (5.075, 10), (5.075, 10.09), (5, 10.09), (5, 10), (0, 10)))
    out = compare_specs(spec("revit"), bump, REPORT, REPORT, TOL, ("revit", "mesh"))
    assert out["contour_differences"] == [{"level": "L0", "side": "mesh only", "area_m2": 0.0068, "reach_m": 0.09,
                                           "bounds": [5.0, 10.0, 5.075, 10.09]}]


def test_each_side_uses_its_own_level_elevation():
    # level 2 cm higher and sill 4 cm higher on b: the window moves 6 cm (> 5 cm)
    b = spec("mesh", openings=[{"wall": 0, "x_m": 2.0, "sill_m": 0.94, "w_m": 1.5, "h_m": 1.5, "depth_m": 0.2}])
    b["levels"][0]["elev_m"] = 0.02
    out = compare_specs(spec("revit"), b, REPORT, REPORT, TOL, ("revit", "mesh"))
    row = next(r for r in out["rows"] if r["criterion"].startswith("opening pairs"))
    assert not row["within"] and out["verdict"] == "no match"


def test_opening_depth_is_part_of_its_box():
    deep = spec("mesh", openings=[{"wall": 0, "x_m": 2.0, "sill_m": 0.9, "w_m": 1.5, "h_m": 1.5, "depth_m": 0.8}])
    out = compare_specs(spec("revit"), deep, REPORT, REPORT, TOL, ("revit", "mesh"))
    assert "opening pairs within bbox tolerance, m (worst pair) L0" in out["failing"]


def test_a_missing_floor_is_not_skipped():
    a = spec("revit", levels=[{"name": "L0", "elev_m": 0.0}, {"name": "L1", "elev_m": 3.3}, {"name": "roof", "elev_m": 6.6}])
    b = json.loads(json.dumps(a))
    b["floors"].append({"level": "L1", "contour": [[0, 0], [10, 0], [10, 10], [0, 10]], "openings": []})
    a["floors"][0]["repeat_to"] = None
    out = compare_specs(a, {**b, "frame": {**FRAME, "source": "mesh"}}, REPORT, REPORT, TOL, ("revit", "mesh"))
    assert "floors" in out["failing"] and out["verdict"] == "no match"


def test_pairing_finds_the_correspondence_a_greedy_order_misses():
    def ops(*xs):
        return [{"wall": 0, "x_m": x, "sill_m": 0.9, "w_m": 1.0, "h_m": 1.5, "depth_m": 0.2} for x in xs]
    out = compare_specs(spec("revit", openings=ops(2.00, 2.06)), spec("mesh", openings=ops(2.04, 2.10)),
                        REPORT, REPORT, TOL, ("revit", "mesh"))
    row = next(r for r in out["rows"] if r["criterion"].startswith("opening pairs"))
    assert row["within"] and row["pairs"] == 2 and row["b"] == pytest.approx(0.04)


def test_threshold_is_applied_to_the_raw_value():
    moved = spec("mesh", contour=((0, -0.05004), (10, -0.05004), (10, 10), (0, 10)), openings=[])
    out = compare_specs(spec("revit", openings=[]), moved, REPORT, REPORT, TOL, ("revit", "mesh"))
    assert "contour Hausdorff, m L0" in out["failing"]


def test_two_specs_without_openings_match():
    out = compare_specs(spec("revit", openings=[]), spec("mesh", openings=[]), REPORT, REPORT, TOL, ("revit", "mesh"))
    assert out["verdict"] == "match"


def test_notch_reach_is_its_depth_not_zero():
    # the region of a 0.23 m notch has all its corners on the other contour; its reach is 0.23
    notch = spec("mesh", contour=((0, 0), (4, 0), (4, 0.23), (5, 0.23), (5, 0), (10, 0), (10, 10), (0, 10)))
    out = compare_specs(spec("revit"), notch, REPORT, REPORT, TOL, ("revit", "mesh"))
    assert [(g["side"], g["reach_m"]) for g in out["contour_differences"]] == [("revit only", 0.23)]


def test_floor_order_in_the_file_does_not_matter():
    # PR #32 review 2: the same floors listed L1, L0 on one side
    levels = [{"name": "L0", "elev_m": 0.0}, {"name": "L1", "elev_m": 3.3}, {"name": "roof", "elev_m": 6.6}]
    a = spec("revit", levels=levels)
    a["floors"].append({"level": "L1", "contour": [[0, 0], [10, 0], [10, 10], [0, 10]], "openings": []})
    b = {**json.loads(json.dumps(a)), "frame": {**FRAME, "source": "mesh"}}
    b["floors"].reverse()
    assert compare_specs(a, b, REPORT, REPORT, TOL, ("revit", "mesh"))["verdict"] == "match"



def test_kinds_aside_are_reported_but_not_in_the_verdict():
    # grilles of an npm_min texture-only source: listed in tolerances, reported per level, not in the verdict
    grille = {"wall": 1, "x_m": 4.0, "sill_m": 3.0, "w_m": 0.3, "h_m": 0.4, "kind": "grille"}
    a = spec("revit")
    a["floors"][0]["openings"].append(grille)
    tol = {**TOL, "spec_compare": {**TOL["spec_compare"], "opening_kinds_not_in_verdict": ["grille"]}}
    out = compare_specs(a, spec("mesh"), REPORT, REPORT, tol, ("revit", "mesh"))
    assert out["verdict"] == "match"
    row = next(r for r in out["rows"] if r["criterion"].startswith("openings of kind grille"))
    assert (row["a"], row["b"], row["within"]) == (1, 0, True)
    assert compare_specs(a, spec("mesh"), REPORT, REPORT, TOL, ("revit", "mesh"))["verdict"] == "no match"

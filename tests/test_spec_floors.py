"""Floor classification: typical_of / repeat_to (issue #8). Synthetic data; not a real object."""
import pytest
from shapely.geometry import Polygon

from dt_ai.spec import Spec, extract_spec
from test_spec_contour_shapes import SQUARE10, flat, walls
from test_spec_extract import OBJECT, Mesh, box_building

H = 3.3


def tower(levels=5, heights=None, windows=None):
    """`levels` storeys on a 10 x 10 m plan: a door on L0, the same two windows on every middle
    storey, three windows on the top one. windows: {storey: [(u0, u1)]} overrides."""
    heights = heights or [H] * levels
    elev = [sum(heights[:i]) for i in range(levels + 1)]
    boxes = [(0, 4.0, 5.0, 0.0, 2.1, 0.0)]                                   # door, L0
    for k in range(1, levels):
        default = [(1.0, 2.5), (6.0, 7.5)] if k < levels - 1 else [(1.0, 2.0), (4.0, 5.0), (7.0, 8.0)]
        for u0, u1 in (windows or {}).get(k, default):
            boxes.append((0, u0, u1, elev[k] + 0.9, elev[k] + 2.4, 0.0))
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, elev[-1], boxes, extra_z=elev[1:-1])
    flat(b, Polygon(SQUARE10), elev[-1], up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    names = [f"L{i}" for i in range(levels)] + ["roof"]
    return {"source": "synthetic-tower", "meshes": [b.dump()],
            "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]} for n, z in zip(names, elev)]}


def written(spec):
    return [(f.level, f.typical_of, f.repeat_to, f.contour is not None) for f in spec.floors]


def test_five_storeys_bottom_unique_three_typical_top_unique():
    spec, report = extract_spec(tower(), OBJECT)
    assert written(spec) == [("L0", None, None, True), ("L1", None, None, True), ("L2", "L1", "L3", False),
                             ("L4", None, None, True)]
    assert report["floor_classes"] == [
        {"levels": ["L0"], "class": "unique"},
        {"levels": ["L1", "L2", "L3"], "class": "typical", "template": "L1"},
        {"levels": ["L4"], "class": "unique"}]


def test_changed_opening_on_a_middle_floor_breaks_the_run():
    spec, report = extract_spec(tower(windows={2: [(1.0, 2.5), (6.2, 7.7)]}), OBJECT)
    assert all(f.contour is not None for f in spec.floors)      # L3 equals L1, not L2: no jump over L2
    assert [c["class"] for c in report["floor_classes"]] == ["unique"] * 5


def test_round_trip_gives_the_full_per_floor_data():
    spec, _ = extract_spec(tower(), OBJECT)
    full = spec.expanded_floors()
    assert [f.level for f in full] == ["L0", "L1", "L2", "L3", "L4"]
    for f in full[2:4]:
        assert (f.contour, f.openings) == (full[1].contour, full[1].openings)
    again = Spec.model_validate_json(spec.model_dump_json(exclude_none=True))
    assert again.expanded_floors() == full


def test_different_storey_height_is_not_typical():
    spec, report = extract_spec(tower(heights=[H, H, 3.6, H, H]), OBJECT)
    assert written(spec)[1:3] == [("L1", None, None, True), ("L2", None, None, True)]


def test_b01_box_is_written_as_in_the_plan():
    # HARNESS_PLAN §3 example: {"level": "L1", "typical_of": "L0", "repeat_to": "L1"}
    spec, _ = extract_spec(box_building(), OBJECT)
    assert written(spec) == [("L0", None, None, True), ("L1", "L0", "L1", False)]


def test_typical_of_must_point_to_a_full_floor_below():
    spec, _ = extract_spec(box_building(), OBJECT)
    bad = spec.model_dump()
    bad["floors"][1]["typical_of"] = "roof"
    with pytest.raises(ValueError, match="typical_of must be a full floor below"):
        Spec.model_validate(bad)


# --- regressions from Codex review 1 of the #8 PR -------------------------------------------------

from dt_ai.spec.floors import collapse, same_floor  # noqa: E402

LV = [{"name": f"L{i}", "elev_m": H * i} for i in range(11)]
OPEN = {"wall": 0, "x_m": 2.0, "sill_m": 1.0, "w_m": 1.0, "h_m": 1.0, "depth_m": 0.2, "source": "hole"}


def floor(name, dx=0.0, openings=(OPEN,)):
    return {"level": name, "contour": [[0 + dx, 0], [10 + dx, 0], [10 + dx, 10], [0 + dx, 10]],
            "openings": [dict(o) for o in openings]}


def test_small_drift_does_not_add_up_along_a_run():
    # F1: 6 mm per floor passes every neighbour, but not the template after two floors
    floors = [floor(f"L{i}", dx=0.006 * i) for i in range(10)]
    out, classes = collapse(LV, floors)
    for c in classes:
        if c["class"] == "typical":
            i0, i1 = int(c["levels"][0][1:]), int(c["levels"][-1][1:])
            assert 0.006 * (i1 - i0) <= 0.01


def test_contour_match_moves_radii_and_walls_with_the_vertices():
    # F2: the same square started at another corner; opening wall indices follow the match
    a = {"level": "L0", "contour": [[0, 0], [10, 0], [10, 10, {"r": 1.0}], [0, 10]], "openings": [dict(OPEN)]}
    b = {"level": "L1", "contour": [[10, 0], [10, 10, {"r": 1.0}], [0, 10], [0, 0]],
         "openings": [{**OPEN, "wall": 3}]}                       # south wall is wall 3 in b's numbering
    assert same_floor(a, b, H, H)
    moved_radius = {**b, "contour": [[10, 0, {"r": 1.0}], [10, 10], [0, 10], [0, 0]]}
    assert not same_floor(a, moved_radius, H, H)
    other_wall = {**b, "contour": [[10, -0.006], [10, 10], [0, 10], [0, 0]], "openings": [dict(OPEN)]}
    assert not same_floor(a, other_wall, H, H)                   # wall 0 of b is the east wall


def test_plane_conflict_is_part_of_the_opening():
    # F3
    assert not same_floor(floor("L0"), floor("L1", openings=({**OPEN, "plane_conflict": True},)), H, H)


def test_typical_entries_are_validated():
    # F4/F5: overlap with a full floor, repeat to the roof level, openings on a typical entry
    spec, _ = extract_spec(tower(), OBJECT)
    base = spec.model_dump()
    overlap = {**base, "floors": base["floors"] + [{**base["floors"][1], "level": "L3"}]}
    to_roof = {**base, "floors": [dict(f) for f in base["floors"]]}
    to_roof["floors"][2] = {**to_roof["floors"][2], "repeat_to": "roof"}
    own = {**base, "floors": [dict(f) for f in base["floors"]]}
    own["floors"][2] = {**own["floors"][2], "openings": [OPEN]}
    for bad, msg in ((overlap, "given twice"), (to_roof, "stop below the top level"), (own, "no openings of its own")):
        with pytest.raises(ValueError, match=msg):
            Spec.model_validate(bad)


def test_opening_order_does_not_matter():
    # F6: two openings with the same wall, x and sill
    o1, o2 = OPEN, {**OPEN, "w_m": 2.0}
    assert same_floor(floor("L0", openings=(o1, o2)), floor("L1", openings=(o2, o1)), H, H)


def test_cli_counts_floors_not_entries(tmp_path, capsys):
    # F7
    import json
    from dt_ai.cli.main import main
    dump, obj, out = tmp_path / "dump.json", tmp_path / "object.json", tmp_path / "spec-v001.json"
    dump.write_text(json.dumps(tower()), encoding="utf-8")
    obj.write_text(json.dumps(OBJECT), encoding="utf-8")
    assert main(["spec", "extract", "--dump", str(dump), "--object", str(obj), "--output", str(out)]) == 0
    assert "5 floors (4 written)" in capsys.readouterr().out

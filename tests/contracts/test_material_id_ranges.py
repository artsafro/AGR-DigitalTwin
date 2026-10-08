from pathlib import Path

import yaml


def test_material_id_ranges_are_ordered_and_disjoint():
    data = yaml.safe_load((Path(__file__).resolve().parents[2] / "standards/material_id_ranges.yaml").read_text(encoding="utf-8"))
    groups = sorted(data["groups"].values(), key=lambda g: g["first"])
    assert data["unassigned"] == 0 and groups[0]["first"] == 1
    for g in groups:
        assert g["first"] <= g["last"]
    for a, b in zip(groups, groups[1:]):
        assert a["last"] < b["first"]

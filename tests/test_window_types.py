"""library/windows/window_types.json (issue #4, user decision 2026-10-09)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "library"))
from build_window_types import layout  # noqa: E402

DOC = json.loads((ROOT / "library" / "windows" / "window_types.json").read_text(encoding="utf-8"))
KEYS = {"id", "name", "status", "typed", "role", "width_m", "height_m", "sections", "transoms", "sashes", "handing",
        "panes", "panes_m", "variant_of", "source"}


CONFIRMED = {"W01", "W02", "W03", "W04", "W05", "W06", "W07", "D01", "D02", "D03", "KPP1-W01", "KPP1-W02", "KPP1-W03"}


def test_every_entry_has_the_agreed_fields():
    ids = [t["id"] for t in DOC["types"]]
    assert len(ids) == len(set(ids)) == 22
    for t in DOC["types"]:
        assert KEYS <= set(t), t["id"]
        assert t["status"] in ("confirmed", "unconfirmed") and t["handing"] is None and t["sashes"] is None, t["id"]
        assert t["width_m"] > 0 and t["height_m"] > 0, t["id"]


def test_only_the_users_confirmations_are_confirmed():
    # user decision 2026-10-09: the atlas types W01-W07, D01-D03 and the three KPP1 candidates, named by form + size
    confirmed = {t["id"]: t for t in DOC["types"] if t["status"] == "confirmed"}
    assert set(confirmed) == CONFIRMED
    for t in confirmed.values():
        assert t["name"] and t["decision"]["by"] == "user" and t["typed"], t["id"]
        size = f"{round(t['width_m'] * 1000)}×{round(t['height_m'] * 1000)}"
        assert t["name"].endswith(size) or t["id"] == "D01", (t["id"], t["name"], size)   # D01 2095 mm named 2100
        assert "створ" not in t["name"] and "KPP" not in t["name"] and "КПП" not in t["name"], t["name"]


def test_school_typology_is_complete():
    school = [t["id"] for t in DOC["types"] if t["source"]["object"] == "SOSH1150"]
    assert school == ["W01", "W02", "W03", "W04", "W05", "W06", "W07", "D01", "D02", "D03", "D04",
                      "W01_H", "W02_H", "W03_H", "W01_N", "W04_N", "D03_W", "CW_021", "CW_022"]


def test_untyped_rows_are_kept_and_marked():
    untyped = {t["id"]: t for t in DOC["types"] if not t["typed"]}
    assert set(untyped) == {"CW_021", "CW_022", "D04"}
    assert all(t["note"].startswith("не типизирован") for t in untyped.values())


def test_kpp1_candidates_come_from_the_spec():
    kpp1 = [t for t in DOC["types"] if t["source"]["object"] == "tec26-kpp1"]
    assert [(t["width_m"], t["height_m"], t["panes"], t["source"]["occurrences"]) for t in kpp1] == [
        (1.18, 1.8, 1, 18), (1.18, 5.45, 4, 1), (2.0, 1.8, 2, 1)]


@pytest.mark.parametrize("panes, expected", [
    ([[0.07, 0.07, 1.55, 2.83], [1.62, 0.07, 2.54, 0.55], [1.67, 0.67, 2.49, 2.24], [1.67, 2.41, 2.49, 2.78],
      [2.61, 0.07, 3.53, 2.83]], (3, 2)),                        # W01: three fields, the middle one in three
    ([[0.05, 0.05, 1.0, 2.75], [1.1, 0.05, 2.05, 2.75]], (2, 0)),  # two tall fields, no transom
    ([], (None, None)),
])
def test_layout_counts_sections_and_transoms(panes, expected):
    assert layout(panes) == expected

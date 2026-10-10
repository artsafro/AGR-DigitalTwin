"""Level helpers generated from a Revit model (pattern markup-helpers, MH2, user decisions 2026-10-10).

Revit levels are not placed by hand: `tools/source/measure_spec_revit_twin.mjs` reads the document's Levels
and Roofs into twin-data.json (`revit_levels`, `revit_roofs`), and object.json maps them to spec names:

    "revit_levels": {
      "levels": {"отм. 0,000": "L0", "отм. +3,900": "L1", "отм. +7,700": null},   # null = not a floor
      "roof": {"type": "<Revit roof type>"}                                         # LEVEL_roof
    }

A mapped level becomes LEVEL_<name> at its elevation; LEVEL_roof is the top of the roof covering — the
roof element's base level + offset + its volume / area (the covering's mean thickness; user decision
2026-10-10: "верх покрытия кровли"). A Revit level the table does not name is a question, never a guess.
"""


class MarkupError(ValueError):
    pass


def revit_level_helpers(dump, table):
    """(helpers, questions) for a revit-twin dump and the object's `revit_levels` table."""
    levels = dump.get("revit_levels")
    if levels is None:
        raise MarkupError("the Revit export has no levels (twin-data.json revit_levels); re-export with "
                          "tools/source/measure_spec_revit_twin.mjs")
    names = table.get("levels", {})
    helpers, questions = [], []
    for lv in levels:
        if lv["name"] not in names:
            questions.append({"priority": "high", "kind": "revit-level", "wall": None, "depth_m": None,
                              "length_m": None, "facade_share": None,
                              "heights_m": [round(lv["elevation_m"], 3), round(lv["elevation_m"], 3)], "at": None,
                              "revit_level": lv["name"]})
        elif names[lv["name"]] is not None:
            helpers.append({"name": f"LEVEL_{names[lv['name']]}", "location": [0.0, 0.0, lv["elevation_m"]]})
    roof = table.get("roof")
    if roof is not None:
        found = [r for r in dump.get("revit_roofs", []) if r["type"] == roof["type"]]
        if len(found) != 1:
            raise MarkupError(f"object.json revit_levels.roof type {roof['type']!r}: {len(found)} roof elements of "
                              "that type in the Revit export, need exactly one")
        r = found[0]
        if not r.get("area_m2") or r.get("volume_m3") is None:
            raise MarkupError(f"Revit roof {r['id']}: no volume / area to measure the covering thickness")
        top = r["base_level_m"] + r.get("offset_m", 0.0) + r["volume_m3"] / r["area_m2"]
        helpers.append({"name": "LEVEL_roof", "location": [0.0, 0.0, round(top, 4)],
                        "derived": f"roof {r['id']}: base {r['base_level_m']} + offset {r.get('offset_m', 0.0)} + "
                                   f"volume {r['volume_m3']} / area {r['area_m2']}"})
    return helpers, questions

"""Build library/windows/window_types.json (issue #4) from the user's window library and KPP1.

    uv run python tools/library/build_window_types.py --type-map <type-map.json> \
        --library-v001 <curtain-types.json> --kpp1-twin <twin-data.json> --kpp1-spec <spec.json> \
        --output library/windows/window_types.json

Pattern: none — library tooling, not a building node (REVIEW_CHECKLIST Q1: new-case).

Sources (read only; the user's .blend is not opened):
- SOSH1150 typology v003 (`jobs/REVIT-OPENINGS/outputs/openings-v003/type-map.json` in the user's
  project folder): 11 types and 6 size variants with their pane layouts;
- the untyped curtain assemblies CW_021 / CW_022 from `library-v001/curtain-types.json`;
- KPP1 facade windows from the Revit spec (spec v0.3) and their pane layout from the Revit export;
- the window file Win_Typical.max (`library/windows/sources/win-typical-max-v001.json`, read from
  3ds Max without changing it): frame extent, glass and opaque infill per object.

Duplicates (user decision 2026-10-09): the same subdivision — fields, transoms, panes and pane
layout within SAME_M — and the same size within SAME_M are one type; the later entry keeps its
row and points to the first with `same_as`. Names are form + size, no project.

User decision 2026-10-09: every entry is `unconfirmed` until the user confirms and names it — the
user's decisions are kept in library/windows/confirmations.json and applied here;
handing is null; CW_021, CW_022 and D04 are kept as rows marked not typed. Sections are the
vertical fields of a type, transoms the horizontal divisions of its most divided field, both from
the pane layout; opening sashes are not in the sources (null).
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

GAP_M = 0.02             # panes closer than this along an axis are in one field / row
SAME_M = 0.02            # same type: size and pane layout within 2 cm (user decision 2026-10-09)
FIELDS = {1: "однопольное", 2: "двухпольное", 3: "трёхпольное", 4: "четырёхпольное", 5: "пятипольное", 6: "шестипольное"}


def _clusters(ranges):
    """Merge intervals (a, b) that overlap or touch within GAP_M; returns the merged intervals."""
    out = []
    for a, b in sorted(ranges):
        if out and a <= out[-1][1] + GAP_M:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def layout(panes):
    """Sections and transoms of a pane layout [[x0, z0, x1, z1], ...] (metres from the bottom left)."""
    if not panes:
        return None, None
    columns = _clusters([(p[0], p[2]) for p in panes])
    transoms = 0
    for a, b in columns:
        rows = _clusters([(p[1], p[3]) for p in panes if p[0] >= a - GAP_M and p[2] <= b + GAP_M])
        transoms = max(transoms, len(rows) - 1)
    # fields: the most columns in one horizontal band, so a full-width transom above does not merge
    # the fields below it (an entrance door with a fanlight over two leaves)
    bands = _clusters([(p[1], p[3]) for p in panes])
    sections = max(len(_clusters([(p[0], p[2]) for p in panes if p[1] >= a - GAP_M and p[3] <= b + GAP_M]))
                   for a, b in bands)
    return max(sections, len(columns)), transoms


def entry(id_, name, role, width, height, panes, *, source, typed=True, note=None, variant_of=None, **extra):
    sections, transoms = layout(panes)
    out = {"id": id_, "name": name, "status": "unconfirmed", "typed": typed, "role": role,
           "width_m": round(width, 3), "height_m": round(height, 3), "sections": sections, "transoms": transoms,
           "sashes": None, "handing": None, "panes": len(panes) if panes else None,
           "panes_m": [[round(c, 3) for c in p] for p in panes] if panes else None, "variant_of": variant_of,
           "source": source}
    out.update(extra)
    if note:
        out["note"] = note
    return out


def _mm(v):
    return round(v * 1000)


def max_types(source, path):
    """Window types of a 3ds Max window file (library/windows/sources/*.json): frame extent, glass,
    opaque infill; name by form + size, no project."""
    out, prefix = [], source["id_prefix"]
    for n, o in enumerate(source["objects"], 1):
        door = "Дверь" in o["object"] or "Д_" in o["object"]
        fields = o["glass_m"] + o["opaque_m"]
        sections, transoms = layout(fields)
        words = FIELDS.get(sections, f"{sections}-польн")
        if door:
            base = f"Дверь {'остеклённая ' if o['glass_m'] else ''}{words[:-2]}ая"
        else:
            base = f"Окно {words}"
        extra = " с глухой фрамугой" if o["opaque_m"] else (" с фрамугой" if transoms else "")
        name = f"{base}{extra} {_mm(o['width_m'])}×{_mm(o['height_m'])}"
        out.append(entry(
            f"{prefix}-{n:02d}", name, "door" if door else "window", o["width_m"], o["height_m"], o["glass_m"],
            source={"object": Path(source["source"]["file"]).name, "file": Path(path).as_posix(),
                    "max_object": o["object"], "occurrences": None},
            opaque_m=o["opaque_m"] or None))
        if sections is not None:                  # members of the layout include the opaque infill
            out[-1]["sections"], out[-1]["transoms"] = sections, transoms
    return out


def _near(u, v):
    """Within SAME_M, inclusive, in whole millimetres (no binary-float edge, PR #43 review 1)."""
    return abs(round(u * 1000) - round(v * 1000)) <= round(SAME_M * 1000)


def _same(a, b):
    """Same subdivision — fields, transoms, glass and opaque infill with their layout — and size, all
    within SAME_M (user decision 2026-10-09)."""
    if (a["sections"], a["transoms"], a["panes"]) != (b["sections"], b["transoms"], b["panes"]):
        return False
    if not (_near(a["width_m"], b["width_m"]) and _near(a["height_m"], b["height_m"])):
        return False
    for key in ("panes_m", "opaque_m"):
        pa, pb = sorted(a.get(key) or []), sorted(b.get(key) or [])
        if len(pa) != len(pb) or not all(_near(u, v) for p, q in zip(pa, pb) for u, v in zip(p, q)):
            return False
    return True


def dedupe(types):
    """Each entry that repeats an earlier typed one points to it with same_as."""
    for i, t in enumerate(types):
        first = next((u for u in types[:i] if u["typed"] and not u.get("same_as") and _same(u, t)), None)
        t["same_as"] = first["id"] if (first and t["typed"]) else None
    return types


def sosh(type_map, curtain_types):
    src = {"object": "SOSH1150", "file": "jobs/REVIT-OPENINGS/outputs/openings-v003/type-map.json (user project)"}
    out = []
    for t in type_map["types"] + type_map["size_variants"]:
        untyped = t["id"] == "D04"
        out.append(entry(
            t["id"], t["title"], t["role"], t["width_m"], t["height_m"], t["panes_m"],
            source={**src, "fbx": t["source"], "merged": t["merged_sources"], "pdf_pages": t["pdf_pages"],
                    "match": t["match"], "occurrences": t["represented_occurrences"]},
            typed=not untyped, variant_of=t.get("family"), infill=t["infill"], frame_finish=t["frame_finish"],
            note="не типизирован: взят из FBX как пример полотна, к месту на фасаде не привязан" if untyped else None))
    by_id = {c["id"]: c for c in curtain_types}
    notes = {"CW_021": "не типизирован: особое членение (3 панели, 15 импостов, 1 окно)",
             "CW_022": "не типизирован: неоднозначные наложения панелей в исходнике; габарит по bbox, не проверен"}
    for cid in ("CW_021", "CW_022"):
        c = by_id[cid]
        dims = sorted(c["dimensions"], reverse=True)
        out.append(entry(cid, None, "curtain", dims[0], dims[1] if cid == "CW_021" else c["dimensions"][2], None,
                         source={**src, "file": "jobs/REVIT-OPENINGS/outputs/library-v001/curtain-types.json (user project)",
                                 "fbx": cid, "occurrences": len(c.get("placements", [])), "bbox_m": c["dimensions"],
                                 "counts": c.get("counts")},
                         typed=False, note=notes[cid]))
    return out


def kpp1(twin_index, spec_path):
    """Facade window types of KPP1 (Revit spec), with the pane layout of the Revit export."""
    from dt_ai.spec import revit_twin
    dump = revit_twin.load(twin_index)
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    groups = Counter()
    for f in spec["floors"]:
        for o in f["openings"]:
            if o.get("kind") == "window":
                groups[(o["w_m"], o["h_m"], o.get("panes"), o.get("glass_w"), o.get("glass_h"), o.get("level_to"))] += 1
    out = []
    for n, ((w, h, panes, gw, gh, level_to), count) in enumerate(sorted(groups.items(), key=lambda kv: -kv[1]), 1):
        layout_m = None
        for o in dump["openings"]:
            if (o["kind"] == "window" and o.get("panes") == panes and abs(math.dist(o["p0"], o["p1"]) - w) <= 0.01
                    and abs((o["z1"] - o["z0"]) - h) <= 0.01 and o.get("glass")):
                ux, uy = [(b - a) / math.dist(o["p0"], o["p1"]) for a, b in zip(o["p0"], o["p1"])]
                along = [sorted(((g[0] - o["p0"][0]) * ux + (g[1] - o["p0"][1]) * uy,
                                 (g[2] - o["p0"][0]) * ux + (g[3] - o["p0"][1]) * uy)) for g in o["glass"]]
                layout_m = sorted([a[0], g[4] - o["z0"], a[1], g[5] - o["z0"]] for a, g in zip(along, o["glass"]))
                break
        out.append(entry(
            f"KPP1-W{n:02d}", None, "window", w, h, layout_m,
            source={"object": "tec26-kpp1", "file": f"{Path(spec_path).as_posix()} (spec v0.3, Revit path)",
                    "revit": "ADSK_Витраж_Без разрезки_Импосты 50х100 frame wall with MEP_Окно AGS68 windows",
                    "occurrences": count, "glass_m": [gw, gh], "across_level": level_to},
            note="кандидат из KPP1-spec: проём = стена-рамка (дыра с рамой), стекло = окна AGS68"))
    return out


def confirm(types, confirmations):
    """Apply the user's decisions (status, name) to the built entries; an unknown id is an error."""
    by_id = {t["id"]: t for t in types}
    for d in confirmations["decisions"]:
        if d["id"] not in by_id:
            raise SystemExit(f"confirmation for unknown type {d['id']}")
        t = by_id[d["id"]]
        t["status"] = d["status"]
        if d.get("name"):
            t["name"] = d["name"]
        t["decision"] = {"by": d["by"], "date": d["date"], **({"note": d["note"]} if d.get("note") else {})}
    return types


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--type-map", type=Path, required=True)
    ap.add_argument("--library-v001", type=Path, required=True)
    ap.add_argument("--kpp1-twin", type=Path, required=True)
    ap.add_argument("--kpp1-spec", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--max-source", type=Path, action="append", default=[],
                    help="a 3ds Max window source (library/windows/sources/*.json); repeatable")
    ap.add_argument("--confirmations", type=Path, default=Path(__file__).resolve().parents[2] / "library" / "windows" / "confirmations.json")
    args = ap.parse_args(argv)
    if not args.confirmations.exists():                 # never drop the user's decisions silently (PR #42 review 1)
        raise SystemExit(f"confirmations file not found: {args.confirmations}")
    max_sources, prefixes = [], set()
    for src in args.max_source:                           # one id space per source (PR #43 review 1)
        source = json.loads(src.read_text(encoding="utf-8"))
        if source["id_prefix"] in prefixes:
            raise SystemExit(f"max source given twice or prefix {source['id_prefix']} reused: {src}")
        prefixes.add(source["id_prefix"])
        max_sources.append((src, source))
    types = (sosh(json.loads(args.type_map.read_text(encoding="utf-8")),
                  json.loads(args.library_v001.read_text(encoding="utf-8")))
             + kpp1(args.kpp1_twin, args.kpp1_spec))
    for src, source in max_sources:
        types += max_types(source, src)
    types = dedupe(types)
    types = confirm(types, json.loads(args.confirmations.read_text(encoding="utf-8")))
    doc = {"schema": "window-types/1",
           "note": "Machine-readable window type list (HARNESS_PLAN §6, issue #4). An entry is unconfirmed until "
                   "the user confirms and names it (library/windows/confirmations.json); handing is null; sashes are not in "
                   "the sources. Sizes are the rough opening with its frame (spec v0.3); panes_m are glass "
                   "rectangles [x0, z0, x1, z1] from the bottom left of the opening. Built by "
                   "tools/library/build_window_types.py.",
           "types": types}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"window types: {len(types)} ({sum(t['status'] == 'confirmed' for t in types)} confirmed, "
          f"{sum(not t['typed'] for t in types)} not typed) -> {args.output}")


if __name__ == "__main__":
    main()

"""Derive the exterior openings spec of KPP1 from the Revit export (sidecars + object dumps).

Usage: py -3 extract_openings.py <source_dir> <census_dir>   -> <census_dir>/openings_spec.json

Facade frames (u along the facade, z up, d = depth inward from the outer cassette plane):
  S: y = -0.33, u = x     N: y = 11.33, u = x     W: x = -0.33, u = y     E: x = 27.33, u = y
Rects are [u0, u1, z0, z1] in metres (Revit internal coordinates).
"""
import json, os, re, sys

FT = 0.3048
FEATURE_IDS = {1832606}  # north vertical fin feature: listed under "features", modeled with decor (stage 4)


def facade_of(lo, hi):
    if hi[1] < 0.6 and lo[1] < 0: return "S"
    if lo[1] > 10.4: return "N"
    if hi[0] < 0.6 and lo[0] < 0: return "W"
    if lo[0] > 26.4: return "E"
    return None


def rect(lo, hi, f):
    a = 1 if f in "WE" else 0
    return [round(lo[a], 3), round(hi[a], 3), round(lo[2], 3), round(hi[2], 3)]  # 1 mm: drops 0.1 mm Revit noise


def inside(r, R, tol=0.012):
    return r[0] >= R[0] - tol and r[1] <= R[1] + tol and r[2] >= R[2] - tol and r[3] <= R[3] + tol


def main(src, cen):
    side = json.load(open(os.path.join(src, "curtain.export.json"), encoding="utf-8-sig"))
    inst = [i for t in side["types"] for i in t["instances"] if i.get("boundingBox")]
    bb = lambda i: ([i["boundingBox"]["min"][k] * FT for k in "xyz"], [i["boundingBox"]["max"][k] * FT for k in "xyz"])
    objs = []
    for g in ("curtain", "openings"):
        for o in json.load(open(os.path.join(cen, g + ".objects.json"), encoding="utf-8")):
            o["kind"] = re.sub(r"(_[0-9a-f]{7}(\.\d+)?| \[\d+\])$", "", o["name"])
            objs.append(o)

    spec = {f: {"surrounds": [], "doors": [], "portals": [], "features": [], "grilles": []} for f in "SNWE"}
    hosts = [i for i in inst if i["type"].startswith("ADSK_Витраж")]
    for s in inst:
        lo, hi = bb(s)
        f = facade_of(lo, hi)
        if f is None:
            continue
        R = rect(lo, hi, f)
        if s["type"].startswith("ADSK_Обрамление порталов"):
            spec[f]["portals"].append({"id": s["elementId"], "rect": R})
        elif s["type"].startswith("ADSK_Обрамление витражей"):
            mine = [o for o in objs if facade_of(o["min"], o["max"]) == f and inside(rect(o["min"], o["max"], f), R)]
            bays = []
            for h in hosts:
                hl, hh = bb(h)
                if facade_of(hl, hh) != f or not inside(rect(hl, hh, f), R):
                    continue
                B = rect(hl, hh, f)
                ins = [o for o in mine if inside(rect(o["min"], o["max"], f), B)]
                bays.append({"id": h["elementId"], "rect": B,
                             "windows": [rect(o["min"], o["max"], f) for o in ins if o["kind"].startswith("MEP_Окно")],
                             "glass": [rect(o["min"], o["max"], f) for o in ins if "Cтеклопак" in o["kind"]]})
            spec[f]["features" if s["elementId"] in FEATURE_IDS else "surrounds"].append({
                "id": s["elementId"], "rect": R, "bays": bays,
                "mullions": [rect(o["min"], o["max"], f) for o in mine if o["kind"].startswith("Прямоугольный импост 200х75")]})

    for o in objs:
        if o["kind"].startswith("MEP_Веза_Р50"):  # vent grilles: ~1 cm proud of the cassettes -> finish only
            f = facade_of(o["min"], o["max"])
            spec[f]["grilles"].append(rect(o["min"], o["max"], f))
        if not o["kind"].startswith("ADSK_Дверь_"):
            continue
        f = facade_of(o["min"], o["max"])
        if f is None:
            continue
        r = rect(o["min"], o["max"], f)
        spec[f]["doors"].append({"name": o["kind"], "rect": [r[0], r[1], r[2], round(r[2] + 2.1, 3)],
                                 "double": "Двупольная" in o["kind"]})
    json.dump(spec, open(os.path.join(cen, "openings_spec.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for f, v in spec.items():
        print(f, {k: len(x) for k, x in v.items()},
              "bays", sum(len(s["bays"]) for s in v["surrounds"]),
              "windows", sum(len(b["windows"]) for s in v["surrounds"] for b in s["bays"]),
              "glass", sum(len(b["glass"]) for s in v["surrounds"] for b in s["bays"]))


if __name__ == "__main__":
    main(*sys.argv[1:3])

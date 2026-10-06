"""Match Blender-imported FBX objects (names truncated) to Revit sidecar elements by bounding box.

Writes census-v001/<group>.match.json: object name -> elementId, type, category, materials, distance.
"""
import json, sys, os
FT = 0.3048
src, cen = sys.argv[1:3]
def side(g):
    d = json.load(open(os.path.join(src, g + ".export.json"), encoding="utf-8-sig"))
    out = []
    for t in d["types"]:
        for i in t["instances"]:
            b = i.get("boundingBox")
            if not b: continue
            out.append({"id": i["elementId"], "type": i["type"], "family": i["family"], "category": i["category"],
                        "mats": [m["name"] for m in i.get("materials", [])], "host": i.get("host"),
                        "min": [b["min"][k] * FT for k in "xyz"], "max": [b["max"][k] * FT for k in "xyz"]})
    return out
summary = {}
for f in sorted(os.listdir(cen)):
    if not f.endswith(".objects.json"): continue
    g = f[:-13]; objs = json.load(open(os.path.join(cen, f), encoding="utf-8")); els = side(g)
    off = [0.0, 0.0, 0.0]  # FBX world = Revit internal coordinates in metres (verified on floors/roof)
    res, used = {}, set()
    for o in objs:
        best = min(els, key=lambda e: sum(abs(e["min"][k] - off[k] - o["min"][k]) + abs(e["max"][k] - off[k] - o["max"][k]) for k in range(3)))
        dist = sum(abs(best["min"][k] - off[k] - o["min"][k]) + abs(best["max"][k] - off[k] - o["max"][k]) for k in range(3))
        res[o["name"]] = {**{k: best[k] for k in ("id", "type", "family", "category", "mats", "host")}, "dist": round(dist, 4)}
        used.add(best["id"])
    json.dump({"offset_m": off, "objects": res}, open(os.path.join(cen, g + ".match.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    ds = sorted(r["dist"] for r in res.values())
    summary[g] = {"objs": len(objs), "els": len(els), "uniqueMatched": len(used), "off": [round(x, 3) for x in off],
                  "dist_med": ds[len(ds) // 2] if ds else None, "dist_max": ds[-1] if ds else None, "bad(>0.05)": sum(d > 0.05 for d in ds)}
for k, v in summary.items(): print(k, v)

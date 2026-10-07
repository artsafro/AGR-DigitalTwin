"""Copy of jobs/KPP1/scripts/package_vpm.py (accepted case KPP1 v005) for PSU275: spec = jobs/PSU275/vpm_textures.json,
H_RELIEF = 169.65 (0.000 from the S1 site plan). Original description:
Assemble the KPP1 VPM OKS package: FBX + external PNG set + GeoJSON -> SM_<Address>.zip.

Usage: py -3 package_vpm.py <package_dir> <textures_dir> [--no-geojson]
--no-geojson: user decision 2026-10-07 (GeoJSON, coordinates and district code deferred) -> ZIP holds
FBX + PNG only; the GeoJSON checks are reported as excluded, not passed.
<package_dir> holds SM_<Address>.fbx (export_vpm.py); its parent holds export_meta.json and
thumbnail_256.jpg. GeoJSON follows reg App.3 (p.51-55): literal ObjectFeature, exact key order.
Values are written only when the source supports them; unknown OKS values stay "" (numbers) or
null (coordinates) and are listed in package_report.json as blockers - never invented
(docs/domain/conflicts.md #2, ADR: review, never invent).
"""
import base64, json, os, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
pkg, tex = sys.argv[1:3]
NO_GEOJSON = "--no-geojson" in sys.argv
meta = json.load(open(os.path.join(pkg, "..", "export_meta.json")))
spec = json.load(open(os.path.join(HERE, "..", "vpm_textures.json"), encoding="utf-8"))
A = meta["address"]
stem = f"SM_{A}"

for f in sorted(os.listdir(tex)):
    if f.startswith(f"T_{A}_") and f.endswith(".png"):
        shutil.copy2(os.path.join(tex, f), os.path.join(pkg, f))

H_RELIEF = 169.65  # PSU275: 0.000 = 169.65 (S1 site plan mark, docs/sources/psu275.md)
h_otn = meta["h_otn_model_max_z_m"]
img = base64.b64encode(open(meta["thumbnail"], "rb").read()).decode("ascii")
props = {
    "address": "", "okrug": "", "rajon": "",
    "name": "Центральная проходная",  # Revit Project Information: Building Name
    "developer": "", "designer": "", "cadNum": "", "FNO_code": "", "FNO_name": "", "ZU_area": "",
    "h_relief": H_RELIEF, "h_otn": h_otn, "h_abs": round(H_RELIEF + h_otn, 2),
    "s_obsh": "", "s_naz": "", "s_podz": "", "spp_gns": "", "act_AGR": "",
    "imageBase64": img, "other": "",
}
glasses = {f"M_{A}_MainGlass_1": {  # Revit: ADSK_Стекло_Прозрачное бесцветное (clear); values are proposals
    "color_RGB": {"Red": 225, "Green": 235, "Blue": 235},
    "transparency": 0.2, "refraction": 1.5, "roughness": 0.05, "metallicity": 0.0}}
geo = {"type": "FeatureCollection", "features": [{
    "type": "ObjectFeature", "properties": props,
    "geometry": {"type": "Point", "coordinates": [None, None]},
    "Glasses": [glasses]}]}  # list with one object keyed by glass material (reg p.51-52 example)
gpath = os.path.join(pkg, f"{stem}.geojson")
if not NO_GEOJSON:
    json.dump(geo, open(gpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
elif os.path.exists(gpath):
    os.remove(gpath)

zpath = os.path.join(pkg, "..", f"{stem}.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(os.listdir(pkg)):
        z.write(os.path.join(pkg, f), f)

blockers = ([k for k, v in props.items() if v == "" and k != "other"] + ["geometry.coordinates (MSK-77)"]
            if not NO_GEOJSON else ["GeoJSON deferred by the user (2026-10-07)"])
report = {"zip": os.path.abspath(zpath), "zip_bytes": os.path.getsize(zpath),
          "files": sorted(os.listdir(pkg)), "geojson_blockers_unknown_in_source": blockers,
          "geojson_proposals": ["Glasses values (colour/transparency/refraction/roughness/metallicity)"],
          "address_placeholder": A}
json.dump(report, open(os.path.join(pkg, "..", "package_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in report.items() if k != "files"}, ensure_ascii=False, indent=1), len(report["files"]), "files")

#!/usr/bin/env bash
# Full KPP1 run: stage 6 build -> master QA -> VPM export/package -> NPM atlas/export/package -> SINTEZ.
# Textures (make_textures.py) and the Revit export/census are separate, slower steps.
# Usage: run_all.sh <version_tag e.g. v002>
set -e
J="$(cd "$(dirname "$0")/.." && pwd)"
V="${1:?version tag}"
BL="/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
O="$J/outputs"
bash "$J/scripts/run_stage.sh" 6
"$BL" --background --factory-startup "$O/build-v001/KPP1_VPM_v006_ucx.blend" --python "$J/scripts/qa_master.py" -- "$O/build-v001/qa_master_v006.json" 2>&1 | grep -E "QA-"
P="$O/package-vpm-$V"; rm -rf "$P"; mkdir -p "$P/SM_Kpp_1"
"$BL" --background --factory-startup --python "$J/scripts/export_vpm.py" -- "$O/build-v001/KPP1_VPM_v006_ucx.blend" "$P/SM_Kpp_1" 2>&1 | grep -E "^EXPORT|Traceback"
PYTHONIOENCODING=utf-8 py -3 "$J/scripts/package_vpm.py" "$P/SM_Kpp_1" "$O/textures-v001" --no-geojson > /dev/null
N="$O/package-npm-$V"; rm -rf "$N"; mkdir -p "$N/0000_Kpp_1"
[ -f "$O/npm-textures-v001/npm_atlas.json" ] || py -3 "$J/scripts/make_npm_atlas.py" "$O/npm-textures-v001"
"$BL" --background --factory-startup --python "$J/scripts/export_npm.py" -- "$O/build-v001/KPP1_VPM_v006_ucx.blend" "$O/npm-textures-v001" "$N/0000_Kpp_1" 2>&1 | grep -E "^EXPORT|Traceback"
(cd "$N/0000_Kpp_1" && py -3 -c "import zipfile; z=zipfile.ZipFile('../0000_Kpp_1.zip','w',zipfile.ZIP_DEFLATED); z.write('0000_Kpp_1_01.fbx'); z.close()")
S="$O/sintez-$V"; rm -rf "$S"; mkdir -p "$S"
cp "$P/SM_Kpp_1.zip" "$N/0000_Kpp_1.zip" "$S/"
"$BL" --background --factory-startup --python "$J/scripts/run_agr_checker.py" -- "$S" "$S/agr_check.json" > "$S/checker_log.txt" 2>&1
grep -E "AGR-SUMMARY" "$S/checker_log.txt"

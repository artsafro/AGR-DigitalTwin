#!/usr/bin/env bash
# Full KPP1 run: stage 6 build -> master QA -> VPM -> fresh NPM atlas -> SINTEZ.
# Source/census/textures-v001 are read-only inputs prepared separately.
# Usage: run_all.sh <new version_tag e.g. v002>. Existing versions are refused.
set -euo pipefail
J="$(cd "$(dirname "$0")/.." && pwd)"
V="${1:?version tag}"
BL="/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
O="$J/outputs"
# Reserve ALL outputs before building. No rm, overwrite, or old atlas cache.
py -3 "$J/scripts/export_safety.py" "$O" "$V"
B="$O/build-$V"
P="$O/package-vpm-$V"
N="$O/package-npm-$V"
A="$O/npm-textures-$V"
S="$O/sintez-$V"
bash "$J/scripts/run_stage.sh" 6 "build-$V"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 "$B/KPP1_VPM_v006_ucx.blend" --python "$J/scripts/qa_master.py" -- "$B/qa_master_v006.json" 2>&1 | grep -E "QA-"
mkdir "$P/SM_Kpp_1"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/scripts/export_vpm.py" -- "$B/KPP1_VPM_v006_ucx.blend" "$P/SM_Kpp_1" 2>&1 | grep -E "^EXPORT|Traceback"
PYTHONIOENCODING=utf-8 py -3 "$J/scripts/package_vpm.py" "$P/SM_Kpp_1" "$O/textures-v001" --no-geojson > /dev/null
mkdir "$N/0000_Kpp_1"
py -3 "$J/scripts/make_npm_atlas.py" "$A"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/scripts/export_npm.py" -- "$B/KPP1_VPM_v006_ucx.blend" "$A" "$N/0000_Kpp_1" 2>&1 | grep -E "^EXPORT|Traceback"
(cd "$N/0000_Kpp_1" && py -3 -c "import zipfile; z=zipfile.ZipFile('../0000_Kpp_1.zip','w',zipfile.ZIP_DEFLATED); z.write('0000_Kpp_1_01.fbx'); z.close()")
cp "$P/SM_Kpp_1.zip" "$N/0000_Kpp_1.zip" "$S/"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/scripts/run_agr_checker.py" -- "$S" "$S/agr_check.json" > "$S/checker_log.txt" 2>&1
grep -E "AGR-SUMMARY" "$S/checker_log.txt"

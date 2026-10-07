#!/usr/bin/env bash
# Full KPP1 run: stage 6 build -> master/overlap QA -> VPM -> fresh NPM atlas -> SINTEZ -> quad review exports.
# Source/census/textures-v001 are read-only inputs prepared separately.
# Usage: run_all.sh <new version_tag e.g. v002>. Existing versions are refused.
set -euo pipefail
J="$(cd "$(dirname "$0")/.." && pwd)"
V="${1:?version tag}"
BL="/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
O="$J/outputs"
# Reserve ALL outputs before building. No rm, overwrite, or old atlas cache.
[ ! -e "$O/max-$V" ] || { echo "Version already has review exports: $O/max-$V" >&2; exit 1; }
py -3 "$J/scripts/export_safety.py" "$O" "$V"
B="$O/build-$V"
P="$O/package-vpm-$V"
N="$O/package-npm-$V"
A="$O/npm-textures-$V"
S="$O/sintez-$V"
X="$O/max-$V"
mkdir "$X"
bash "$J/scripts/run_stage.sh" 6 "build-$V"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 "$B/KPP1_VPM_v006_ucx.blend" --python "$J/scripts/qa_master.py" -- "$B/qa_master_v006.json" 2>&1 | grep -E "QA-"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 "$B/KPP1_VPM_v006_ucx.blend" --python "$J/scripts/qa_overlap.py" -- "$B/overlap_v006.json" SM_Kpp_1_Main SM_Kpp_1_MainGlass 2>&1 | grep -E "^OVERLAP"
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
# quad (untriangulated) review exports for 3ds Max; review copies only, never delivery
mkdir -p "$X/vpm/SM_Kpp_1" "$X/npm/0000_Kpp_1"
KEEP_QUADS=1 "$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/scripts/export_vpm.py" -- "$B/KPP1_VPM_v006_ucx.blend" "$X/vpm/SM_Kpp_1" 2>&1 | grep -c "^EXPORT"
KEEP_QUADS=1 "$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/scripts/export_npm.py" -- "$B/KPP1_VPM_v006_ucx.blend" "$A" "$X/npm/0000_Kpp_1" 2>&1 | grep -c "^EXPORT"

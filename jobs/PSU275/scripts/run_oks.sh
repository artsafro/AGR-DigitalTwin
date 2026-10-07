#!/usr/bin/env bash
# PSU275 extra OKS run (chimney / ducts / transformer / tanks), same chain as run_all.sh without glass:
# textures -> stage5+UCX (vpm_stage5_oks.py) -> QA (master, overlap) -> VPM export + readback -> package
# -> NPM atlas + export -> SINTEZ AGR Checker.
# Usage: run_oks.sh <key: chimney|ducts|transformer|tanks> <version tag> <pieces dir from build_oks_extras.py>
# VPM: own package SM_Psu_<N>.zip (own pivot). NPM: one FBX 0000_Psu_1_<NN>.fbx (objects SM_Psu_1_<NNN>_Main,
# index N = the VPM address number) with the main building pivot NPM_PIVOT (default 0.305,0.0 = package-npm-v006),
# collected into one NPM ZIP by run_npm_combined.sh (SINTEZ wants 2-21 FBX per NPM ZIP).
# Spec: jobs/PSU275/oks/<key>/vpm_textures.json (env PSU275_SPEC for the shared PSU275 scripts).
# Existing versions are refused (no overwrite).
set -euo pipefail
J="$(cd "$(dirname "$0")/.." && pwd)"
K="${1:?key}"; V="${2:?version tag}"; PIECES="${3:?pieces dir}"
BL="/c/Program Files/Blender Foundation/Blender 4.4/blender.exe"
BL51="/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
O="$J/outputs/oks-$K-$V"
[ ! -e "$O" ] || { echo "exists: $O" >&2; exit 1; }
export PSU275_SPEC="$(cygpath -w "$J/oks/$K/vpm_textures.json")"
T="$O/textures"; D="$O/build"; P="$O/package-vpm"; A="$O/npm-textures"; N="$O/package-npm"; S="$O/sintez"
ADDR=$(py -3 -c "import json,os;print(json.load(open(os.environ['PSU275_SPEC'],encoding='utf-8'))['address'])")
uv run --quiet --with pillow python "$J/scripts/make_textures_psu275.py" "$(cygpath -w "$T")" > /dev/null
"$BL" --background --factory-startup --python-exit-code 1 --python "$J/scripts/vpm_stage5_oks.py" -- "$PSU275_SPEC" "$T" "$PIECES/$K.json" "$D/PSU275_${K}_stage6_ucx.blend" 2>&1 | grep -E "^STAGE5|Traceback|Error"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 "$D/PSU275_${K}_stage6_ucx.blend" --python "$J/scripts/qa_master_psu275.py" -- "$D/qa_master.json" 2>&1 | grep -E "^QA-"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 "$D/PSU275_${K}_stage6_ucx.blend" --python "$J/../KPP1/scripts/qa_overlap.py" -- "$D/overlap.json" "SM_${ADDR}_Main" 2>&1 | grep -E "^OVERLAP"
mkdir -p "$P/SM_$ADDR"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/scripts/export_vpm_psu275.py" -- "$D/PSU275_${K}_stage6_ucx.blend" "$P/SM_$ADDR" 2>&1 | grep -E "^EXPORT|Traceback"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/../KPP1/scripts/qa_master.py" -- "$P/readback_qa.json" "$P/SM_$ADDR/SM_$ADDR.fbx" 2>&1 | grep -E "^QA-NORMALS|Traceback"
PYTHONIOENCODING=utf-8 py -3 "$J/scripts/package_vpm.py" "$P/SM_$ADDR" "$T" --no-geojson > /dev/null
IDX="${ADDR#Psu_}"
export PSU275_NPM_ADDRESS="Psu_1" PSU275_NPM_INDEX="$IDX" PSU275_NPM_PIVOT="${NPM_PIVOT:-0.305,0.0}"
uv run --quiet --with pillow python "$J/scripts/make_npm_atlas.py" "$(cygpath -w "$A")" > /dev/null
mkdir -p "$N"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/scripts/export_npm.py" -- "$D/PSU275_${K}_stage6_ucx.blend" "$A" "$N" 2>&1 | grep -E "^EXPORT|Traceback"
mkdir -p "$S"; cp "$P/SM_$ADDR.zip" "$S/"
"$BL51" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/../KPP1/scripts/run_agr_checker.py" -- "$S" "$S/agr_check.json" > "$S/checker_log.txt" 2>&1
grep -E "AGR-SUMMARY" "$S/checker_log.txt"

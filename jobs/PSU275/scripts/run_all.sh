#!/usr/bin/env bash
# PSU275 VPM + NPM run after the BODY/ROOF/PORTALS/WINDOWS inputs (pattern: jobs/KPP1/scripts/run_all.sh, KPP1 v005).
# stage5 (Main/Glass, seal, texel cuts, UDIM UV, materials) -> UCX -> QA (master, overlap) -> VPM export + readback
# -> package -> NPM atlas + export -> SINTEZ AGR Checker.
# Usage: run_all.sh <new version tag, e.g. v002> <shell_dir> <surface_dir> <roof-wells.json> <portals.json> <windows-vpm.json> <textures_dir>
# Optional: EXTRAS="<pieces.json> ..." (e.g. stairs) are added to Main with their finishes and explicit UVs.
# Existing versions are refused (no overwrite).
set -euo pipefail
J="$(cd "$(dirname "$0")/.." && pwd)"
V="${1:?version tag}"; SHELL_DIR="$2"; SURF="$3"; ROOF="$4"; PORT="$5"; WIN="$6"; TEX="$7"
BL="/c/Program Files/Blender Foundation/Blender 4.4/blender.exe"
BL51="/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"   # SINTEZ extension lives in 5.1
O="$J/outputs"
D="$O/build-$V"; P="$O/package-vpm-$V"; A="$O/npm-textures-$V"; N="$O/package-npm-$V"; S="$O/sintez-$V"
for d in "$D" "$P" "$A" "$N" "$S"; do [ ! -e "$d" ] || { echo "exists: $d" >&2; exit 1; }; done
ADDR=$(py -3 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8'))['address'])" "$(cygpath -w "$J/vpm_textures.json")")
"$BL" --background --factory-startup --python-exit-code 1 --python "$J/scripts/vpm_stage5.py" -- "$SHELL_DIR" "$SURF" "$ROOF" "$PORT" "$WIN" "$TEX" "$D/PSU275_VPM_stage5.blend" ${EXTRAS:-} 2>&1 | grep -E "^STAGE5|Traceback"
"$BL" --background --factory-startup "$D/PSU275_VPM_stage5.blend" --python-exit-code 1 --python "$J/scripts/vpm_ucx.py" -- "$J/masses.json" "$PORT" "$D/PSU275_VPM_stage6_ucx.blend" 2>&1 | grep -E "^UCX|Traceback"
PSU275_MASSES="$J/masses.json" "$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 "$D/PSU275_VPM_stage6_ucx.blend" --python "$J/scripts/qa_master_psu275.py" -- "$D/qa_master.json" 2>&1 | grep -E "^QA-"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 "$D/PSU275_VPM_stage6_ucx.blend" --python "$J/../KPP1/scripts/qa_overlap.py" -- "$D/overlap.json" "SM_${ADDR}_Main" "SM_${ADDR}_MainGlass" 2>&1 | grep -E "^OVERLAP"
mkdir -p "$P/SM_$ADDR"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/../KPP1/scripts/export_vpm.py" -- "$D/PSU275_VPM_stage6_ucx.blend" "$P/SM_$ADDR" 2>&1 | grep -E "^EXPORT|Traceback"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/../KPP1/scripts/qa_master.py" -- "$P/readback_qa.json" "$P/SM_$ADDR/SM_$ADDR.fbx" 2>&1 | grep -E "^QA-NORMALS|Traceback"
PYTHONIOENCODING=utf-8 py -3 "$J/scripts/package_vpm.py" "$P/SM_$ADDR" "$TEX" --no-geojson > /dev/null
uv run --quiet --with pillow python "$J/scripts/make_npm_atlas.py" "$A" > /dev/null
mkdir -p "$N/0000_$ADDR"
"$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/scripts/export_npm.py" -- "$D/PSU275_VPM_stage6_ucx.blend" "$A" "$N/0000_$ADDR" 2>&1 | grep -E "^EXPORT|Traceback"
(cd "$N/0000_$ADDR" && py -3 -c "import zipfile,glob; f=glob.glob('*.fbx')[0]; z=zipfile.ZipFile('../0000_$ADDR.zip','w',zipfile.ZIP_DEFLATED); z.write(f); z.close()")
mkdir -p "$S"; cp "$P/SM_$ADDR.zip" "$N/0000_$ADDR.zip" "$S/"
"$BL51" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/../KPP1/scripts/run_agr_checker.py" -- "$S" "$S/agr_check.json" > "$S/checker_log.txt" 2>&1
grep -E "AGR-SUMMARY" "$S/checker_log.txt"

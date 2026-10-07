#!/usr/bin/env bash
# PSU275 combined delivery check: one NPM ZIP 0000_Psu_1.zip with the main building FBX (_01) and the extra OKS
# FBX (_02.._05, run_oks.sh, same pivot), plus every VPM SM_Psu_<N>.zip, checked together by SINTEZ AGR Checker.
# Usage: run_npm_combined.sh <version tag> <main package-npm dir> <main package-vpm zip> <extra oks dir>...
# Existing versions are refused (no overwrite).
set -euo pipefail
J="$(cd "$(dirname "$0")/.." && pwd)"
V="${1:?version tag}"; MAIN_NPM="$2"; MAIN_VPM="$3"; shift 3
BL51="/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
S="$J/outputs/delivery-$V"
[ ! -e "$S" ] || { echo "exists: $S" >&2; exit 1; }
mkdir -p "$S/npm"
cp "$MAIN_NPM"/0000_Psu_1/0000_Psu_1_01.fbx "$S/npm/"
cp "$MAIN_VPM" "$S/"
for d in "$@"; do cp "$d"/package-npm/0000_Psu_1_*.fbx "$S/npm/"; cp "$d"/package-vpm/SM_Psu_*.zip "$S/"; done
(cd "$S/npm" && py -3 -c "import zipfile,glob; z=zipfile.ZipFile('../0000_Psu_1.zip','w',zipfile.ZIP_DEFLATED); [z.write(f) for f in sorted(glob.glob('*.fbx'))]; z.close(); print('NPM-ZIP', sorted(glob.glob('*.fbx')))")
mkdir -p "$S/check"; cp "$S"/*.zip "$S/check/"
"$BL51" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/../KPP1/scripts/run_agr_checker.py" -- "$S/check" "$S/agr_check.json" > "$S/checker_log.txt" 2>&1
grep -E "AGR-SUMMARY" "$S/checker_log.txt"
ls -la "$S"/*.zip

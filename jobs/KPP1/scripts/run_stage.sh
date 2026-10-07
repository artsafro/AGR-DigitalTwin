#!/usr/bin/env bash
# Build one KPP1 stage headless: run_stage.sh <stage> [build_dir_name]
J="$(cd "$(dirname "$0")/.." && pwd)"
BL="/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
OUT="$J/outputs/${2:-build-v001}"
mkdir -p "$OUT"
"$BL" --background --factory-startup --python "$J/scripts/build_kpp1.py" -- \
  "$J/outputs/source-v001" "$J/outputs/census-v001" "$OUT" "$1" > "$OUT/stage$1.log" 2>&1
code=$?; grep -q "Traceback" "$OUT/stage$1.log" && code=1
echo "stage $1 exit $code"
grep -E "Traceback" -A14 "$OUT/stage$1.log" | grep -v "WARNING: mesh" | head -30
exit $code

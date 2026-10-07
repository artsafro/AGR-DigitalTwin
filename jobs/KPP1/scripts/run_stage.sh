#!/usr/bin/env bash
# Build one KPP1 stage headless: run_stage.sh <stage> [build_dir_name]
# run_all supplies a newly reserved version-specific build directory.
set -uo pipefail
J="$(cd "$(dirname "$0")/.." && pwd)"
BL="/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
STAGE="${1:?stage}"
BUILD="${2:-build-v001}"
[[ "$STAGE" =~ ^[1-6]$ ]] || { echo "stage must be 1..6" >&2; exit 1; }
[[ "$BUILD" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$ ]] || { echo "invalid build directory token" >&2; exit 1; }
OUT="$J/outputs/$BUILD"
mkdir -p "$OUT" || exit 1
if "$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$J/scripts/build_kpp1.py" -- \
  "$J/outputs/source-v001" "$J/outputs/census-v001" "$OUT" "$STAGE" > "$OUT/stage$STAGE.log" 2>&1; then
    code=0
else
    code=$?
fi
if grep -q "Traceback" "$OUT/stage$STAGE.log"; then code=1; fi
echo "stage $STAGE exit $code"
grep -E "Traceback" -A14 "$OUT/stage$STAGE.log" | grep -v "WARNING: mesh" | head -30 || true
exit "$code"

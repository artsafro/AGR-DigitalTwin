#!/usr/bin/env bash
# Same-camera close-ups of fine details: Revit source FBX groups vs the master (render_preview.py FOCUS).
# Usage: compare_details.sh <master.blend> <out_dir>
J="$(cd "$(dirname "$0")/.." && pwd)"
BL="/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
M="$1"; OUT="$2"; mkdir -p "$OUT"
SRC_GROUPS="walls_ext,curtain,openings,floors,roofs,generic,stairs_rails_equip"
while read -r name focus views; do
  [ -z "$name" ] && continue
  FOCUS="$focus" VIEWS="$views" ZOOM=1.0 "$BL" --background --factory-startup --python "$J/scripts/render_preview.py" -- "$OUT/${name}_revit" "$J/outputs/source-v001" "$SRC_GROUPS" > /dev/null 2>&1
  TEX=1 FOCUS="$focus" VIEWS="$views" ZOOM=1.0 "$BL" --background --factory-startup --python "$J/scripts/render_preview.py" -- "$OUT/${name}_model" "$M" > /dev/null 2>&1
  echo "$name done"
done <<'LIST'
canopy_small 1.1,-1.0,3.0,3.5 SW
portal_S 9.5,-1.0,1.8,6 SW
grille_plinth 23.85,-0.6,2.15,2.5 SE
roof_shaft 12.2,8.4,8.9,4 SE
roof_items 6,4,8.2,9 SE
stair_east 29,5.2,4.5,10 SE,NE
feature_N 11.3,11.6,4.8,9 NE
window_bay 1.0,-0.6,5.7,3 SW
LIST

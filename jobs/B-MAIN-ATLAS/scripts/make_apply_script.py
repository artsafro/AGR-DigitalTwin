"""Generate a 2-space MAXScript UV/ID remap from an atlas manifest."""

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--manifest", type=Path, default=ROOT / "outputs/v001/atlas_manifest.json")
parser.add_argument("--input", type=Path, default=ROOT / "outputs/v001")
parser.add_argument("--node", default="B_Main")
parser.add_argument("--expected-scene", type=Path, default=Path("C:/Users/artsafro/Desktop/!3D viz/!А101/61_Golubinskaya/Alex_Golubinskaya_Buildigs.max"))
parser.add_argument("--output-scene", type=Path, default=ROOT / "outputs/v001/B_Main_Atlas_v001.max")
parser.add_argument("--script", type=Path, default=ROOT / "scripts/apply_atlas.ms")
args = parser.parse_args()
OUTPUT = args.manifest.parent
manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
with (args.input / "face_uv_before.csv").open(newline="", encoding="utf-8") as stream:
    face_count = sum(1 for _ in csv.DictReader(stream))


def max_path(path):
    return str(path.resolve()).replace("\\", "\\\\")


entries = []
for item in manifest["materials"]:
    old_id = item["old_id"]
    new_id = item["new_id"]
    x, y, w, h = item["rect_px"]
    # Atlas has 8 px gutter; Max UV V grows opposite to PNG pixel Y.
    left, right = x + 8, x + w - 8
    bottom, top = 2048 - (y + h - 8), 2048 - (y + 8)
    for group in item.get("uv_groups", [{"bounds": item["uv_bounds_before"]}]):
        u0, v0, u1, v1 = group["bounds"]
        values = [old_id, new_id, u0, v0, u1, v1,
                  left / 2048, bottom / 2048, right / 2048, top / 2048]
        entries.append("    #(" + ", ".join(f"{v:.10f}" if isinstance(v, float) else str(v) for v in values) + ")")

atlas = max_path(OUTPUT / manifest.get("atlas_file", "B_Main_1001_2048_RGBA.png"))
scene = max_path(args.output_scene)
expected_source = max_path(args.expected_scene)
script = f'''(
  local expectedSource = "{expected_source}"
  local outputPath = "{scene}"
  local atlasPath = "{atlas}"
  if (maxFilePath + maxFileName) != expectedSource do throw "Scene path changed; refusing to alter another scene."
  local obj = getNodeByName "{args.node}"
  if obj == undefined or (polyOp.getNumFaces obj) != {face_count} do throw "{args.node} changed; refusing remap."
  local entries = #(
{',\n'.join(entries)}
  )
  local remap = for i = 1 to 256 collect 0
  for entry in entries do remap[entry[1]] = entry[2]
  local owner = for i = 1 to (polyOp.getNumMapVerts obj 1) collect 0
  for faceIndex = 1 to (polyOp.getNumFaces obj) do (
    local oldId = polyOp.getFaceMatID obj faceIndex
    if oldId < 1 or oldId > 256 or remap[oldId] == 0 do throw ("Unexpected material ID: " + oldId as string)
    local tv = polyOp.getMapFace obj 1 faceIndex
    for vertexIndex in tv do (
      if owner[vertexIndex] != 0 and owner[vertexIndex] != oldId do throw "UV vertex shared by two material IDs."
      owner[vertexIndex] = oldId
    )
  )
  undo "{args.node} 2K atlas trial" on (
    for vertexIndex = 1 to owner.count where owner[vertexIndex] != 0 do (
      local oldUv = polyOp.getMapVert obj 1 vertexIndex
      local entry = undefined
      for candidate in entries where candidate[1] == owner[vertexIndex] do (
        if oldUv.x >= candidate[3] - 0.0001 and oldUv.x <= candidate[5] + 0.0001 and oldUv.y >= candidate[4] - 0.0001 and oldUv.y <= candidate[6] + 0.0001 do entry = candidate
      )
      if entry == undefined do throw "No UV mapping group for vertex."
      local newU = entry[7] + ((oldUv.x - entry[3]) / (entry[5] - entry[3])) * (entry[9] - entry[7])
      local newV = entry[8] + ((oldUv.y - entry[4]) / (entry[6] - entry[4])) * (entry[10] - entry[8])
      polyOp.setMapVert obj 1 vertexIndex [newU, newV, oldUv.z]
    )
    for faceIndex = 1 to (polyOp.getNumFaces obj) do (
      local oldId = polyOp.getFaceMatID obj faceIndex
      polyOp.setFaceMatID obj faceIndex remap[oldId]
    )
    local diffuse = bitmapTexture filename:atlasPath
    diffuse.alphaSource = 0
    local opacity = bitmapTexture filename:atlasPath
    opacity.alphaSource = 0
    opacity.monoOutput = 1
    local material = standardMaterial name:"{args.node}_ATLAS_1001"
    material.diffuseMap = diffuse
    material.opacityMap = opacity
    material.twoSided = false
    obj.material = material
    showTextureMap material diffuse true
    update obj
  )
  local invalid = 0
  for vertexIndex = 1 to owner.count where owner[vertexIndex] != 0 do (
    local uv = polyOp.getMapVert obj 1 vertexIndex
    if uv.x < 0 or uv.x > 1 or uv.y < 0 or uv.y > 1 do invalid += 1
  )
  if invalid != 0 do throw ("UVs outside 1001: " + invalid as string)
  saveMaxFile outputPath quiet:true
  outputPath
)
'''
target = args.script
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(script, encoding="utf-8")
print(target)

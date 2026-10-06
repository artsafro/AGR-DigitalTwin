(
  local expectedScene = "C:\\Users\\artsafro\\.AGR_Project\\jobs\\A-MAIN-ATLAS\\outputs\\v001\\A_Main_Atlas_v001.max"
  local outputPath = "C:\\Users\\artsafro\\.AGR_Project\\jobs\\A-MAIN-ATLAS\\outputs\\v002\\GLB_A_B_Atlases_v002.max"
  local atlasPath = "C:\\Users\\artsafro\\.AGR_Project\\jobs\\B-MAIN-ATLAS\\outputs\\v002\\B_Main_1001_2048_RGBA.png"
  if (maxFilePath + maxFileName) != expectedScene do throw "Unexpected scene; refusing B_Main atlas relink."
  if not (doesFileExist atlasPath) do throw "B_Main white atlas missing."
  local obj = getNodeByName "B_Main"
  if obj == undefined or obj.material.name != "B_Main_ATLAS_1001" do throw "Unexpected B_Main material."
  undo "B_Main white glass atlas" on (
    local diffuse = bitmapTexture filename:atlasPath
    diffuse.alphaSource = 0
    local opacity = bitmapTexture filename:atlasPath
    opacity.alphaSource = 0
    opacity.monoOutput = 1
    obj.material.diffuseMap = diffuse
    obj.material.opacityMap = opacity
    showTextureMap obj.material diffuse true
    update obj
  )
  saveMaxFile outputPath quiet:true
  outputPath
)

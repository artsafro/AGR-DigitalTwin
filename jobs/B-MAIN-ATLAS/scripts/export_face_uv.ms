(
  local nodeName = if ::atlasNodeName == undefined then "B_Main" else ::atlasNodeName
  local outputPath = if ::atlasFaceOutput == undefined then "C:\\Users\\artsafro\\.AGR_Project\\jobs\\B-MAIN-ATLAS\\outputs\\v001\\face_uv_before.csv" else ::atlasFaceOutput
  local obj = getNodeByName nodeName
  local stream = createFile outputPath
  format "face,id,u0,v0,u1,v1\n" to:stream
  for faceIndex = 1 to (polyOp.getNumFaces obj) do (
    local materialId = polyOp.getFaceMatID obj faceIndex
    local minU = 1e9
    local minV = 1e9
    local maxU = -1e9
    local maxV = -1e9
    for tv in (polyOp.getMapFace obj 1 faceIndex) do (
      local uv = polyOp.getMapVert obj 1 tv
      minU = amin minU uv.x
      minV = amin minV uv.y
      maxU = amax maxU uv.x
      maxV = amax maxV uv.y
    )
    format "%,%,%,%,%,%\n" faceIndex materialId minU minV maxU maxV to:stream
  )
  close stream
  outputPath
)

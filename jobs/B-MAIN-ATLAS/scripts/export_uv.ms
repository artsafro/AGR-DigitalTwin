(
  local nodeName = if ::atlasNodeName == undefined then "B_Main" else ::atlasNodeName
  local outputPath = if ::atlasUvOutput == undefined then "C:\\Users\\artsafro\\.AGR_Project\\jobs\\B-MAIN-ATLAS\\outputs\\v001\\uv_before.csv" else ::atlasUvOutput
  local obj = getNodeByName nodeName
  local owner = for i = 1 to (polyOp.getNumMapVerts obj 1) collect 0
  for faceIndex = 1 to (polyOp.getNumFaces obj) do (
    local materialId = polyOp.getFaceMatID obj faceIndex
    local tv = polyOp.getMapFace obj 1 faceIndex
    for vertexIndex in tv do owner[vertexIndex] = materialId
  )
  local stream = createFile outputPath
  format "vertex,id,u,v\n" to:stream
  for vertexIndex = 1 to owner.count where owner[vertexIndex] != 0 do (
    local uv = polyOp.getMapVert obj 1 vertexIndex
    format "%,%,%,%\n" vertexIndex owner[vertexIndex] uv.x uv.y to:stream
  )
  close stream
  outputPath
)

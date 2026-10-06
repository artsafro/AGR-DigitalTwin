(
  local expectedSource = "C:\\Users\\artsafro\\Desktop\\!3D viz\\!А101\\61_Golubinskaya\\Alex_Golubinskaya_Buildigs.max"
  local outputPath = "C:\\Users\\artsafro\\.AGR_Project\\jobs\\B-MAIN-ATLAS\\outputs\\v001\\B_Main_Atlas_v001.max"
  local atlasPath = "C:\\Users\\artsafro\\.AGR_Project\\jobs\\B-MAIN-ATLAS\\outputs\\v001\\B_Main_1001_2048_RGBA.png"
  if (maxFilePath + maxFileName) != expectedSource do throw "Scene path changed; refusing to alter another scene."
  local obj = getNodeByName "B_Main"
  if obj == undefined or (polyOp.getNumFaces obj) != 12156 do throw "B_Main changed; refusing remap."
  local entries = #(
    #(2, 1, 1.1551300000, 0.4268070000, 1.5095400000, 0.4381840000, 0.0039062500, 0.7539062500, 0.4960937500, 0.9960937500),
    #(6, 2, 1.3713800000, 0.7491330000, 1.4442000000, 0.7551690000, 0.0039062500, 0.3789062500, 0.2460937500, 0.4960937500),
    #(11, 3, 1.1673400000, 0.2979660000, 1.1970900000, 0.3157590000, 0.2539062500, 0.3789062500, 0.4960937500, 0.4960937500),
    #(20, 4, 1.6189400000, -1.1840400000, 1.7321600000, -1.1500600000, 0.5039062500, 0.5039062500, 0.7460937500, 0.9960937500),
    #(24, 5, 1.5796800000, 0.5650970000, 1.8220200000, 0.6631630000, 0.5039062500, 0.3789062500, 0.7460937500, 0.4960937500),
    #(27, 6, 0.8820970000, 1.4207600000, 0.9538870000, 1.4271300000, 0.0039062500, 0.2539062500, 0.2460937500, 0.3710937500),
    #(30, 7, -0.0234501000, 1.1676700000, 1.0482300000, 1.2611700000, 0.0039062500, 0.5039062500, 0.4960937500, 0.7460937500),
    #(31, 8, 1.2630200000, 0.5694390000, 1.4974500000, 0.6618290000, 0.7539062500, 0.3789062500, 0.9960937500, 0.4960937500),
    #(32, 9, 1.1682400000, 0.3292670000, 1.2039200000, 0.3469020000, 0.2539062500, 0.2539062500, 0.4960937500, 0.3710937500),
    #(50, 10, 1.4845300000, 0.8197950000, 1.5154700000, 1.0531300000, 0.7539062500, 0.5039062500, 0.9960937500, 0.9960937500),
    #(100, 11, 1.2640800000, 0.8543200000, 1.3150500000, 0.8656970000, 0.5039062500, 0.2539062500, 0.7460937500, 0.3710937500)
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
  undo "B_Main 2K atlas trial" on (
    for vertexIndex = 1 to owner.count where owner[vertexIndex] != 0 do (
      local oldUv = polyOp.getMapVert obj 1 vertexIndex
      local entry = undefined
      for candidate in entries where candidate[1] == owner[vertexIndex] do entry = candidate
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
    local material = standardMaterial name:"B_Main_ATLAS_1001"
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

(
  local expectedSource = "C:\\Users\\artsafro\\.AGR_Project\\jobs\\B-MAIN-ATLAS\\outputs\\v001\\B_Main_Atlas_v001.max"
  local outputPath = "C:\\Users\\artsafro\\.AGR_Project\\jobs\\A-MAIN-ATLAS\\outputs\\v001\\A_Main_Atlas_v001.max"
  local atlasPath = "C:\\Users\\artsafro\\.AGR_Project\\jobs\\A-MAIN-ATLAS\\outputs\\v001\\A_Main_1001_2048_RGBA.png"
  if (maxFilePath + maxFileName) != expectedSource do throw "Scene path changed; refusing to alter another scene."
  local obj = getNodeByName "A_Main"
  if obj == undefined or (polyOp.getNumFaces obj) != 12791 do throw "A_Main changed; refusing remap."
  local entries = #(
    #(2, 1, 1.1543900000, 0.4268070000, 1.5102800000, 0.4381840000, 0.0039062500, 0.7539062500, 0.4960937500, 0.9960937500),
    #(3, 2, 1.3306700000, 0.4268070000, 1.3340000000, 0.4381840000, 0.0039062500, 0.1289062500, 0.2460937500, 0.2460937500),
    #(6, 3, 1.4379100000, 0.7453010000, 1.5107300000, 0.7509900000, 0.0039062500, 0.3789062500, 0.2460937500, 0.4960937500),
    #(11, 4, 1.1673400000, 0.2979660000, 1.1970900000, 0.3157590000, 0.2539062500, 0.3789062500, 0.4960937500, 0.4960937500),
    #(15, 5, 1.4633400000, 0.7461540000, 1.4853000000, 0.7501360000, 0.2539062500, 0.1289062500, 0.4960937500, 0.2460937500),
    #(20, 6, 1.6189400000, -1.1840400000, 1.7321600000, -1.1500600000, 0.5039062500, 0.5039062500, 0.7460937500, 0.9960937500),
    #(20, 6, 2.3512500000, 0.7238990000, 2.3785600000, 0.7999930000, 0.5039062500, 0.5039062500, 0.7460937500, 0.9960937500),
    #(24, 7, 1.3586400000, 0.5625500000, 1.6009900000, 0.6606160000, 0.5039062500, 0.3789062500, 0.7460937500, 0.4960937500),
    #(27, 8, 0.8820970000, 1.4207600000, 0.9538870000, 1.4271300000, 0.0039062500, 0.2539062500, 0.2460937500, 0.3710937500),
    #(30, 9, -0.0234501000, 1.1676700000, 1.0482300000, 1.2611700000, 0.0039062500, 0.5039062500, 0.4960937500, 0.7460937500),
    #(31, 10, 1.3626000000, 0.5655600000, 1.5970300000, 0.6576050000, 0.7539062500, 0.3789062500, 0.9960937500, 0.4960937500),
    #(32, 11, 1.1682400000, 0.3292670000, 1.2039200000, 0.3469020000, 0.2539062500, 0.2539062500, 0.4960937500, 0.3710937500),
    #(50, 12, 1.4845300000, 0.8197950000, 1.5154700000, 1.0531300000, 0.7539062500, 0.5039062500, 0.9960937500, 0.9960937500),
    #(100, 13, 0.4753160000, 0.6193520000, 0.5262840000, 0.6307280000, 0.5039062500, 0.2539062500, 0.7460937500, 0.3710937500),
    #(100, 13, 1.4633400000, 0.7424570000, 1.4853000000, 0.7538340000, 0.5039062500, 0.2539062500, 0.7460937500, 0.3710937500)
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
  undo "A_Main 2K atlas trial" on (
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
    local material = standardMaterial name:"A_Main_ATLAS_1001"
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

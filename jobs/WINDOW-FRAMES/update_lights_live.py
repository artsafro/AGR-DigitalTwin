import bpy
from pathlib import Path
root=Path('C:/Users/artsafro/.AGR_Project/jobs/WINDOW-FRAMES/outputs')
o=bpy.data.objects['BoxLights_AllFrames_v001']
with bpy.data.libraries.load(str(root/'frames_box_lights_v002.blend'),link=False) as (a,b):
    b.meshes=['BoxLights_AllFrames_v001']
o.data=b.meshes[0]
o['planar_revision']='v002'
bpy.ops.wm.save_as_mainfile(filepath=str(root/'frames_box_lights_live_v002.blend'))
print('Planar revision applied and saved: '+bpy.data.filepath)

import bpy
from pathlib import Path
root=Path('C:/Users/artsafro/.AGR_Project/jobs/WINDOW-FRAMES/outputs')
assert len(bpy.data.objects['BoxLights_AllFrames_v001'].data.polygons)==1235
bpy.ops.wm.save_as_mainfile(filepath=str(root/'frames_box_lights_live_v001.blend'))
print(bpy.data.filepath)

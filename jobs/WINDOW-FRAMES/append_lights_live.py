import bpy,json
from pathlib import Path
root=Path('C:/Users/artsafro/.AGR_Project/jobs/WINDOW-FRAMES/outputs')
assert bpy.data.objects.get('BoxLights_AllFrames_v001') is None
assert len(bpy.data.objects['frames'].data.vertices)==3118
with bpy.data.libraries.load(str(root/'frames_box_lights_v001.blend'),link=False) as (a,b):
    b.objects=['BoxLights_AllFrames_v001']
o=b.objects[0]; bpy.context.scene.collection.objects.link(o)
for ob in bpy.context.selected_objects:ob.select_set(False)
o.select_set(True); bpy.context.view_layer.objects.active=o
bpy.ops.wm.save_as_mainfile(filepath=str(root/'frames_box_lights_live_v001.blend'))
print('Appended '+o.name+'; '+str(len(o.data.polygons))+' quads; source frames and sample retained.')

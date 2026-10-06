import bpy, json
from pathlib import Path
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/model-v002')
out.mkdir(parents=True,exist_ok=True)
assert not (out/'input.blend').exists()
print(json.dumps({'file':bpy.data.filepath,'dirty':bpy.data.is_dirty,'objects':len(bpy.context.scene.objects),'collections':[c.name for c in bpy.context.scene.collection.children]}))
assert {'LP','Revit','LP_old'} <= set(c.name for c in bpy.context.scene.collection.children)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'input.blend'),copy=True)

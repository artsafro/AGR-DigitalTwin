import bpy,json,hashlib
from pathlib import Path
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/model-v002')
new=[o for o in bpy.data.collections['LP'].objects if o.name.startswith('LP_Add_')]
assert len(new)==5 and sum(len(o.data.polygons) for o in new)==2710
assert all(o.library is None and o.data.library is None for o in new)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'LP_working-v002.blend'))
result={'file':bpy.data.filepath,'new_objects':[o.name for o in new],'quads':2710,'appended_data_local':True}
(out/'live-receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))

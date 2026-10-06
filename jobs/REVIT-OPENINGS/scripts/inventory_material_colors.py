import bpy,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(root/'outputs/body-v005/live-autosave-snapshot.blend'))
ob=bpy.data.objects['skolka']
print(json.dumps([{'slot':i,'name':m.name if m else None,
    'diffuse_rgba':list(m.diffuse_color) if m else None,
    'nodes':m.use_nodes if m else None} for i,m in enumerate(ob.data.materials)],ensure_ascii=False))

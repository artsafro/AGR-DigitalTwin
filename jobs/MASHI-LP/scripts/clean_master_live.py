import bpy,bmesh,json
from pathlib import Path
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001');removed={}
for o in bpy.data.collections['MASTER_Revit_v001'].objects:
 bm=bmesh.new();bm.from_mesh(o.data);seen=set();delete=[]
 for f in bm.faces:
  key=tuple(sorted(tuple(round(x,6) for x in v.co) for v in f.verts))
  if key in seen:delete.append(f)
  else:seen.add(key)
 removed[o.name]=len(delete)
 if delete:bmesh.ops.delete(bm,geom=delete,context='FACES_ONLY')
 loose=[e for e in bm.edges if not e.link_faces]
 if loose:bmesh.ops.delete(bm,geom=loose,context='EDGES')
 loose=[v for v in bm.verts if not v.link_edges]
 if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
 bm.to_mesh(o.data);o.data.update();bm.free()
path=out/'MASHI-comparison-trial-v002.blend';assert not path.exists()
bpy.ops.wm.save_as_mainfile(filepath=str(path))
(out/'live-clean.json').write_text(json.dumps(dict(file=bpy.data.filepath,duplicates_removed=removed),indent=2))
bpy.ops.screen.screenshot(filepath=str(out/'Blender-comparison.png'))
print('saved',bpy.data.filepath,'removed',removed)

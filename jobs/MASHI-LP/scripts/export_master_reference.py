import bpy,json
from pathlib import Path
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001')
rows=[]
for group in ['Revit','LP_old']:
 for o in bpy.data.collections[group].objects:
  if o.type!='MESH' or o.name=='MultiMat_1':continue
  me=o.data;me.calc_loop_triangles()
  rows.append(dict(group=group,name=o.name,vertices=[list(o.matrix_world@v.co) for v in me.vertices],faces=[list(p.vertices) for p in me.polygons],materials=[p.material_index for p in me.polygons]))
(out/'reference.json').write_text(json.dumps(rows))
print('exported',len(rows))

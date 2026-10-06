import bpy,json
from pathlib import Path
from collections import Counter
from mathutils import Vector
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001')
out.mkdir(exist_ok=True)
rows=[]
for group in ['Revit','LP_old']:
 for o in bpy.data.collections[group].objects:
  if o.type!='MESH':continue
  o.data.calc_loop_triangles()
  pts=[o.matrix_world@v.co for v in o.data.vertices]
  used=Counter(p.material_index for p in o.data.polygons)
  rows.append(dict(group=group,name=o.name,vertices=len(pts),polygons=len(o.data.polygons),bounds=[[min(p[a] for p in pts) for a in range(3)],[max(p[a] for p in pts) for a in range(3)]],matrix=[list(r) for r in o.matrix_world],materials=[dict(id=i,name=m.name if m else None,faces=used[i],color=list(m.diffuse_color) if m else None) for i,m in enumerate(o.data.materials)]))
(out/'inventory.json').write_text(json.dumps(rows,indent=2))
print(json.dumps({'active':bpy.data.filepath,'objects':len(bpy.data.objects),'rows':rows}))

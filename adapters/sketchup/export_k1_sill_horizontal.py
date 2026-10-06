"""Export horizontal polygons of the transition sill for coverage diagnosis."""
import bpy,json
from pathlib import Path
root=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(root/'GLB_K1_assembled_v022.blend'))
o=bpy.data.objects['TOP_<auto>26'];m=o.data
rows=[]
for p in m.polygons:
 if abs(p.normal.z)<.99:continue
 points=[list(o.matrix_world@m.vertices[i].co) for i in p.vertices]
 rows.append({'index':p.index,'z':sum(v[2] for v in points)/len(points),'normal_z':p.normal.z,'xy':[v[:2] for v in points]})
(root/'top-sill-horizontal-v022.json').write_text(json.dumps(rows),encoding='utf-8')
print('HORIZONTAL',len(rows))

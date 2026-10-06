"""Export horizontal typical-sill polygons at the highest repeated floor."""
import bpy,json
from pathlib import Path
root=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(root/'GLB_K1_assembled_v023.blend'))
o=bpy.data.objects['K1_TYPICAL_NPM'];m=o.data
rows=[]
for p in m.polygons:
 if m.materials[p.material_index].name!='M_Sill_Color' or p.normal.z<.99:continue
 pts=[list(m.vertices[i].co) for i in p.vertices];z=sum(q[2] for q in pts)/len(pts)
 if 63.15<z<63.3:rows.append({'index':p.index,'z':z,'xy':[q[:2] for q in pts]})
(root/'typical-sill-z63-v023.json').write_text(json.dumps(rows),encoding='utf-8')
print('SILL_TOP',len(rows))

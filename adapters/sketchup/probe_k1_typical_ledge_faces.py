"""Read-only inspected face records at the visible typical/top transition ledge."""
import bpy,json
from pathlib import Path
root=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(root/'GLB_K1_assembled_v023.blend'))
o=bpy.data.objects['K1_TYPICAL_NPM'];m=o.data
ids=[2280,3225,3226,18759,18765,18773,18774,17987,17989,17992,19842]
attr=m.attributes.get('npm_part_id')
rows=[]
for i in ids:
 p=m.polygons[i]
 rows.append({'face':i,'normal':list(p.normal),'material':m.materials[p.material_index].name,
              'part_id':attr.data[i].value if attr else None,
              'points':[list(m.vertices[k].co) for k in p.vertices]})
print('FACES='+json.dumps(rows,ensure_ascii=False))

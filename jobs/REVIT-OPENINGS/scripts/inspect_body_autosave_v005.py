"""Read-only inventory of a copied Blender autosave from the open session."""
import json
from collections import Counter
from pathlib import Path
import bpy

root=Path(__file__).resolve().parents[1]
out=root/'outputs/body-v005'
bpy.ops.wm.open_mainfile(filepath=str(out/'live-autosave-snapshot.blend'))
scene=bpy.context.scene
rows=[]
for obj in scene.objects:
    row={'name':obj.name,'type':obj.type,'collections':[c.name for c in obj.users_collection],
         'dimensions':[round(v,4) for v in obj.dimensions],
         'matrix_world':[[round(float(v),6) for v in line] for line in obj.matrix_world],
         'properties':{k:str(obj[k])[:120] for k in obj.keys()}}
    if obj.type=='MESH':
        row.update(vertices=len(obj.data.vertices),faces=len(obj.data.polygons),
                   materials=[m.name if m else None for m in obj.data.materials],
                   material_counts=dict(Counter(p.material_index for p in obj.data.polygons)))
    rows.append(row)
report={'file':bpy.data.filepath,'scene':scene.name,'objects':rows,
        'collections':dict(Counter(c for r in rows for c in r['collections'])),
        'selected':[o.name for o in bpy.context.selected_objects]}
(out/'autosave-inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'scene':scene.name,'objects':len(rows),'collections':report['collections'],
                  'selected':report['selected'][:12],
                  'large_meshes':[{k:r[k] for k in ['name','vertices','faces','materials','material_counts']}
                                  for r in sorted((r for r in rows if r['type']=='MESH'),
                                                  key=lambda r:r['faces'],reverse=True)[:12]]},ensure_ascii=False))

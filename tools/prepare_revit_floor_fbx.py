"""Blender-only import and exact full-name index for the OBR22 floor prototype."""
import bpy,json,sys
from pathlib import Path
from mathutils import Vector
p=Path(sys.argv[sys.argv.index('--')+1]).resolve()
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(p/'OBR22_K02_floor02_source.fbx'),use_image_search=False)
objects=[]
for o in bpy.context.scene.objects:
    if o.type!='MESH': continue
    vs=[o.matrix_world@Vector(v) for v in o.bound_box]
    objects.append({'name':o.name,'vertices':len(o.data.vertices),'faces':len(o.data.polygons),'min':[min(v[i] for v in vs) for i in range(3)],'max':[max(v[i] for v in vs) for i in range(3)],'materials':[m.name if m else None for m in o.data.materials]})
(p/'fbx_inventory.json').write_text(json.dumps(objects,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(p/'source_import.blend'))
print('SUMMARY',json.dumps({'objects':len(objects),'vertices':sum(o['vertices'] for o in objects),'faces':sum(o['faces'] for o in objects),'min':[min(o['min'][i] for o in objects) for i in range(3)],'max':[max(o['max'][i] for o in objects) for i in range(3)],'sample':objects[:5]},ensure_ascii=True))

import json,re
from pathlib import Path
from io_scene_fbx import parse_fbx,import_fbx
p=Path(sys.argv[sys.argv.index('--')+1]).resolve()
root,version=parse_fbx.parse(str(p/'OBR22_K02_floor02_source.fbx'))
objects=next(x for x in root.elems if x.id==b'Objects')
rows=[]; mats=[]
for x in objects.elems:
    if x.id==b'Model':
        raw=x.props[1].split(b'\x00\x01')[0]
        name=raw.decode('utf-8','replace')
        rows.append({'fbx_id':x.props[0],'name':name,'blender_name':import_fbx.validate_blend_names(raw),'revit_id_candidates':re.findall(r'\[(\d+)\]',name)})
    if x.id==b'Material': mats.append(str(x.props))
(p/'fbx-name-map.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'count':len(rows),'samples':rows[:8],'materials':mats[:3],'material_count':len(mats)},ensure_ascii=True))

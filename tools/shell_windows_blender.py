"""Build v007 and read back a temporary final-Attach copy for cross-group QA."""
import hashlib
import json
import sys
from pathlib import Path

import bpy
import numpy as np

p=Path(sys.argv[sys.argv.index('--')+1]).resolve()
optimized='--optimized' in sys.argv
version='v008' if optimized else 'v007'
data=json.loads((p/('shell-windows-optimized.json' if optimized else 'shell-windows.json')).read_text(encoding='utf-8'))
blend=p/('OBR22_K02_typical_floor_v008_WINDOWS_CLEAN.blend' if optimized else 'OBR22_K02_typical_floor_v007_SHELL_WINDOWS.blend')

if '--check' in sys.argv:
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    meshes=[]
    for expected in data['meshes']:
        obj=bpy.data.objects[expected['name']];mesh=obj.data
        v=np.array([list(x.co) for x in mesh.vertices]);f=[list(x.vertices) for x in mesh.polygons]
        assert f==expected['faces']
        assert np.max(np.linalg.norm(v-np.array(expected['vertices']),axis=1))<5e-6
        assert all(len(x)==4 for x in f)
        meshes.append({**expected,'vertices':v.tolist(),'faces':f})
    assert len([o for o in bpy.context.scene.objects if o.type=='MESH'])==len(meshes)
    assert not any(o.modifiers for o in bpy.context.scene.objects if o.type=='MESH')
    # Actual Blender Join on a throwaway scene; master keeps editable logical groups.
    bpy.ops.object.select_all(action='DESELECT')
    for expected in data['meshes']:bpy.data.objects[expected['name']].select_set(True)
    bpy.context.view_layer.objects.active=bpy.data.objects[data['meshes'][0]['name']]
    bpy.ops.object.join()
    joined=bpy.context.view_layer.objects.active
    assert len(joined.data.polygons)==sum(len(m['faces']) for m in meshes)
    offset=0;joined_faces=[]
    for m in meshes:
        joined_faces.extend([[i+offset for i in f] for f in m['faces']]);offset+=len(m['vertices'])
    assert [list(f.vertices) for f in joined.data.polygons]==joined_faces
    result={**data,'meshes':meshes,'actual_blender_join_verified':True,
            'sha256':hashlib.sha256(blend.read_bytes()).hexdigest()}
    (p/('shell-windows-optimized-readback.json' if optimized else 'shell-windows-readback.json')).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    print('READBACK_AND_JOIN_OK',len(meshes),len(joined.data.polygons),result['sha256'])
    raise SystemExit(0)

bpy.ops.wm.open_mainfile(filepath=str(p/'OBR22_K02_typical_floor_v006_EXTERIOR.blend'))
for obj in list(bpy.context.scene.objects):
    if obj.type=='MESH':bpy.data.objects.remove(obj,do_unlink=True)
collection=bpy.data.collections.new('02_WINDOWS_MEASURED');bpy.context.scene.collection.children.link(collection)
colors=[(.75,.77,.79,1),(.28,.3,.32,1),(.08,.22,.30,1)]
materials=[]
for name,color in zip(['BODY_neutral_preview','FRAME_neutral_preview','PANEL_inferred_preview'],colors):
    material=bpy.data.materials.new(name);material.diffuse_color=color;materials.append(material)
for mi,item in enumerate(data['meshes']):
    mesh=bpy.data.meshes.new(item['name']);mesh.from_pydata(item['vertices'],[],item['faces']);mesh.update()
    obj=bpy.data.objects.new(item['name'],mesh)
    (bpy.data.collections['01_BODY_EXTERIOR_ONLY'] if mi==0 else collection).objects.link(obj)
    for material in materials:mesh.materials.append(material)
    for face,mat in zip(mesh.polygons,item['materials']):face.material_index=mat
    if mi:
        record=data['windows'][mi-1];obj['revit_element_id']=record['id'];obj['source_type']=record['type']
        obj['recess_m']=record['recess_m'];obj['lateral_embed_m']=.01
    else:obj['shell_m']=.4;obj['inner_faces_removed']=True
    obj['stage']=version+' simplified measured facade; see SHELL_WINDOWS_METADATA.json'
meta={k:v for k,v in data.items() if k!='meshes'}
bpy.data.texts.new('SHELL_WINDOWS_METADATA.json').write(json.dumps(meta,ensure_ascii=False,indent=2))
bpy.data.texts['READ_ME.txt'].clear()
bpy.data.texts['READ_ME.txt'].write(version+': наружные фейсы + Shell0.4м без внутренней стенки. Откосы и верх/низ сохранены.\n'
    '45 окон: плоскость по проёму, рама с врезанием10мм, панели и посадка измерены из источника.\n'
    'Это упрощённые типовые окна, без ручек/фурнитуры; материалы условные.\n'
    '6 обрезанных границей этажа участков лестничных проёмов остаются без окна: нужен полный соседний источник.\n'
    'Высота3м и выемка v006 остаются записанными предположениями. Внутренние задние фейсы намеренно отсутствуют.\n')
s=bpy.context.scene;s['status']=version+' Shell without inner faces +45 measured simplified windows; partial stairs pending'
s.display.shading.color_type='MATERIAL';s.display.shading.light='STUDIO'
for obj in s.objects:obj.select_set(False)
body=bpy.data.objects[data['meshes'][0]['name']];body.select_set(True);bpy.context.view_layer.objects.active=body
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
# Temporary preview wires are not saved into the scene.
for obj in list(s.objects):
    if obj.type!='MESH':continue
    wire=obj.copy();wire.data=obj.data.copy();s.collection.objects.link(wire)
    wire.data.materials.clear();mat=bpy.data.materials.get('PREVIEW_WIRE') or bpy.data.materials.new('PREVIEW_WIRE')
    mat.diffuse_color=(.005,.008,.012,1);wire.data.materials.append(mat)
    for poly in wire.data.polygons:poly.material_index=0
    mod=wire.modifiers.new('PREVIEW_WIRE','WIREFRAME');mod.thickness=.002;mod.use_replace=True
for cam,name,w,h in [('Наружная_оболочка','shell-windows-overview.png',2000,900),('Сетка_наружного_проёма','shell-windows-detail.png',1400,1000)]:
    s.camera=bpy.data.objects[cam];s.render.resolution_x=w;s.render.resolution_y=h;s.render.filepath=str(p/(name.replace('.png','-clean.png') if optimized else name))
    bpy.ops.render.render(write_still=True)
print('SAVED',blend)

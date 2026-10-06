"""Real Blender linked meshes, UV variants and saved-file evidence."""
import hashlib
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

p=Path(sys.argv[sys.argv.index('--')+1]).resolve();out=p/'uv_trial'
d=json.loads((out/'uv-manifest.json').read_text(encoding='utf-8'))
names={'MASTER':'OBR22_K02_v009_INSTANCES_IDS.blend','NPM_ATLAS':'OBR22_K02_v009_NPM_ATLAS.blend','VPM_UDIM':'OBR22_K02_v009_VPM_UDIM.blend'}

if '--check' in sys.argv:
    evidence={}
    for variant,name in names.items():
        file=out/name;bpy.ops.wm.open_mainfile(filepath=str(file))
        objects=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(objects)==46
        unique={o.data.name:o.data for o in objects};assert len(unique)==4
        records=[]
        for item in d['instances']:
            obj=bpy.data.objects[item['name']];assert obj.data.name==item['mesh_key']
            assert np.max(abs(np.array(obj.matrix_world)-np.array(item['matrix'])))<5e-6
        for expected in (d['vpm_meshes'] if variant=='VPM_UDIM' else d['meshes']):
            mesh=bpy.data.meshes[expected['key']]
            f=[list(face.vertices) for face in mesh.polygons];assert f==expected['faces']
            verts=np.array([list(v.co) for v in mesh.vertices]);assert np.max(abs(verts-np.array(expected['vertices'])))<5e-6
            ids=[v.value for v in mesh.attributes['finish_id'].data];assert ids==expected['finish_ids']
            uvs={layer.name:[[float(v) for v in loop.uv] for loop in layer.data] for layer in mesh.uv_layers}
            assert set(uvs)==({'NPM_ATLAS'} if variant=='MASTER' else {variant})
            records.append({'key':mesh.name,'users_in_scene':sum(o.data==mesh for o in objects),'faces':f,'vertices':verts.tolist(),'uv_layers':uvs,'finish_ids':ids})
        images=[{'name':im.name,'source':im.source,'path':bpy.path.abspath(im.filepath),'tiles':[t.number for t in im.tiles]} for im in bpy.data.images if im.source in {'TILED','FILE'}]
        evidence[variant]={'meshes':records,'images':images,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'instances':len(objects)-1,'shared_window_meshes':len(unique)-1}
    (out/'blender-uv-readback.json').write_text(json.dumps(evidence),encoding='utf-8')
    print('READBACK_OK',[(k,v['shared_window_meshes'],v['instances']) for k,v in evidence.items()])
    raise SystemExit(0)

def colour(values):
    return tuple(v/255/12.92 if v/255<=.04045 else ((v/255+.055)/1.055)**2.4 for v in values)+(1.,)

def build(variant,name):
    bpy.ops.wm.open_mainfile(filepath=str(p/'OBR22_K02_typical_floor_v008_WINDOWS_CLEAN.blend'))
    for obj in list(bpy.context.scene.objects):
        if obj.type=='MESH':bpy.data.objects.remove(obj,do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users==0:bpy.data.meshes.remove(mesh)
    materials={}
    for ident,rgb in d['palette'].items():
        mat=bpy.data.materials.new('ID_'+ident+('_UNRESOLVED' if ident=='0' else '_PDF_CANDIDATE'))
        mat.diffuse_color=colour(rgb);mat['finish_id']=int(ident);mat['status']='layout preview, not approved PBR'
        materials[int(ident)]=mat
    opaque=None;glass=None
    if variant!='MASTER':
        im=bpy.data.images.load(str(out/f'{variant}_Diffuse_PREVIEW.1001.png'),check_existing=False)
        if variant=='VPM_UDIM':
            im.source='TILED';im.filepath=str(out/'VPM_UDIM_Diffuse_PREVIEW.<UDIM>.png')
            for tile in d['layouts'][variant]['tiles'][1:]:im.tiles.new(tile)
            im.reload()
        opaque=bpy.data.materials.new(variant+'_OPAQUE_PREVIEW');opaque.use_nodes=True
        nodes=opaque.node_tree.nodes;tex=nodes.new('ShaderNodeTexImage');tex.image=im
        opaque.node_tree.links.new(tex.outputs['Color'],nodes.get('Principled BSDF').inputs['Base Color']);nodes.active=tex
        glass=materials[90]
    library={}
    for mi,item in enumerate(d['vpm_meshes'] if variant=='VPM_UDIM' else d['meshes']):
        mesh=bpy.data.meshes.new(item['key']);mesh.from_pydata(item['vertices'],[],item['faces']);mesh.update()
        mesh.attributes.new('finish_id','INT','FACE').data.foreach_set('value',item['finish_ids'])
        mesh['source_type']=item.get('source_type','BODY');mesh['linked_instance_master']=True
        if variant=='MASTER':
            slots=list(materials)
            for ident in slots:mesh.materials.append(materials[ident])
            for face,ident in zip(mesh.polygons,item['finish_ids']):face.material_index=slots.index(ident)
        else:
            mesh.materials.append(opaque);mesh.materials.append(glass)
            for face,ident in zip(mesh.polygons,item['finish_ids']):face.material_index=int(ident==90)
        for layout_name,layout in d['layouts'].items():
            if layout_name!=('NPM_ATLAS' if variant=='MASTER' else variant):continue
            layer=mesh.uv_layers.new(name=layout_name)
            for entry in layout['entries']:
                if entry['mesh']!=mi:continue
                for loop,uv in zip(mesh.polygons[entry['face']].loop_indices,entry['uv']):layer.data[loop].uv=uv
        library[item['key']]=mesh
    collection=bpy.data.collections.new('INSTANCED_FLOOR');bpy.context.scene.collection.children.link(collection)
    for item in d['instances']:
        obj=bpy.data.objects.new(item['name'],library[item['mesh_key']]);collection.objects.link(obj);obj.matrix_world=Matrix(item['matrix'])
        for key in ['revit_id','source_type','normalization_max_error_m']:
            if key in item:obj[key]=item[key]
    meta={k:v for k,v in d.items() if k not in ['meshes','vpm_meshes','layouts']}
    bpy.data.texts.new('UV_TRIAL_PROVENANCE.json').write(json.dumps(meta,ensure_ascii=False,indent=2))
    s=bpy.context.scene;s['status']='Geometry accepted; UV/material trial only. See uv-manifest and QA. Not final NPM/VPM delivery.'
    s.display.shading.color_type='MATERIAL' if variant=='MASTER' else 'TEXTURE'
    s.display.shading.light='FLAT';s.camera=bpy.data.objects['Наружная_оболочка']
    bpy.ops.wm.save_as_mainfile(filepath=str(out/name))
    for cam,suffix,w,h in [('Наружная_оболочка','overview',2000,900),('Сетка_наружного_проёма','detail',1400,1000)]:
        s.camera=bpy.data.objects[cam];s.render.resolution_x=w;s.render.resolution_y=h;s.render.filepath=str(out/f'{variant}_{suffix}.png')
        bpy.ops.render.render(write_still=True)

for variant,name in names.items():build(variant,name)
print('SAVED',list(names.values()))

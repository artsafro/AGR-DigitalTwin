"""Apply compact shared UVs; verify saved geometry and real tile/region assignments."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

root=Path(sys.argv[sys.argv.index('--')+1]).resolve()
revision='v012' if '--npm-v012' in sys.argv else 'v011'
out=root/('npm_v012' if revision=='v012' else 'shared_v011')
d=json.loads((out/'shared-uv-manifest.json').read_text(encoding='utf-8'))
old=json.loads((root/'uv_trial/uv-manifest.json').read_text(encoding='utf-8'))


def geometry():
    return {o.name:{'mesh':o.data.name,'matrix':[list(r) for r in o.matrix_world],
                   'v':[list(v.co) for v in o.data.vertices],
                   'f':[list(p.vertices) for p in o.data.polygons],
                   'ids':[v.value for v in o.data.attributes['finish_id'].data]}
            for o in bpy.context.scene.objects if o.type=='MESH'}


def solid(name,rgb):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=tuple((x/255/12.92 if x/255<=.04045 else ((x/255+.055)/1.055)**2.4) for x in rgb)+(1.,)
    return mat


def render(scene,cam,path,width=1600,height=1100):
    scene.camera=cam;scene.render.resolution_x=width;scene.render.resolution_y=height
    scene.render.resolution_percentage=100;scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)


reports={}
for variant,data in d['variants'].items():
    bpy.ops.wm.open_mainfile(filepath=str(root/'textured_v010'/f'OBR22_K02_v010_{variant}.blend'))
    before=geometry()
    materials=[solid('PLACEHOLDER', [1,1,1]),solid('GLASS_PREVIEW',[100,137,151]),solid('ID0_UNRESOLVED',[220,50,170]),solid('FRAME_RAL7024',[69,73,78])]
    mat=materials[0];mat.name=variant+'_SHARED_DIFFUSE';mat.use_nodes=True
    path=out/('NPM_ATLAS_Diffuse.png' if variant=='NPM_ATLAS' else 'VPM_Diffuse.1001.png')
    im=bpy.data.images.load(str(path),check_existing=False)
    if variant=='VPM_UDIM':
        im.source='TILED';im.filepath=str(out/'VPM_Diffuse.<UDIM>.png')
        for tile in data['tiles'][1:]:im.tiles.new(tile)
        im.reload()
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=im;mat.node_tree.nodes.active=tex
    mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    keys=[m['key'] for m in old['vpm_meshes' if variant=='VPM_UDIM' else 'meshes']]
    for key in keys:
        mesh=bpy.data.meshes[key];mesh.materials.clear()
        for material in materials:mesh.materials.append(material)
        for p in mesh.polygons:
            ident=mesh.attributes['finish_id'].data[p.index].value
            p.material_index=1 if ident==90 else 2 if ident==0 else 3 if ident in (6,7) and variant=='VPM_UDIM' else 0
        mesh['UV_POLICY']='intentional overlaps within finish group; no geometric overlaps authorized'
        for v in mesh.uv_layers.active.data:v.uv=(0,0)
    for entry in data['entries']:
        mesh=bpy.data.meshes[keys[entry['mesh']]]
        for loop,uv in zip(mesh.polygons[entry['face']].loop_indices,entry['uv']):mesh.uv_layers.active.data[loop].uv=uv
    im.filepath='//'+Path(im.filepath).name
    scene=bpy.context.scene
    scene['status']='Shared UV trial on rebaked user samples. ID0 unresolved; Diffuse only; not final delivery.'
    scene['material_tile_map']=json.dumps({'4':1001,'2':1002,'3':1003,'5':1004})
    bpy.data.texts.new('SHARED_UV_PROVENANCE.json').write(json.dumps(d,ensure_ascii=False,indent=2))
    scene.display.shading.color_type='TEXTURE';scene.display.shading.light='FLAT'
    scene.camera=bpy.data.objects['Наружная_оболочка']
    file=out/f'OBR22_K02_{revision}_{variant}.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(file),relative_remap=False)
    bpy.ops.wm.open_mainfile(filepath=str(file));assert geometry()==before
    scene=bpy.context.scene
    actual_density=[];regions=0;groups={};max_uv_error=0
    for entry in data['entries']:
        mesh=bpy.data.meshes[keys[entry['mesh']]];p=mesh.polygons[entry['face']]
        uv=np.array([list(mesh.uv_layers.active.data[i].uv) for i in p.loop_indices])
        max_uv_error=max(max_uv_error,float(np.max(abs(uv-np.array(entry['uv'])))))
        assert mesh.attributes['finish_id'].data[p.index].value==entry['finish_id']
        assert p.material_index==0
        group=entry['repeat_group'];groups[group]=groups.get(group,0)+1
        tile=int(np.floor(uv[:,0].mean()))+1001
        if entry['finish_id'] in (2,3,4,5):
            expected=({'4':1001,'2':1002,'3':1003,'5':1004}[str(entry['finish_id'])] if variant=='VPM_UDIM' else 1001)
            assert tile==expected
            local=(uv-[tile-1001,0])*data['size']
            rect=entry['region_px'];pad=data['padding']
            assert np.all(local.min(0)>=np.array(rect[:2])+pad-.002)
            assert np.all(local.max(0)<=np.array(rect[2:])-pad+.002)
            signed=np.sum(uv[:,0]*np.roll(uv[:,1],-1)-uv[:,1]*np.roll(uv[:,0],-1))
            assert signed>0
            q=np.array([list(mesh.vertices[i].co) for i in p.vertices])
            density=np.linalg.norm(np.roll(uv,1,axis=0)-uv,axis=1)*data['size']/np.linalg.norm(np.roll(q,1,axis=0)-q,axis=1)
            actual_density.extend(density.tolist());assert max(abs(density-entry['density']))<.05
            regions+=1
    assert max_uv_error<1e-6
    render(scene,bpy.data.objects['Наружная_оболочка'],out/f'{variant}_overview.png',2000,1100)
    render(scene,bpy.data.objects['Сетка_наружного_проёма'],out/f'{variant}_brick.png')
    body=next(o for o in scene.objects if o.type=='MESH' and o.data.name=='BODY')
    for ident,label in [(2,'light_tile'),(4,'dark_tile')]:
        faces=[p for p in body.data.polygons if body.data.attributes['finish_id'].data[p.index].value==ident and abs(p.normal.z)<.1]
        face=max(faces,key=lambda p:p.area);center=body.matrix_world@face.center
        normal=(body.matrix_world.to_3x3()@face.normal).normalized()
        camera_data=bpy.data.cameras.new('Inspect_'+label);camera=bpy.data.objects.new('Inspect_'+label,camera_data);scene.collection.objects.link(camera)
        camera.location=center+normal*7+Vector((0,0,.5));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        camera_data.type='ORTHO';camera_data.ortho_scale=4.5
        render(scene,camera,out/f'{variant}_{label}.png')
    tex=next(n for n in bpy.data.meshes['BODY'].materials[0].node_tree.nodes if n.type=='TEX_IMAGE')
    assert [t.number for t in tex.image.tiles]==data['tiles']
    assert Path(bpy.path.abspath(tex.image.filepath)).parent==out
    reports[variant]={'geometry_ids_matrices_instances_identical':True,'objects':len(before),'unique_meshes':len({x['mesh'] for x in before.values()}),
        'region_checked_faces':regions,'max_uv_error':max_uv_error,'density_min_max':[min(actual_density),max(actual_density)],
        'tiles':[t.number for t in tex.image.tiles],'tile_sizes':[list(t.size) for t in tex.image.tiles],
        'shared_groups_face_counts':groups,'unused_finish_id':3,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
    print('SHARED_UV_READBACK_OK',variant,flush=True)
(out/'blender-shared-qa.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')

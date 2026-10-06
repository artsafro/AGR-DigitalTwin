"""Blender background: editable source reference, explicitly NOT an NPM master."""
import bpy
import json
import sys
from pathlib import Path
from collections import defaultdict
from mathutils import Matrix, Vector

args = sys.argv[sys.argv.index('--')+1:]
src, out = (Path(p).resolve() for p in args[:2])
out.mkdir(parents=True,exist_ok=True)
assert not (out/'GLB_AB_source_reference.blend').exists(), 'Use a new output version'
defs={int(p.stem):json.loads(p.read_text(encoding='utf-8'))['entities'] for p in (src/'definitions').glob('*.json')}
materials=json.loads((src/'materials.json').read_text(encoding='utf-8'))['items']
textures={m['material']:m for m in json.loads((src/'textures/manifest.json').read_text(encoding='utf-8')) if m['colorized']}
config=json.loads((src.parent.parent/'reference-job.json').read_text(encoding='utf-8'))
excluded=set()
if '--exclude-plane-nodes' in args:
    node_cfg=json.loads((src.parent.parent/'plane-nodes-job.json').read_text(encoding='utf-8'))
    excluded={node_cfg['source_window_definition'],node_cfg['source_ac_definition']}
if '--exclude-sill-reveal-nodes' in args:
    trim_cfg=json.loads((src.parent.parent/'sill-reveal-job.json').read_text(encoding='utf-8'))
    excluded.update(trim_cfg['reveal_definitions']+trim_cfg['sill_definitions'])
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene['status']='SOURCE_REFERENCE_NOT_NPM'
scene['source_capture']=str(src)
scene['delivery']=False

def linear(v):
    v=v/255
    return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4

mats={}
for desc in materials:
    name=desc['name']
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    rgb=tuple(linear(c) for c in desc['color_rgb'])
    mat.diffuse_color=(*rgb,1)
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(*rgb,1)
    bsdf.inputs['Roughness'].default_value=.7
    mat['source_alpha']=desc['alpha']
    mat['source_name']=name
    if name in textures:
        tex=mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image=bpy.data.images.load(str(src/'textures'/textures[name]['file']),check_existing=True)
        tex.image.pack()
        mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    mats[name]=mat

report={'status':'SOURCE_REFERENCE_NOT_NPM','delivery':False,'floors':{},
        'limits':['Not rebuilt as clean quads.','Not atlas-mapped.','Not AGR Checker delivery.',
                  'Front-side UV only; back materials retained in source JSON.',
                  'Inherited textured UV and projective UV require visual validation.']}
for item in config['floors']:
    label,did,zoffset=item['label'],item['definition_id'],item['z_offset_m']
    buckets=defaultdict(lambda: {'verts':[],'faces':[],'uv':[],'source_ids':[]})
    def walk(did,matrix,inherited,visible):
        if did in excluded:return
        for e in defs[did]:
            mat=e.get('material') or inherited
            vis=visible and not e['hidden'] and e['layer_visible']
            if not vis:continue
            if 'definition_id' in e:
                a=e['transform_inches']
                t=Matrix([a[i::4] for i in range(4)])
                walk(e['definition_id'],matrix@t,mat,vis)
            elif e['type']=='Face':
                bucket=buckets[mat]
                start=len(bucket['verts'])
                for p in e['points_inches']:
                    v=(matrix@Vector(p))*.0254
                    v.z+=zoffset-config['definition_base_z_m']
                    bucket['verts'].append(tuple(v))
                uv=e['uvq_front']
                mirrored=matrix.to_3x3().determinant()<0
                for poly in e['polygons']:
                    ix=[abs(v)-1 for v in poly]
                    if mirrored:ix.reverse()
                    bucket['faces'].append([start+i for i in ix])
                    bucket['uv'].append([(uv[i][0]/uv[i][2],uv[i][1]/uv[i][2]) if uv[i] and abs(uv[i][2])>1e-12 else (0,0) for i in ix])
                    bucket['source_ids'].append(e['persistent_id'])
    walk(did,Matrix.Identity(4),None,True)
    coll=bpy.data.collections.new('SOURCE_'+label)
    scene.collection.children.link(coll)
    counts={}
    for name,b in buckets.items():
        mesh=bpy.data.meshes.new(label+'_'+str(name))
        mesh.from_pydata(b['verts'],[],b['faces'])
        mesh.update()
        uv=mesh.uv_layers.new(name='SketchUp_Source_UV')
        for poly,coords in zip(mesh.polygons,b['uv']):
            for i,co in zip(poly.loop_indices,coords):uv.data[i].uv=co
        attr=mesh.attributes.new(name='source_face_pid',type='INT',domain='FACE')
        attr.data.foreach_set('value',b['source_ids'])
        obj=bpy.data.objects.new(label+'_'+str(name),mesh)
        coll.objects.link(obj)
        if name in mats:mesh.materials.append(mats[name])
        obj['source_definition_id']=did
        obj['role']='source reference only'
        counts[str(name)]=len(mesh.polygons)
    report['floors'][label]=counts

scene.render.engine='CYCLES'
scene.cycles.samples=16
scene.cycles.use_denoising=True
scene.render.resolution_x=1600
scene.render.resolution_y=1000
scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('ReferenceWorld')
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.6,.6,.6,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
scene.view_settings.view_transform='Standard'
light=bpy.data.lights.new('Sun','SUN')
light.energy=2
ob=bpy.data.objects.new('Sun',light)
scene.collection.objects.link(ob)
ob.rotation_euler=(.4,-.6,-.3)
cam=bpy.data.cameras.new('ReferenceCamera')
ob=bpy.data.objects.new('ReferenceCamera',cam)
scene.collection.objects.link(ob)
scene.camera=ob
target=Vector((15.94,16.85,3.3))
ob.location=target+Vector((44,-58,27))
ob.rotation_euler=(target-ob.location).to_track_quat('-Z','Y').to_euler()
cam.type='ORTHO'
cam.ortho_scale=51
scene.render.filepath=str(out/'AB_reference.png')
scene['reference_limits']=json.dumps(report['limits'])
bpy.ops.wm.save_as_mainfile(filepath=str(out/'GLB_AB_source_reference.blend'))
# Actual saved-file readback before rendering.
bpy.ops.wm.open_mainfile(filepath=str(out/'GLB_AB_source_reference.blend'))
report['readback_mesh_objects']=sum(o.type=='MESH' for o in bpy.data.objects)
report['readback_polygons']=sum(len(o.data.polygons) for o in bpy.data.objects if o.type=='MESH')
report['packed_images']=sum(bool(im.packed_file) for im in bpy.data.images)
report['saved_readback']=report['readback_polygons']==sum(sum(c.values()) for c in report['floors'].values())
assert report['saved_readback']
(out/'reference-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.render.render(write_still=True)
print('REFERENCE_READBACK '+json.dumps(report,ensure_ascii=True))

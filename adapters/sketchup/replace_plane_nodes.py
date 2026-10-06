"""Replace only source window/basket nodes; preserve approved reference file."""
import bpy, bmesh, json, sys
from pathlib import Path
from mathutils import Matrix, Vector

job=Path(sys.argv[sys.argv.index('--')+1]).resolve()
src=job/'outputs/source-live-v001'
out=job/'outputs/planes-ab-v002'
cfg=json.loads((job/'plane-nodes-job.json').read_text(encoding='utf-8'))
floors=json.loads((job/'reference-job.json').read_text(encoding='utf-8'))
defs={int(f.stem):json.loads(f.read_text(encoding='utf-8'))['entities'] for f in (src/'definitions').glob('*.json')}
target=out/'GLB_AB_planes_v002.blend'
assert not target.exists(),'Use a new output version'
bpy.ops.wm.open_mainfile(filepath=str(job/'outputs/planes-base-v002/GLB_AB_source_reference.blend'))
def descendants(did):
    for e in defs[did]:
        if e['hidden'] or not e['layer_visible']:continue
        if 'definition_id' in e:yield from descendants(e['definition_id'])
        elif e['type']=='Face':yield e
original=json.loads((job/'outputs/reference-ab-v001/reference-report.json').read_text(encoding='utf-8'))
removed=original['readback_polygons']-sum(len(o.data.polygons) for o in bpy.data.objects if o.type=='MESH')

winmat=bpy.data.materials.new('M_Window_Atlas_PENDING')
winmat.use_nodes=True
winmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.12,.19,.22,1)
winmat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.65
winmat['atlas_status']='USER_WILL_MAP_WINDOW_TEXTURE'
winmat.use_backface_culling=True
w=cfg['window'];cx,cy=w['corner_xy_m'];b=w['embed_m']
right=w['opening_front_end_x_m']+b;left=w['opening_side_end_y_m']-b
z0=w['opening_bottom_z_m']-b;z1=w['opening_top_z_m']+b
verts=[(cx,cy,z0),(right,cy,z0),(right,cy,z1),(cx,cy,z1),(cx,left,z0),(cx,left,z1)]
# Outward normals +Y and -X; the corner is welded, no internal caps or thickness.
faces=[(1,0,3,2),(0,4,5,3)]
wm=bpy.data.meshes.new('Window_2_planes_shared')
wm.from_pydata(verts,[],faces);wm.materials.append(winmat);wm.update()
uv=wm.uv_layers.new(name='Window_Atlas_UV')
for p in wm.polygons:
    for i,co in zip(p.loop_indices,[(0,0),(1,0),(1,1),(0,1)]):uv.data[i].uv=co

lo=cfg['ac']['min_m'];hi=cfg['ac']['max_m'];x0,y0,z0=lo;x1,y1,z1=hi
av=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
    (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
af=[(0,1,5,4),(3,0,4,7),(1,2,6,5),(3,2,1,0)]
am=bpy.data.meshes.new('AC_4_planes_open_top_shared')
am.from_pydata(av,[],af);am.update()
manifest=json.loads((out/'AC_opacity_manifest.json').read_text(encoding='utf-8'))
auv=am.uv_layers.new(name='OpacityUV');fuv=am.uv_layers.new(name='FinishUV')
for p,name in zip(am.polygons,cfg['ac']['panels']):
    desc=manifest[name];u,v=desc['axes'];mn=desc['uv_min'];mx=desc['uv_max']
    for idx in p.loop_indices:
        pt=am.vertices[am.loops[idx].vertex_index].co
        uu=(pt[u]-lo[u])/(hi[u]-lo[u]);vv=(pt[v]-lo[v])/(hi[v]-lo[v])
        auv.data[idx].uv=(mn[0]+uu*(mx[0]-mn[0]),mn[1]+vv*(mx[1]-mn[1]))
        fuv.data[idx].uv=((pt[u]-lo[u])/8,(pt[v]-lo[v])/8)
if '[Color B05]' not in bpy.data.materials:
    with bpy.data.libraries.load(str(job/'outputs/reference-ab-v001/GLB_AB_source_reference.blend'),link=False) as (available,requested):
        requested.materials=['[Color B05]']
acmat=bpy.data.materials['[Color B05]'].copy();acmat.name='M_AC_d_o';acmat.use_backface_culling=True
nodes=acmat.node_tree.nodes;links=acmat.node_tree.links
finish=nodes.new('ShaderNodeUVMap');finish.uv_map='FinishUV'
for node in list(nodes):
    if node.type=='TEX_IMAGE':links.new(finish.outputs['UV'],node.inputs['Vector'])
mask=nodes.new('ShaderNodeTexImage');mask.image=bpy.data.images.load(str(out/'AC_opacity.png'));mask.image.colorspace_settings.name='Non-Color';mask.image.pack()
uvnode=nodes.new('ShaderNodeUVMap');uvnode.uv_map='OpacityUV';links.new(uvnode.outputs['UV'],mask.inputs['Vector'])
links.new(mask.outputs['Color'],nodes['Principled BSDF'].inputs['Alpha'])
# Back faces transparent also in Cycles; viewport culling alone is insufficient there.
geo=nodes.new('ShaderNodeNewGeometry');trans=nodes.new('ShaderNodeBsdfTransparent');mix=nodes.new('ShaderNodeMixShader')
links.new(geo.outputs['Backfacing'],mix.inputs[0]);links.new(nodes['Principled BSDF'].outputs[0],mix.inputs[1]);links.new(trans.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],nodes['Material Output'].inputs['Surface'])
am.materials.append(acmat)
counts={'windows':0,'ac':0};expected_removed=0;placements=[]
def instances(did,parent=None):
    parent=Matrix.Identity(4) if parent is None else parent
    for e in defs[did]:
        if 'definition_id' not in e or e['hidden'] or not e['layer_visible']:continue
        a=e['transform_inches'];m=parent@Matrix([a[i::4] for i in range(4)])
        if e['definition_id'] in [cfg['source_window_definition'],cfg['source_ac_definition']]:
            yield e,m
        else:yield from instances(e['definition_id'],m)
for f in floors['floors']:
    coll=bpy.data.collections.new('PLANES_'+f['label']);bpy.context.scene.collection.children.link(coll)
    for e,source_matrix in instances(f['definition_id']):
        d=e.get('definition_id')
        if d not in [cfg['source_window_definition'],cfg['source_ac_definition']]:continue
        if e['hidden'] or not e['layer_visible']:continue
        kind='windows' if d==cfg['source_window_definition'] else 'ac'
        mesh=wm if kind=='windows' else am
        m=source_matrix.copy()
        m.translation*=.0254;m.translation.z+=f['z_offset_m']-floors['definition_base_z_m']
        assert abs(m.to_3x3().determinant()-1)<1e-6,'Non-rigid placement requires special handling'
        obj=bpy.data.objects.new(f['label']+'_'+kind+'_'+str(e['persistent_id']),mesh);coll.objects.link(obj);obj.matrix_world=m
        obj['role']=kind;obj['source_instance_pid']=e['persistent_id'];obj['embed_m']=b if kind=='windows' else 0
        counts[kind]+=1
        expected_removed+=sum(len(q['polygons']) for q in descendants(d))
        placements.append({'floor':f['label'],'role':kind,'source_pid':e['persistent_id']})
assert removed==expected_removed,(removed,expected_removed)
scene=bpy.context.scene;scene['status']='PLANE_NODES_V002_BODY_IS_SOURCE';scene['delivery']=False
scene.render.filepath=str(out/'AB_planes.png')
bpy.ops.wm.save_as_mainfile(filepath=str(target))
bpy.ops.wm.open_mainfile(filepath=str(target))
checks=[]
for ob in bpy.data.objects:
    if ob.get('role') not in counts:continue
    me=ob.data;role=ob['role']
    checks.append({'name':ob.name,'quads':all(len(p.vertices)==4 for p in me.polygons),
                   'face_count':len(me.polygons),'no_modifiers':len(ob.modifiers)==0,
                   'no_top':all(p.normal.z<.999 for p in me.polygons) if role=='ac' else True,
                   'single_sided':all(m.use_backface_culling for m in me.materials),
                   'min_area':min(p.area for p in me.polygons)})
assert len(checks)==sum(counts.values())
assert all(c['quads'] and c['no_top'] and c['no_modifiers'] and c['single_sided'] and c['min_area']>0 for c in checks)
report={'counts':counts,'removed_source_polygons':removed,'added_quads':counts['windows']*2+counts['ac']*4,
        'saved_readback':True,'new_nodes_checks':checks,'placements':placements,'delivery':False,
        'limitations':['Window atlas intentionally unassigned: user will place UV.','Remaining BODY is original source topology.',
                       'Full model QA and AGR Checker not passed.']}
(out/'planes-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.render.render(write_still=True)
print('PLANE_NODES '+json.dumps({k:v for k,v in report.items() if k not in ['new_nodes_checks','placements']}))

"""GLB v008: penetrate non-welded pier ends into adjacent concrete belts."""
import bpy, bmesh, json, hashlib
from pathlib import Path
job=Path('jobs/GLB-NPM').resolve();out=job/'outputs/clearance-ab-v008';out.mkdir(exist_ok=True)
target=out/'GLB_AB_clearance_v008.blend';assert not target.exists()
bpy.ops.wm.open_mainfile(filepath=str(job/'outputs/clearance-ab-v007/GLB_AB_clearance_v007.blend'))
def signature(o):
    return hashlib.sha256(json.dumps(([list(v.co) for v in o.data.vertices],
        [list(p.vertices) for p in o.data.polygons], [p.material_index for p in o.data.polygons],
        [[list(d.uv) for d in l.data] for l in o.data.uv_layers],list(map(list,o.matrix_world)))).encode()).hexdigest()
unchanged={o.name:signature(o) for o in bpy.data.objects if o.type=='MESH' and not o.name.endswith('Материал3')}
changes=[]
for o in bpy.data.objects:
    if o.type!='MESH' or not o.name.endswith('Материал3'):continue
    me=o.data;lo=min(v.co.z for v in me.vertices);hi=max(v.co.z for v in me.vertices)
    assert abs((hi-lo)-2.3)<.00001
    for v in me.vertices:
        if abs(v.co.z-lo)<.00001:v.co.z-=.01
        elif abs(v.co.z-hi)<.00001:v.co.z+=.01
    me.update();bm=bmesh.new();bm.from_mesh(me)
    caps=[f for f in bm.faces if abs(f.normal.z)>.99999]
    assert len(caps)==97
    bmesh.ops.delete(bm,geom=caps,context='FACES')
    loose=[v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bm.to_mesh(me);bm.free();me.update()
    changes.append({'object':o.name,'removed_bottom_caps':len(caps),'upper_caps_already_absent':True,
        'penetration_top_and_bottom_m':.01,'local_z_before':[lo,hi]})
bpy.context.scene['status']='PIER_EMBED_V008_VISUAL_ACCEPTANCE_PENDING'
bpy.context.scene['delivery']=False
bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target))
assert all(signature(bpy.data.objects[n])==h for n,h in unchanged.items())
for c in changes:
    o=bpy.data.objects[c['object']];lo,hi=c['local_z_before']
    assert abs(min(v.co.z for v in o.data.vertices)-(lo-.01))<.00001
    assert abs(max(v.co.z for v in o.data.vertices)-(hi+.01))<.00001
    assert not any(abs(p.normal.z)>.99999 for p in o.data.polygons)
    assert all(p.area>1e-9 for p in o.data.polygons)
faces=[{'object':o.name,'index':p.index,'points':[list(o.matrix_world@o.data.vertices[i].co) for i in p.vertices]}
    for o in bpy.data.objects if o.type=='MESH' for p in o.data.polygons]
(out/'faces-readback.json').write_text(json.dumps(faces),encoding='utf-8')
(out/'pier-readback.json').write_text(json.dumps({'changes':changes,'unchanged_mesh_count':len(unchanged),
    'saved_readback':True,'limits':['Top of B must be covered by next A belt in tower assembly; it is intentionally open in the A/B module.']},indent=2),encoding='utf-8')
print('PIERS',json.dumps(changes,ensure_ascii=True),'faces',len(faces))

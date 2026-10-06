"""Apply user's +/-10 mm vertical penetration to the v003 sill shell."""
import bpy,bmesh,json,sys,hashlib
from pathlib import Path
job=Path(sys.argv[sys.argv.index('--')+1]).resolve()
out=job/'outputs/sills-ab-v004';out.mkdir(parents=True,exist_ok=True)
target=out/'GLB_AB_sills_v004.blend';assert not target.exists()
bpy.ops.wm.open_mainfile(filepath=str(job/'outputs/sills-ab-v003/GLB_AB_sills_v003.blend'))
before={};report={'version':'v004','offset_top_m':.01,'offset_bottom_m':-.01,'sills':[],
    'delivery':False,'intentional_volume_penetration':True,'full_model_intersection_QA':False}
def sig(ob):
    d={'m':[list(r) for r in ob.matrix_world],'v':[list(v.co) for v in ob.data.vertices],
       'p':[list(p.vertices) for p in ob.data.polygons],'uv':[[list(d.uv) for d in l.data] for l in ob.data.uv_layers]}
    return hashlib.sha256(json.dumps(d).encode()).hexdigest()
unchanged={o.name:sig(o) for o in bpy.data.objects if o.type=='MESH' and o.get('role')!='simple_sills'}
for ob in bpy.data.objects:
    if ob.get('role')!='simple_sills':continue
    me=ob.data
    top={i for p in me.polygons if p.normal.z>.999 for i in p.vertices}
    bottom={i for p in me.polygons if p.normal.z<-.999 for i in p.vertices}
    assert not top&bottom and len(top|bottom)==len(me.vertices)
    before[ob.name]={'co':[list(v.co) for v in me.vertices],'top':sorted(top),'bottom':sorted(bottom)}
    for i in top:me.vertices[i].co.z+=.01
    for i in bottom:me.vertices[i].co.z-=.01
    me.update();ob['top_penetration_m']=.01;ob['bottom_penetration_m']=.01
scene=bpy.context.scene;scene['status']='SILL_VERTICAL_PENETRATION_10MM_V004'
scene.render.filepath=str(out/'AB_sills_v004.png')
bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target))
assert unchanged=={o.name:sig(o) for o in bpy.data.objects if o.type=='MESH' and o.get('role')!='simple_sills'}
for name,old in before.items():
    ob=bpy.data.objects[name];me=ob.data;bm=bmesh.new();bm.from_mesh(me)
    top=set(old['top']);changes=[]
    for i,v in enumerate(me.vertices):
        prior=old['co'][i];delta=v.co.z-prior[2];expected=.01 if i in top else -.01
        assert abs(delta-expected)<1e-6
        assert abs(v.co.x-prior[0])<1e-7 and abs(v.co.y-prior[1])<1e-7
        changes.append(delta)
    nonmanifold=sum(len(e.link_faces)!=2 for e in bm.edges)
    duplicate=len(bm.faces)-len({tuple(sorted(tuple(round(x,5) for x in v.co) for v in f.verts)) for f in bm.faces})
    assert nonmanifold==0 and duplicate==0
    assert all(len(f.verts)==4 and f.calc_area()>1e-9 for f in bm.faces)
    report['sills'].append({'object':name,'quads':len(bm.faces),'nonmanifold_edges':nonmanifold,
      'duplicate_faces':duplicate,'xy_unchanged':True,'top_offset_verified_m':.01,
      'bottom_offset_verified_m':-.01,'resulting_thickness_m':.06})
    bm.free()
report['other_geometry_transforms_uv_unchanged']=True;report['saved_readback']=True
(out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(out/'source_vertex_positions.json').write_text(json.dumps(before),encoding='utf-8')
bpy.ops.render.render(write_still=True)
print(json.dumps(report))

import bpy,bmesh,json,sys,hashlib
from pathlib import Path
from mathutils import Vector
job=Path(sys.argv[sys.argv.index('--')+1]).resolve();out=job/'outputs/sills-ab-v003'
def signature(ob):
    d={'matrix':[list(r) for r in ob.matrix_world],
       'vertices':[list(v.co) for v in ob.data.vertices],
       'faces':[list(p.vertices) for p in ob.data.polygons],
       'uv':{l.name:[list(v.uv) for v in l.data] for l in ob.data.uv_layers}}
    return hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(job/'outputs/planes-ab-v002/GLB_AB_planes_v002.blend'))
prior={o.name:signature(o) for o in bpy.data.objects if o.get('role') in ['windows','ac']}
bpy.ops.wm.open_mainfile(filepath=str(out/'GLB_AB_sills_v003.blend'))
current={o.name:signature(o) for o in bpy.data.objects if o.get('role') in ['windows','ac']}
assert prior==current,'Window/AC geometry or UV changed'
checks=[]
for ob in bpy.data.objects:
    if ob.get('role')!='simple_sills':continue
    bm=bmesh.new();bm.from_mesh(ob.data)
    bad=sum(len(e.link_faces)!=2 for e in bm.edges)
    deg=sum(f.calc_area()<1e-9 for f in bm.faces)
    quads=all(len(f.verts)==4 for f in bm.faces)
    sig=[tuple(sorted(tuple(round(c,5) for c in v.co) for v in f.verts)) for f in bm.faces]
    dup=len(sig)-len(set(sig))
    checks.append({'mesh':ob.name,'quads':len(bm.faces),'all_quads':quads,'nonmanifold_edges':bad,'degenerates':deg,'duplicates':dup})
    assert bad==0 and deg==0 and dup==0 and quads,checks[-1]
    bm.free()
painted=sum(1 for ob in bpy.data.objects if ob.type=='MESH' for p in ob.data.polygons
            if len(ob.data.materials)>p.material_index and ob.data.materials[p.material_index].name=='M_Reveal_Color')
assert painted==208,painted
report={'saved_readback':True,'window_ac_geometry_transforms_uv_unchanged':True,'sills':checks,
        'existing_reveal_polygons_color_assigned':painted,'new_reveal_meshes':0,'delivery':False}
(out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
win=next(o for o in bpy.data.objects if o.get('role')=='windows' and o.name.startswith('A_'))
target=win.matrix_world@Vector((0,.1,-.3))
direction=win.matrix_world.to_3x3()@Vector((-1,1,.55)).normalized()
scene=bpy.context.scene;cam=scene.camera;cam.location=target+direction*7
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=4.2
scene.render.resolution_x=1500;scene.render.resolution_y=1100;scene.cycles.samples=32
scene.render.filepath=str(out/'window_sill_closeup.png')
bpy.ops.render.render(write_still=True)
print('VERIFIED '+json.dumps(report))

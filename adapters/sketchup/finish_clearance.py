import bpy,bmesh,json
from pathlib import Path
job=Path('jobs/GLB-NPM').resolve();prev=job/'outputs/clearance-ab-v005';out=job/'outputs/clearance-ab-v006';out.mkdir(exist_ok=True)
target=out/'GLB_AB_clearance_v006.blend';assert not target.exists()
bpy.ops.wm.open_mainfile(filepath=str(prev/'GLB_AB_clearance_v005.blend'))
seen=set();removed=0
for ob in bpy.data.objects:
    if ob.type!='MESH':continue
    me=ob.data
    if ob.get('role')=='ac' and me.name not in seen:
        for v in me.vertices:
            if v.co.y>.27:v.co.y-=.01
    elif 'Материал3' in ob.name:
        high=max(v.co.z for v in me.vertices)
        for v in me.vertices:
            if abs(v.co.z-high)<1e-5:v.co.z-=.01
        me.update();bm=bmesh.new();bm.from_mesh(me)
        caps=[f for f in bm.faces if f.normal.z>.999 and abs(f.calc_center_median().z-(high-.01))<1e-5]
        removed+=len(caps);bmesh.ops.delete(bm,geom=caps,context='FACES');bm.to_mesh(me);bm.free()
    me.update();seen.add(me.name)
desc=json.loads((prev/'misc-union.json').read_text());ob=bpy.data.objects['A_<auto>58'];old=ob.data
me=bpy.data.meshes.new('Misc_joined_source_envelope');me.from_pydata(desc['vertices'],[],desc['faces']);me.materials.append(old.materials[0]);me.update()
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000005);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();me.update();ob.data=me
me.uv_layers.new(name='Solid_Color_UV')
scene=bpy.context.scene;scene['status']='CLEARANCE_V006_PENDING_CHECK';scene['delivery']=False
bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target))
faces=[]
for o in bpy.data.objects:
    if o.type!='MESH':continue
    for p in o.data.polygons:faces.append({'object':o.name,'index':p.index,'points':[list(o.matrix_world@o.data.vertices[i].co) for i in p.vertices]})
(out/'faces-readback.json').write_text(json.dumps(faces),encoding='utf-8')
(out/'changes.json').write_text(json.dumps({'removed_internal_wall_top_cap_polygons':removed,'ac_rear_depth_reduction_m':.01,'misc_source_union':True},indent=2),encoding='utf-8')
print('v006 saved',len(faces),'faces; removed internal caps',removed)

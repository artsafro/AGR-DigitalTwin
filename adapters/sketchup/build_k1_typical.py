"""Straight pier ends, exterior-only typical floors, exact source K1 placements."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Matrix,Vector
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out.parent/'clearance-ab-v007/GLB_AB_clearance_v007.blend'))
visibility=json.loads((out/'body-visibility.json').read_text(encoding='utf-8'))
removed={};module=[]
for o in list(bpy.data.objects):
 if o.type!='MESH':continue
 if '<auto>26' in o.name:
  removed[o.name]={'interior_floor_faces':len(o.data.polygons)};bpy.data.objects.remove(o,do_unlink=True);continue
 if o.name.endswith('Материал3'):
  me=o.data;lo=min(v.co.z for v in me.vertices);hi=max(v.co.z for v in me.vertices)
  bad={r['index'] for r in visibility[o.name] if r['outside_visible_samples']==0}
  bm=bmesh.new();bm.from_mesh(me);bm.faces.ensure_lookup_table()
  kill=[f for f in bm.faces if f.index in bad or abs(f.normal.z)>.99999]
  removed[o.name]={'interior_back_faces':len(bad),'caps':len(kill)-len(bad)}
  bmesh.ops.delete(bm,geom=kill,context='FACES')
  for v in bm.verts:
   if abs(v.co.z-lo)<.00001:v.co.z-=.01
   elif abs(v.co.z-hi)<.00001:v.co.z+=.01
  loose=[v for v in bm.verts if not v.link_faces];bmesh.ops.delete(bm,geom=loose,context='VERTS')
  bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
  bm.to_mesh(me);bm.free();me.update()
  o['end_treatment']='Z_ONLY_10MM_NO_BEVEL_NO_INSET'
 if o.get('role') not in ['windows','ac','simple_sills']:o['role']='body'
 if o.get('role')=='simple_sills':
  base=0 if o.name.startswith('A_') else 3.3
  for v in o.data.vertices:
   if any(abs(v.co.z-base-z)<.00001 for z in [.975,1.035]):v.co.z-=.0001
  o.data.update()
 module.append(o)
bpy.context.scene['status']='STRAIGHT_EXTERIOR_AB_PENDING_ASSEMBLY_QA'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'GLB_AB_straight_v011.blend'))
instances=sorted(json.loads((out/'floor-instances.json').read_text()),key=lambda r:r['z_translation_m'])
coll=bpy.data.collections.new('K1_TYPICAL_EXTERIOR');bpy.context.scene.collection.children.link(coll)
new=[]
for level,row in enumerate(instances):
 label='A' if row['definition_id']==170455 else 'B'
 w=Matrix(row['matrix_inches']);w.translation*=.0254
 placement=w@Matrix.Translation((0,0,.02-(0 if label=='A' else 3.3)))
 for src in module:
  if not src.name.startswith(label+'_'):continue
  ob=src.copy();ob.data=src.data.copy();ob.name=f'K1_L{level+1:02d}_{src.name}'
  ob.matrix_world=placement@src.matrix_world;coll.objects.link(ob)
  ob['source_floor_entity']=row['path'][-1];ob['source_floor_definition']=row['definition_id'];ob['floor_index']=level+1
  ob['source_module_name']=src.name
  new.append(ob)
for o in module:bpy.data.objects.remove(o,do_unlink=True)
# Attach by logical role; body joints will be clipped in plane before the final weld.
for role in ['body','windows','ac','simple_sills']:
 group=[o for o in list(coll.objects) if o.get('role','body')==role]
 if not group:continue
 bpy.ops.object.select_all(action='DESELECT')
 for o in group:o.select_set(True)
 bpy.context.view_layer.objects.active=group[0];bpy.ops.object.join()
 ob=bpy.context.object;ob.name='K1_'+role.upper();ob['role']=role
 bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
 if role!='body':
  bm=bmesh.new();bm.from_mesh(ob.data);before=len(bm.verts)
  bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000005)
  bm.to_mesh(ob.data);bm.free();ob.data.update();ob['welded_vertices']=before-len(ob.data.vertices)
scene=bpy.context.scene;scene['status']='K1_TYPICAL_ASSEMBLY_PENDING_COPLANAR_WELD';scene['delivery']=False
objects=[o for o in bpy.data.objects if o.type=='MESH'];pts=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
lo=Vector(tuple(min(v[i] for v in pts) for i in range(3)));hi=Vector(tuple(max(v[i] for v in pts) for i in range(3)))
aim=(lo+hi)/2;cam=scene.camera;cam.location=aim+Vector((85,-110,65));cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=76
scene.render.resolution_x=1300;scene.render.resolution_y=1500;scene.cycles.samples=24
bpy.ops.wm.save_as_mainfile(filepath=str(out/'K1_typical_assembled_preQA.blend'))
records=[]
for o in objects:
 for p in o.data.polygons:
  records.append({'object':o.name,'index':p.index,'material':o.data.materials[p.material_index].name,
   'points':[list(o.matrix_world@o.data.vertices[i].co) for i in p.vertices],
   'uv':[list(o.data.uv_layers.active.data[i].uv) for i in p.loop_indices]})
(out/'assembly-faces.json').write_text(json.dumps(records),encoding='utf-8')
(out/'assembly-report.json').write_text(json.dumps({'floor_count':len(instances),'removed_per_AB':removed,'source_placements':True,
 'pier_end_changes':'Z only +10/-10mm; no added faces, no XY offset', 'limits':['Top block not built yet','Final body weld pending']},indent=2),encoding='utf-8')
print('K1',len(instances),'floors',len(records),'faces')

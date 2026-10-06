"""Keep visible pier surfaces; add buried end strips, remove hidden caps."""
import bpy,bmesh,json,hashlib
from pathlib import Path
from mathutils import Vector
job=Path('jobs/GLB-NPM').resolve();out=job/'outputs/clearance-ab-v010'
target=out/'GLB_AB_clearance_v010.blend';assert not target.exists()
bpy.ops.wm.open_mainfile(filepath=str(job/'outputs/clearance-ab-v007/GLB_AB_clearance_v007.blend'))
desc=json.loads((out/'pier-extensions.json').read_text(encoding='utf-8'));changes=[]
def sig(o):
 return hashlib.sha256(json.dumps(([list(v.co) for v in o.data.vertices],[list(p.vertices) for p in o.data.polygons],
 [p.material_index for p in o.data.polygons],[[list(d.uv) for d in l.data] for l in o.data.uv_layers],list(map(list,o.matrix_world)))).encode()).hexdigest()
unchanged={o.name:sig(o) for o in bpy.data.objects if o.type=='MESH' and o.name not in desc}
for name,rows in desc.items():
 o=bpy.data.objects[name];old=o.data;inv=o.matrix_world.inverted()
 verts=[tuple(v.co) for v in old.vertices];faces=[];mats=[];uvs=[]
 for p in old.polygons:
  if abs(p.normal.z)>.99999:continue
  faces.append(tuple(p.vertices));mats.append(p.material_index)
  uvs.append([tuple(old.uv_layers.active.data[i].uv) for i in p.loop_indices])
 for row in rows:
  p=old.polygons[row['face']]
  a,b=[inv@Vector(row[x]) for x in ['a','b']]
  ia=min(p.vertices,key=lambda i:(old.vertices[i].co-a).length)
  ib=min(p.vertices,key=lambda i:(old.vertices[i].co-b).length)
  assert (old.vertices[ia].co-a).length<.00001 and (old.vertices[ib].co-b).length<.00001
  j=len(verts);verts.extend(tuple(inv@Vector(row[x])) for x in ['new_a','new_b'])
  faces.append((ib,ia,j,j+1));mats.append(p.material_index)
  uv={v:old.uv_layers.active.data[l].uv.copy() for v,l in zip(p.vertices,p.loop_indices)}
  # Extend the existing planar UV in the vertical direction without shifting visible UVs.
  other=next(i for i in p.vertices if i not in [ia,ib])
  slope=(uv[other]-uv[ia])/(old.vertices[other].co.z-a.z)
  dz=verts[j][2]-a.z
  uvs.append([tuple(uv[ib]),tuple(uv[ia]),tuple(uv[ia]+slope*dz),tuple(uv[ib]+slope*dz)])
 me=bpy.data.meshes.new(name+'_EmbeddedEnds');me.from_pydata(verts,[],faces);me.update()
 for m in old.materials:me.materials.append(m)
 layer=me.uv_layers.new(name=old.uv_layers.active.name)
 for p,mat,uv in zip(me.polygons,mats,uvs):
  p.material_index=mat
  for i,value in zip(p.loop_indices,uv):layer.data[i].uv=value
 # Weld only coincident vertices within the pier mesh; loop UVs/materials remain per face.
 bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
 loose=[v for v in bm.verts if not v.link_faces]
 bmesh.ops.delete(bm,geom=loose,context='VERTS');bm.to_mesh(me);bm.free();me.update();o.data=me
 changes.append({'object':name,'removed_bottom_caps':97,'new_end_quads':len(rows),
  'penetration_m':.01,'visible_surface_preserved':True,'buried_xy_boundary_margin_m':.01})
bpy.context.scene['status']='PIER_EMBED_V010_VISUAL_ACCEPTANCE_PENDING';bpy.context.scene['delivery']=False
bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target))
assert all(sig(bpy.data.objects[n])==h for n,h in unchanged.items())
for name in desc:
 o=bpy.data.objects[name];assert all(p.area>1e-10 for p in o.data.polygons)
 assert not any(abs(p.normal.z)>.99999 for p in o.data.polygons)
 bm=bmesh.new();bm.from_mesh(o.data)
 assert not any(len(e.link_faces)>2 for e in bm.edges)
 bm.free()
faces=[{'object':o.name,'index':p.index,'points':[list(o.matrix_world@o.data.vertices[i].co) for i in p.vertices]}
 for o in bpy.data.objects if o.type=='MESH' for p in o.data.polygons]
(out/'faces-readback.json').write_text(json.dumps(faces),encoding='utf-8')
(out/'pier-readback.json').write_text(json.dumps({'changes':changes,'unchanged_mesh_count':len(unchanged),
 'saved_readback':True,'limits':['Top B is concealed by next A belt only after repeat assembly.','Final tower Attach and export QA pending.']},indent=2),encoding='utf-8')
print('PIER_EXTENSIONS',len(faces),'faces',len(unchanged),'unchanged meshes')

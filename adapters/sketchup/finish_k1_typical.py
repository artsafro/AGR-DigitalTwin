import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
from mathutils.kdtree import KDTree
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'K1_typical_assembled_preQA.blend'))
ob=bpy.data.objects['K1_BODY'];old=ob.data
repl=json.loads((out/'coplanar-body-replacements.json').read_text())
vs=[];fs=[];uvs=[];mats=[]
for p in old.polygons:
 parts=repl.get(str(p.index),[{'points':[list(old.vertices[i].co) for i in p.vertices],
                             'uv':[list(old.uv_layers.active.data[i].uv) for i in p.loop_indices]}])
 for row in parts:
  start=len(vs);vs.extend(row['points']);fs.append(list(range(start,len(vs))));uvs.append(row['uv']);mats.append(p.material_index)
me=bpy.data.meshes.new('K1_BODY_PlanarWeld');me.from_pydata(vs,[],fs);me.update()
for mat in old.materials:me.materials.append(mat)
uv=me.uv_layers.new(name=old.uv_layers.active.name)
for p,m,coords in zip(me.polygons,mats,uvs):
 p.material_index=m
 for i,co in zip(p.loop_indices,coords):uv.data[i].uv=co
bm=bmesh.new();bm.from_mesh(me);before=len(bm.verts)
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
# Conform straight shared edges before welding; do not bridge separate penetrating shells.
bm.verts.ensure_lookup_table();tree=KDTree(len(bm.verts))
for i,v in enumerate(bm.verts):tree.insert(v.co,i)
tree.balance();original=list(bm.verts);splits=0
for edge in list(bm.edges):
 a,b=edge.verts;delta=b.co-a.co;length=delta.length
 if length<.00002:continue
 hits=[]
 for co,i,dist in tree.find_range((a.co+b.co)/2,length/2+.00002):
  v=original[i]
  if v in [a,b]:continue
  t=(co-a.co).dot(delta)/(length*length)
  if .00001/length<t<1-.00001/length and (co-(a.co+delta*t)).length<.00001:hits.append((t,co.copy()))
 previous=0;start=a;current=edge
 for t,co in sorted(hits,key=lambda x:x[0]):
  if t-previous<.00001/length:continue
  newedge,newvert=bmesh.utils.edge_split(current,start,(t-previous)/(1-previous))
  newvert.co=co;current=next(e for e in newvert.link_edges if b in e.verts);start=newvert;previous=t;splits+=1
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
# Join compatible source triangles into quads, respecting materials and loop UVs.
bmesh.ops.join_triangles(bm,faces=[f for f in bm.faces if len(f.verts)==3],
 angle_face_threshold=.0001,angle_shape_threshold=.8,cmp_uvs=True,cmp_materials=True)
loose=[v for v in bm.verts if not v.link_faces];bmesh.ops.delete(bm,geom=loose,context='VERTS')
bm.to_mesh(me);bm.free();me.update();ob.data=me
scene=bpy.context.scene;scene['status']='K1_TYPICAL_STRAIGHT_EXTERIOR_TOP_NEXT';scene['delivery']=False
target=out/'K1_typical_straight_v011.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target))
records=[];report={}
for o in bpy.data.objects:
 if o.type!='MESH':continue
 bm=bmesh.new();bm.from_mesh(o.data)
 report[o.name]={'vertices':len(bm.verts),'faces':len(bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),
 'edges_more_than_two_faces':sum(len(e.link_faces)>2 for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-9 for f in bm.faces)}
 bm.free()
 for p in o.data.polygons:records.append({'object':o.name,'index':p.index,'points':[list(o.matrix_world@o.data.vertices[i].co) for i in p.vertices]})
(out/'typical-saved-faces.json').write_text(json.dumps(records),encoding='utf-8')
(out/'typical-weld-readback.json').write_text(json.dumps({'objects':report,'body_vertices_before_weld':before,
 'conforming_edge_splits':splits,'partitioned_belt_faces':len(repl),'weld_tolerance_m':.00001},indent=2),encoding='utf-8')
scene=bpy.context.scene;scene.render.filepath=str(out/'K1_typical.png');bpy.ops.render.render(write_still=True)
print('WELD',len(repl),'belt faces',splits,'edge splits',len(records),'faces')

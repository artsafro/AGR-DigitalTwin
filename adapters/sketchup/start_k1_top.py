"""Begin unique K1 top from its exact source transform, with texture-plane nodes."""
import bpy,bmesh,json,math
from pathlib import Path
from collections import defaultdict
from mathutils import Matrix,Vector
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve();src=out.parent/'source-live-v001'
bpy.ops.wm.open_mainfile(filepath=str(out/'K1_typical_straight_v011.blend'))
# At penetrating junctions keep the coplanar welded pair and detach the third shell.
ob=bpy.data.objects['K1_BODY'];bm=bmesh.new();bm.from_mesh(ob.data);detach=set()
for e in bm.edges:
 if len(e.link_faces)<=2:continue
 ff=list(e.link_faces);pairs=[(ff[i].normal.dot(ff[j].normal),i,j) for i in range(len(ff)) for j in range(i)]
 score,i,j=max(pairs)
 assert score>.9999
 detach.update(f for k,f in enumerate(ff) if k not in [i,j])
uv=bm.loops.layers.uv.active
for f in list(detach):
 vs=[bm.verts.new(v.co) for v in f.verts];nf=bm.faces.new(vs);nf.material_index=f.material_index
 for a,b in zip(nf.loops,f.loops):a[uv].uv=b[uv].uv
 bmesh.ops.delete(bm,geom=[f],context='FACES_ONLY')
loose=[v for v in bm.verts if not v.link_faces];bmesh.ops.delete(bm,geom=loose,context='VERTS')
assert not any(len(e.link_faces)>2 for e in bm.edges)
bm.to_mesh(ob.data);bm.free();ob.data.update()
defs={int(p.stem):json.loads(p.read_text(encoding='utf-8'))['entities'] for p in (src/'definitions').glob('*.json')}
top=json.loads((out/'top-source.json').read_text());w=Matrix(top['matrix_inches'])
buckets=defaultdict(lambda:{'verts':[],'faces':[],'uv':[]});nodecounts=defaultdict(int)
windows={147188,113102,14155,77062};ac={146223,77254,59138,95178}
def bounds(did):
 points=[]
 def rec(d,m):
  for e in defs[d]:
   if 'definition_id' in e:rec(e['definition_id'],m@Matrix([e['transform_inches'][i::4] for i in range(4)]))
   elif e['type']=='Face':points.extend(m@Vector(p)*.0254 for p in e['points_inches'])
 rec(did,Matrix.Identity(4))
 return [Vector(tuple(fn(p[i] for p in points) for i in range(3))) for fn in [min,max]]
coll=bpy.data.collections.new('K1_TOP_DRAFT_SOURCE_CONTOURS');bpy.context.scene.collection.children.link(coll)
windowmat=bpy.data.materials['M_Window_Atlas_PENDING'];actemplate=bpy.data.objects['K1_AC']
def walk(did,matrix,inherited):
 if did in windows|ac:
  lo,hi=bounds(did);center=(lo+hi)/2;size=hi-lo
  if did in windows:
   thin=min(range(3),key=lambda i:size[i]);axes=[i for i in range(3) if i!=thin];verts=[]
   for a,b in [(0,0),(1,0),(1,1),(0,1)]:
    p=center.copy();p[axes[0]]=(hi if a else lo)[axes[0]];p[axes[1]]=(hi if b else lo)[axes[1]];verts.append(p)
   faces=[(0,1,2,3)];mat=windowmat;uvcoords=[[(0,0),(1,0),(1,1),(0,1)]]
  else:
   # Four one-sided panels, no top/back; draft source dimensions, atlas slots retained.
   x0,x1=lo.x+.01,hi.x-.01;y0,y1=lo.y,hi.y-.01;z0,z1=lo.z,hi.z
   verts=[Vector(p) for p in [(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1),(x0,y1,z0),(x0,y1,z1),(x1,y1,z0),(x1,y1,z1)]]
   faces=[(0,1,2,3),(4,0,3,5),(1,6,7,2),(4,6,1,0)];mat=bpy.data.materials['M_AC_d_o']
   uvcoords=[[tuple(actemplate.data.uv_layers.active.data[i].uv) for i in p.loop_indices] for p in list(actemplate.data.polygons)[:4]]
  verts=[matrix@(p/.0254)*.0254 for p in verts]
  me=bpy.data.meshes.new('TopNode');me.from_pydata(verts,[],faces);me.materials.append(mat);me.update();layer=me.uv_layers.new(name='Atlas_UV_DRAFT')
  for p,uvrow in zip(me.polygons,uvcoords):
   for i,v in zip(p.loop_indices,uvrow):layer.data[i].uv=v
  ob=bpy.data.objects.new(('TOP_Window_' if did in windows else 'TOP_AC_')+str(nodecounts[did]),me);coll.objects.link(ob)
  ob['source_definition']=did;ob['status']='DRAFT_OPENING_DEPTH_AND_UV_REVIEW_PENDING';nodecounts[did]+=1
  return
 for e in defs[did]:
  if e.get('hidden') or not e.get('layer_visible',True):continue
  mat=e.get('material') or inherited
  if 'definition_id' in e:walk(e['definition_id'],matrix@Matrix([e['transform_inches'][i::4] for i in range(4)]),mat)
  elif e['type']=='Face':
   b=buckets[mat];start=len(b['verts']);b['verts'].extend(tuple(matrix@Vector(p)*.0254) for p in e['points_inches'])
   for poly in e['polygons']:
    ix=[abs(i)-1 for i in poly]
    if matrix.to_3x3().determinant()<0:ix.reverse()
    b['faces'].append([start+i for i in ix]);uvq=e['uvq_front'];b['uv'].append([(uvq[i][0]/uvq[i][2],uvq[i][1]/uvq[i][2]) if uvq[i] and abs(uvq[i][2])>1e-10 else (0,0) for i in ix])
walk(top['definition_id'],w,None)
for name,b in buckets.items():
 me=bpy.data.meshes.new('TOP_'+str(name));me.from_pydata(b['verts'],[],b['faces']);me.update()
 mat=bpy.data.materials.get(name or '') or bpy.data.materials.new('TOP_DEFAULT');me.materials.append(mat);uv=me.uv_layers.new(name='Source_UV_DRAFT')
 for p,coords in zip(me.polygons,b['uv']):
  for i,v in zip(p.loop_indices,coords):uv.data[i].uv=v
 ob=bpy.data.objects.new(me.name,me);coll.objects.link(ob);ob['status']='SOURCE_CONTOUR_DRAFT_EXTERIOR_CLEANUP_PENDING'
 bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
 bmesh.ops.join_triangles(bm,faces=[f for f in bm.faces if len(f.verts)==3],angle_face_threshold=.0001,angle_shape_threshold=.8,cmp_uvs=True,cmp_materials=True)
 bm.to_mesh(me);bm.free();me.update()
scene=bpy.context.scene;scene['status']='K1_TYPICAL_ASSEMBLED_TOP_DRAFT';scene['delivery']=False
scene.camera.data.ortho_scale=84;scene.camera.location.z+=4
target=out/'K1_with_top_draft_v011.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target));scene=bpy.context.scene
(out/'top-start-report.json').write_text(json.dumps({'source_entity':206495,'source_definition':169633,'plane_nodes_by_definition':dict(nodecounts),
 'detached_penetrating_body_faces':len(detach),'top_objects':len(bpy.data.collections[coll.name].objects) if False else len(buckets)+sum(nodecounts.values()),
 'top_status':'DRAFT: exterior cleanup, normals, opening seating and atlas still require verification'},indent=2),encoding='utf-8')
scene.render.filepath=str(out/'K1_with_top_draft.png');bpy.ops.render.render(write_still=True)
print('TOP START',dict(nodecounts),'raw body faces',sum(len(b['faces']) for b in buckets.values()))

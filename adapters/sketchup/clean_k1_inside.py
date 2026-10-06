import bpy,bmesh,json,math,ast
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'K1_with_top_draft_v011.blend'))
window=bpy.data.objects['K1_WINDOWS'];wv=[window.matrix_world@v.co for v in window.data.vertices]
wf=[list(p.vertices) for p in window.data.polygons];wtree=BVHTree.FromPolygons(wv,wf,all_triangles=False)
ob=bpy.data.objects['K1_BODY'];old=ob.data;verts=[];faces=[];uvs=[];mats=[];trimmed=0
for p in old.polygons:
 pts=[old.vertices[i].co.copy() for i in p.vertices];uv=[old.uv_layers.active.data[i].uv.copy() for i in p.loop_indices]
 if old.materials[p.material_index].name=='M_Reveal_Color':
  center=sum(pts,Vector())/len(pts);loc,n,idx,dist=wtree.find_nearest(center)
  assert dist<.3
  if abs(p.normal.dot(n))<.01:
   result=[];ruv=[]
   for a,b,ua,ub in zip(pts,pts[1:]+pts[:1],uv,uv[1:]+uv[:1]):
    da=(a-loc).dot(n);db=(b-loc).dot(n)
    if da>=-.000001:result.append(a);ruv.append(ua)
    if (da>0 and db<0) or (da<0 and db>0):
     t=da/(da-db);result.append(a.lerp(b,t));ruv.append(ua.lerp(ub,t))
   if any((p-loc).dot(n)<-.000001 for p in pts):trimmed+=1
   pts,uv=result,ruv
 if len(pts)<3:continue
 start=len(verts);verts.extend(pts);faces.append(list(range(start,len(verts))));uvs.append(uv);mats.append(p.material_index)
me=bpy.data.meshes.new('K1_BODY_ExteriorOnly');me.from_pydata(verts,[],faces);me.update()
for m in old.materials:me.materials.append(m)
layer=me.uv_layers.new(name=old.uv_layers.active.name)
for p,m,uv in zip(me.polygons,mats,uvs):
 p.material_index=m
 for i,value in zip(p.loop_indices,uv):layer.data[i].uv=value
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000005)
# Preserve separate penetrating shells at any coincident multi-face edges.
uvlayer=bm.loops.layers.uv.active;detach=set()
for e in bm.edges:
 if len(e.link_faces)>2:
  ff=list(e.link_faces);score,i,j=max((ff[i].normal.dot(ff[j].normal),i,j) for i in range(len(ff)) for j in range(i))
  detach.update(f for k,f in enumerate(ff) if k not in [i,j])
for f in detach:
 nf=bm.faces.new([bm.verts.new(v.co) for v in f.verts]);nf.material_index=f.material_index
 for a,b in zip(nf.loops,f.loops):a[uvlayer].uv=b[uvlayer].uv
 bmesh.ops.delete(bm,geom=[f],context='FACES_ONLY')
bm.to_mesh(me);bm.free();me.update();ob.data=me
# Occlusion test excludes opacity baskets; they must never hide facade faces in this test.
vv=[];ff=[]
for o in bpy.data.objects:
 if o.type!='MESH' or o.name=='K1_AC' or o.name.startswith('TOP_AC_'):continue
 start=len(vv);vv.extend(o.matrix_world@v.co for v in o.data.vertices);ff.extend([start+i for i in p.vertices] for p in o.data.polygons)
tree=BVHTree.FromPolygons(vv,ff,all_triangles=False)
bad=json.loads((out/'interior-probe-before.json').read_text())['front_faces_from_interior']
candidate_sills={ast.literal_eval(k)[1] for k in bad if ast.literal_eval(k)[0]=='K1_SIMPLE_SILLS'}
removed={};retained={}
for o in [bpy.data.objects['K1_SIMPLE_SILLS'],ob]:
 kill=[];keep=[]
 for p in o.data.polygons:
  if o.name=='K1_SIMPLE_SILLS':
   if p.index not in candidate_sills:continue
  elif o.data.materials[p.material_index].name!='<auto>58':continue
  n=p.normal
  if abs(n.z)>.01:continue
  pts=[o.data.vertices[i].co for i in p.vertices];center=sum(pts,Vector())/len(pts);samples=[center]+[center*.2+v*.8 for v in pts];visible=False
  for point in samples:
   for i in range(128):
    a=(i+.31)*math.tau/128;d=Vector((math.cos(a),math.sin(a),0))
    if n.dot(d)<.02:continue
    if tree.ray_cast(point+n*.0002,d,100)[0] is None:visible=True;break
   if visible:break
  (keep if visible else kill).append(p.index)
 bm=bmesh.new();bm.from_mesh(o.data);bm.faces.ensure_lookup_table();bmesh.ops.delete(bm,geom=[bm.faces[i] for i in kill],context='FACES')
 loose=[v for v in bm.verts if not v.link_faces];bmesh.ops.delete(bm,geom=loose,context='VERTS');bm.to_mesh(o.data);bm.free();o.data.update()
 removed[o.name]=len(kill);retained[o.name]=len(keep)
scene=bpy.context.scene;scene['status']='K1_TYPICAL_EXTERIOR_CLEAN_TOP_DRAFT';scene['delivery']=False
target=out/'K1_exterior_top_draft_v012.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target))
(out/'interior-cleanup.json').write_text(json.dumps({'trimmed_reveal_faces_at_window_planes':trimmed,
 'removed_hidden_faces':removed,'retained_exterior_visible_candidates':retained,'method':'Source opaque window planes clip rear reveal portions; exterior horizontal visibility verifies vertical rear faces.'},indent=2),encoding='utf-8')
print('INTERIOR CLEAN',trimmed,removed,retained)

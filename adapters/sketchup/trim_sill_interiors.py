import bpy,bmesh,json,ast
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'K1_exterior_top_draft_v012.blend'))
bad=json.loads((out/'interior-probe-K1_exterior_top_draft_v012.json').read_text())['front_faces_from_interior']
ids={ast.literal_eval(k)[1] for k in bad if ast.literal_eval(k)[0]=='K1_SIMPLE_SILLS'}
w=bpy.data.objects['K1_WINDOWS'];tree=BVHTree.FromPolygons([v.co for v in w.data.vertices],[list(p.vertices) for p in w.data.polygons])
o=bpy.data.objects['K1_SIMPLE_SILLS'];old=o.data;vs=[];fs=[];uvs=[];mats=[];cut=0
for p in old.polygons:
 pts=[old.vertices[i].co.copy() for i in p.vertices];uv=[old.uv_layers.active.data[i].uv.copy() for i in p.loop_indices]
 if p.index in ids:
  loc,n,idx,dist=tree.find_nearest(sum(pts,Vector())/len(pts));assert dist<.3 and abs(p.normal.dot(n))<.01
  pp=[];uu=[]
  for a,b,ua,ub in zip(pts,pts[1:]+pts[:1],uv,uv[1:]+uv[:1]):
   da=(a-loc).dot(n);db=(b-loc).dot(n)
   if da>=-.000001:pp.append(a);uu.append(ua)
   if da*db<0:
    t=da/(da-db);pp.append(a.lerp(b,t));uu.append(ua.lerp(ub,t))
  pts,uv=pp,uu;cut+=1
 if len(pts)<3:continue
 start=len(vs);vs.extend(pts);fs.append(list(range(start,len(vs))));uvs.append(uv);mats.append(p.material_index)
me=bpy.data.meshes.new('K1_Sills_Exterior');me.from_pydata(vs,[],fs);me.update()
for m in old.materials:me.materials.append(m)
layer=me.uv_layers.new(name=old.uv_layers.active.name)
for p,m,coords in zip(me.polygons,mats,uvs):
 p.material_index=m
 for i,co in zip(p.loop_indices,coords):layer.data[i].uv=co
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000005);bm.to_mesh(me);bm.free();me.update();o.data=me
bpy.context.scene['status']='K1_TYPICAL_EXTERIOR_VERIFICATION_TOP_DRAFT'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'K1_exterior_top_draft_v013.blend'))
print('Trimmed rear portions of',cut,'sill side faces at opaque window planes')

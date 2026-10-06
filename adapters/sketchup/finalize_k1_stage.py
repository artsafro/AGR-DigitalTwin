import bpy,bmesh,json
from pathlib import Path
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'K1_exterior_top_draft_v015.blend'))
desc=json.loads((out/'misc-exterior-replacements.json').read_text());o=bpy.data.objects['K1_BODY'];old=o.data;vs=[];fs=[];uvs=[];mats=[]
for p in old.polygons:
 parts=desc.get(str(p.index),[{'points':[list(old.vertices[i].co) for i in p.vertices],'uv':[list(old.uv_layers.active.data[i].uv) for i in p.loop_indices]}])
 for r in parts:
  start=len(vs);vs.extend(r['points']);fs.append(list(range(start,len(vs))));uvs.append(r['uv']);mats.append(p.material_index)
me=bpy.data.meshes.new('K1_CleanBody');me.from_pydata(vs,[],fs);me.update()
for m in old.materials:me.materials.append(m)
uv=me.uv_layers.new(name=old.uv_layers.active.name)
for p,m,row in zip(me.polygons,mats,uvs):
 p.material_index=m
 for i,co in zip(p.loop_indices,row):uv.data[i].uv=co
o.data=me
levels=sorted(r['z_translation_m']+.02 for r in json.loads((out/'floor-instances.json').read_text()))
w=bpy.data.objects['K1_WINDOWS'];cut=0
for v in w.data.vertices:
 z=v.co.z;idx=min(range(len(levels)),key=lambda i:abs(z-levels[i]-2.15));lo,hi=levels[idx]+1,levels[idx]+3.3
 if z<lo-.00001:v.co.z=lo;cut+=1
 elif z>hi+.00001:v.co.z=hi;cut+=1
w.data.update()
# Keep separate meshes until verification is complete; final Attach is performed afterwards.
for o in [bpy.data.objects['K1_BODY']]:
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000005)
 uv=bm.loops.layers.uv.active;detach=set()
 for e in bm.edges:
  if len(e.link_faces)>2:
   ff=list(e.link_faces);score,i,j=max((ff[i].normal.dot(ff[j].normal),i,j) for i in range(len(ff)) for j in range(i));detach.update(f for k,f in enumerate(ff) if k not in [i,j])
 for f in detach:
  nf=bm.faces.new([bm.verts.new(v.co) for v in f.verts]);nf.material_index=f.material_index
  for a,b in zip(nf.loops,f.loops):a[uv].uv=b[uv].uv
  bmesh.ops.delete(bm,geom=[f],context='FACES_ONLY')
 loose=[v for v in bm.verts if not v.link_faces];bmesh.ops.delete(bm,geom=loose,context='VERTS');bm.to_mesh(o.data);bm.free();o.data.update()
scene=bpy.context.scene;scene['status']='K1_TYPICAL_EXTERIOR_TOP_STARTED_PENDING_VISUAL_ACCEPTANCE';scene['delivery']=False
bpy.ops.wm.save_as_mainfile(filepath=str(out/'K1_exterior_top_draft_v016.blend'))
(out/'hidden-window-trim.json').write_text(json.dumps({'window_end_vertices_trimmed':cut,'reason':'Remove hidden 10mm top/bottom strips at final exterior shell assembly. Side overshoot remains; mid-depth unchanged.','opening_z_range_per_floor':[1,3.3]},indent=2),encoding='utf-8')
print('Hidden window end vertices trimmed',cut)

import bpy,bmesh,json,hashlib,sys,math
import numpy as np
from pathlib import Path
from collections import Counter,defaultdict
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path('C:/Users/artsafro/.AGR_Project');sys.path.insert(0,str(root/'src'))
from dt_ai.geometry.connect import connect_quads
out=root/'jobs/MASHI-LP/outputs/master-v001'
sys.path.insert(0,str(root/'jobs/MASHI-LP/scripts'))
from master_connect import conform
data=json.loads((out/'contours.json').read_text())+json.loads((out/'windows.json').read_text())
profile_data=json.loads((out/'profiles-quad.json').read_text())
profile_names={p['source_object'] for p in profile_data}|{'Object015','Object016','Object020'}
data=[p for p in data if p['source_object'] not in profile_names]+profile_data
align=json.loads((out/'old-alignment.json').read_text());rot=np.array(align['rotation']);trans=np.array(align['translation'])
old=bpy.data.objects['SM_MashiPoryvaevoj_34_004_Main.002'];materials=list(old.data.materials)
unknown=bpy.data.materials.new('MASTER_ID_18_UNRESOLVED');unknown.diffuse_color=(.55,.55,.55,1);materials.append(unknown)
v=[Vector(rot@np.array(old.matrix_world@p.co)+trans) for p in old.data.vertices];f=[];mat=[]
for p in old.data.polygons:
 if p.material_index in [4]:continue
 f.append(tuple(p.vertices));mat.append(p.material_index)
oldtree=BVHTree.FromPolygons(v,f)
def fingerprint(o):
 h=hashlib.sha256();h.update(str(tuple(tuple(r) for r in o.matrix_world)).encode())
 if o.type=='MESH':
  for p in o.data.vertices:h.update(str(tuple(p.co)).encode())
  for p in o.data.polygons:h.update(str((tuple(p.vertices),p.material_index)).encode())
  for layer in o.data.uv_layers:
   for u in layer.data:h.update(str(tuple(u.uv)).encode())
 return h.hexdigest()
before={o.name:fingerprint(o) for o in bpy.context.scene.objects}
col=bpy.data.collections.new('MASTER_Revit_v001');bpy.context.scene.collection.children.link(col)
groups=defaultdict(list);mapping=[]
for pi,p in enumerate(data):
 role=p['role'];pts=np.array(p['vertices']);mids=[];dist=[]
 for face in p['faces']:
  center=np.mean(pts[face],axis=0);loc,normal,idx,d=oldtree.find_nearest(Vector(center))
  mids.append(mat[idx] if d<1.5 else 17);dist.append(d)
 mid=Counter(mids).most_common(1)[0][0]
 if role=='glass':mid=9
 elif role=='frames':mid=0
 elif role=='spandrels':mid=10
 elif role=='roof':mid=2
 # Material IDs inferred by aligned old surface are explicitly traceable.
 p['material']=mid;p['patch_id']=pi
 if role=='body' and p['source_object']=='Material #215' and p['area']>25 and abs(p['normal'][2])<.05:role='walls'
 groups[role].append(p)
 mapping.append(dict(patch=pi,source_object=p['source_object'],source_faces=p['source_faces'],source_plane=p['source_plane'],role=role,material_slot=mid,material_name=materials[mid].name,old_surface_median_distance=float(np.median(dist)),method=p['method']))
created=[]
for role,parts in groups.items():
 print('BUILD',role,len(parts),flush=True)
 vv=[];ff=[];pid=[];mats=[];lookup={}
 for part in parts:
  if role=='profiles':
   local_pid=[part['patch_id']]*len(part['faces']);local_mat=[part['material']]*len(part['faces'])
   part['vertices'],part['faces'],_=conform(part['vertices'],part['faces'],local_pid,local_mat)
  ids=[]
  for point in part['vertices']:
   key=tuple(round(x,5) for x in point)
   if key not in lookup:lookup[key]=len(vv);vv.append(point)
   ids.append(lookup[key])
  for face in part['faces']:
   ff.append([ids[i] for i in face]);pid.append(part['patch_id']);mats.append(part['material'])
 # Remove exact duplicate faces across planar source groups.
 seen=set();keep=[]
 for i,face in enumerate(ff):
  key=tuple(sorted(face))
  if key not in seen and len(set(face))==4:seen.add(key);keep.append(i)
 ff=[ff[i] for i in keep];pid=[pid[i] for i in keep];mats=[mats[i] for i in keep]
 if role!='profiles':vv,ff,connect_report=conform(vv,ff,pid,mats)
 else:connect_report={'per_component':True}
 print('CONFORM',role,connect_report,flush=True)
 # Exterior wall shell, no inner reverse faces. Corner offsets solve measured normals.
 if role=='walls':
  pts=np.array(vv);normals=defaultdict(list);edges=defaultdict(list)
  for fi,face in enumerate(ff):
   q=pts[face];n=np.cross(q[1]-q[0],q[2]-q[0]);n/=np.linalg.norm(n)
   for vi in face:normals[vi].append(n)
   for a,b in zip(face,face[1:]+face[:1]):edges[tuple(sorted((a,b)))].append((fi,a,b))
  back={}
  for vi,ns in normals.items():
   ns=np.array(ns);delta=np.linalg.lstsq(ns,np.full(len(ns),-.4),rcond=None)[0]
   back[vi]=len(vv);vv.append((pts[vi]+delta).tolist())
  for links in edges.values():
   if len(links)!=1:continue
   fi,a,b=links[0];ff.append([b,a,back[a],back[b]]);pid.append(pid[fi]);mats.append(mats[fi])
 vv,ff,parents=connect_quads(vv,ff,max_side_m=3.8)
 pid=[pid[i] for i in parents];mats=[mats[i] for i in parents]
 if role!='profiles':vv,ff,connect_after=conform(vv.tolist(),ff.tolist(),pid,mats)
 else:vv,ff,connect_after=vv.tolist(),ff.tolist(),{'per_component':True}
 me=bpy.data.meshes.new('MASTER_'+role);me.from_pydata(vv,[],ff);me.update()
 for m in materials:me.materials.append(m)
 for p,m in zip(me.polygons,mats):p.material_index=m
 a=me.attributes.new('source_patch','INT','FACE');a.data.foreach_set('value',pid)
 a=me.attributes.new('finish_id','INT','FACE');a.data.foreach_set('value',[m+1 for m in mats])
 # Diagnostic density coordinates; final finish phase/texture maps are separate.
 uv=me.uv_layers.new(name='TD_1024_TEST')
 for p in me.polygons:
  q=np.array([me.vertices[i].co for i in p.vertices]);u=q[1]-q[0];u/=np.linalg.norm(u);n=np.array(p.normal);v=np.cross(n,u)
  xy=np.column_stack((q@u,q@v));xy-=xy.min(axis=0);xy=xy/4+.008
  for li,xyi in zip(p.loop_indices,xy):uv.data[li].uv=xyi
 o=bpy.data.objects.new('MASTER_'+role,me);col.objects.link(o);o.location.x=100
 o['source']='Revit measured contours; LP_old profile/material reference';o['placement_offset_m']=[100.,0.,0.];o['stage']='independent_midpoly_prototype';o['shell_m']=.4 if role=='walls' else 0.
 o['uv_note']='Diagnostic 4096px / 1024px per metre. Texture phase and final finish atlas pending.'
 o.color=(.55,.55,.55,1)
 created.append(dict(name=o.name,vertices=len(me.vertices),quads=len(me.polygons),materials=dict(Counter(mats)),connect=connect_report,connect_after=connect_after))
assert all(fingerprint(bpy.data.objects[name])==h for name,h in before.items())
for o in bpy.context.scene.objects:
 if o.type=='MESH':o.hide_render=o.name not in [r['name'] for r in created];o.hide_set(o.hide_render);o.select_set(False)
for o in col.objects:o.select_set(True)
bpy.context.view_layer.objects.active=next(iter(col.objects))
bpy.ops.wm.save_as_mainfile(filepath=str(out/'MASTER-built-v001.blend'))
(out/'material-provenance.json').write_text(json.dumps(mapping,indent=2))
(out/'build-report.json').write_text(json.dumps(dict(original_signatures=before,created=created,source='Revit geometry only, independently rebuilt',originals_unchanged=True,offset=[100,0,0]),indent=2))
print(json.dumps(created),flush=True)
exec(compile((root/'jobs/MASHI-LP/scripts/render_master.py').read_text(),'render_master.py','exec'))

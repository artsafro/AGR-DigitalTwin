"""Remove exact duplicates and finish measurable density cuts in the trial."""
import bpy,json,math,sys,numpy as np
from pathlib import Path
from collections import defaultdict
root=Path('C:/Users/artsafro/.AGR_Project');out=root/'jobs/MASHI-LP/outputs/master-v001'
sys.path.insert(0,str(root/'jobs/MASHI-LP/scripts'))
from master_connect import conform
def project(q):
 n=np.cross(q[1]-q[0],q[2]-q[0]);n/=np.linalg.norm(n);u=q[1]-q[0];u/=np.linalg.norm(u);v=np.cross(n,u);base=np.column_stack((q@u,q@v))
 options=[]
 for angle in np.linspace(0,math.pi/2,19):
  c,s=math.cos(angle),math.sin(angle);xy=base@np.array([[c,-s],[s,c]]);xy-=xy.min(axis=0);options.append(xy)
 return min(options,key=lambda xy:float(xy.max()))
def cut(vv,ff,counts):
 keys=[];ec={}
 for face,cnt in zip(ff,counts):
  es=[tuple(sorted((a,b))) for a,b in zip(face,face[1:]+face[:1])];keys.append(es)
  for e in es:ec[e]=max(ec.get(e,1),cnt)
 changed=True
 while changed:
  changed=False
  for es in keys:
   for a,b in [(es[0],es[2]),(es[1],es[3])]:
    n=max(ec[a],ec[b])
    if ec[a]!=n or ec[b]!=n:changed=True
    ec[a]=ec[b]=n
 vertices=[];faces=[];parent=[];lookup={};vv=np.array(vv)
 for fi,(face,es) in enumerate(zip(ff,keys)):
  q=vv[face];nx,ny=ec[es[0]],ec[es[1]];grid=[]
  for j in range(ny+1):
   row=[];t=j/ny
   for i in range(nx+1):
    s=i/nx;p=(1-s)*(1-t)*q[0]+s*(1-t)*q[1]+s*t*q[2]+(1-s)*t*q[3];key=tuple(np.round(p,7))
    if key not in lookup:lookup[key]=len(vertices);vertices.append(p.tolist())
    row.append(lookup[key])
   grid.append(row)
  for j in range(ny):
   for i in range(nx):faces.append([grid[j][i],grid[j][i+1],grid[j+1][i+1],grid[j+1][i]]);parent.append(fi)
 return vertices,faces,parent
report=[]
for o in bpy.data.collections['MASTER_Revit_v001'].objects:
 me=o.data;vv=[list(v.co) for v in me.vertices];ff=[];mats=[];patch=[];seen=set();removed=0
 for p in me.polygons:
  face=list(p.vertices);key=tuple(sorted(tuple(round(x,5) for x in vv[i]) for i in face))
  if key in seen:removed+=1;continue
  seen.add(key);ff.append(face);mats.append(p.material_index);patch.append(me.attributes['source_patch'].data[p.index].value)
 before=len(ff)
 for step in range(3):
  points=np.array(vv);counts=[max(1,math.ceil(float(project(points[f]).max())/3.8)) for f in ff]
  if max(counts)==1:break
  vv,ff,parent=cut(vv,ff,counts);mats=[mats[i] for i in parent];patch=[patch[i] for i in parent]
 if o.name!='MASTER_profiles':vv,ff,_=conform(np.array(vv,dtype=np.float32).astype(float).tolist(),ff,patch,mats,tolerance=.00003)
 new=bpy.data.meshes.new(me.name+'_density');new.from_pydata(vv,[],ff);new.update()
 for m in me.materials:new.materials.append(m)
 for p,m in zip(new.polygons,mats):p.material_index=m
 for name,values in [('source_patch',patch),('finish_id',[m+1 for m in mats])]:new.attributes.new(name,'INT','FACE').data.foreach_set('value',values)
 uv=new.uv_layers.new(name='TD_1024_TEST');spans=[]
 for p in new.polygons:
  xy=project(np.array([new.vertices[i].co for i in p.vertices]));spans.append(float(xy.max()))
  for li,v in zip(p.loop_indices,xy/4+.008):uv.data[li].uv=v
 o.data=new;o['qa_status']='TRIAL: unresolved intersections; see MASTER_TRIAL_REPORT.md';o['production_ready']=False
 report.append(dict(name=o.name,removed_exact_duplicates=removed,faces_before=before,faces_after=len(ff),max_uv_physical_span=max(spans)))
col=bpy.data.collections['MASTER_Revit_v001'];col['status']='TRIAL / QA NOT PASSED';col['report']='jobs/MASHI-LP/MASTER_TRIAL_REPORT.md'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'MASTER-trial-v001.blend'))
(out/'finalize-report.json').write_text(json.dumps(report,indent=2));print(report)

"""Use shared principal facade directions instead of noisy per-face projection frames."""
import bpy,json,sys,math,hashlib,shutil
from pathlib import Path
import numpy as np

source=Path(sys.argv[sys.argv.index('--')+1]).resolve()
out=Path(sys.argv[sys.argv.index('--')+2]).resolve();out.mkdir(parents=True,exist_ok=False)
manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'));D=manifest['sampling_px_m'];N=manifest['atlas_size']
for name,meta in manifest['objects'].items():
 o=bpy.data.objects[name];m=o.data;world=np.array([o.matrix_world@v.co for v in m.vertices]);origin=np.array(meta['origin_m'])
 records=json.loads((source/meta['records_file']).read_text());uv=m.uv_layers[meta['new_uv_layer']]
 # Weighted fourth-angle histogram yields the two common perpendicular facade axes.
 angles=[];weights=[]
 for p,r in zip(m.polygons,records):
  if r['vertical'][2]>.999:
   t=np.array(r['tangent']);angle=math.atan2(t[1],t[0])%(math.pi/2)
   angles.append(angle);weights.append(p.area)
 hist={}
 for a,w in zip(angles,weights):
  key=round(a*180/math.pi,1)%90;hist[key]=hist.get(key,0)+w
 mode=max(hist,key=hist.get)*math.pi/180
 near=[(a,w) for a,w in zip(angles,weights) if abs((a-mode+math.pi/4)%(math.pi/2)-math.pi/4)<math.radians(.2)]
 # Weighted circular mean avoids the 0/90 boundary.
 base=math.atan2(sum(w*math.sin(4*a) for a,w in near),sum(w*math.cos(4*a) for a,w in near))/4
 axes=[np.array([math.cos(base+k*math.pi/2),math.sin(base+k*math.pi/2),0.]) for k in range(2)]
 for t in axes:
  if t[np.argmax(abs(t))]<0:t*=-1
 snapped=0;exceptions=0;worst=0
 for p,r in zip(m.polygons,records):
  q=world[list(p.vertices)];t=np.array(r['tangent']);v=np.array(r['vertical'])
  if v[2]>.999:
   candidate=max(axes,key=lambda a:abs(np.dot(t,a)))
   if abs(np.dot(t,candidate))>math.cos(math.radians(3)):
    t=candidate;v=np.array([0.,0.,1.]);snapped+=1
   else:exceptions+=1
  xy=np.stack(((q-origin)@t,(q-origin)@v),axis=1)
  mid=str(p.material_index+1);period=np.array(manifest['panel_dimensions_m'][mid])
  shift=np.floor((xy.min(0)+1e-9)/period)*period;fold=xy-shift
  for a in range(2):
   if fold[:,a].min()<-1e-8:fold[:,a]+=period[a];shift[a]-=period[a]
  x,y,w,h=manifest['regions_px'][mid]
  assert (fold.min(0)>=-1e-7).all() and (fold.max(0)*D<=np.array([w,h])+1e-5).all(),(name,p.index)
  values=(fold*D+np.array([x,y]))/N
  for li,value in zip(p.loop_indices,values):uv.data[li].uv=value
  error=float(np.max(abs(np.linalg.norm(q-np.roll(q,1,axis=0),axis=1)-np.linalg.norm(xy-np.roll(xy,1,axis=0),axis=1))))
  worst=max(worst,error);r.update(tangent=t.tolist(),vertical=v.tolist(),shift_m=shift.tolist(),projection_edge_error_m=error)
 meta.update(principal_tangent_angle_deg=math.degrees(base),shared_frame_faces=snapped,nonprincipal_vertical_faces=exceptions,max_projection_edge_error_m=worst)
 (out/meta['records_file']).write_text(json.dumps(records),encoding='utf-8')
 print(name,snapped,exceptions,'edge_error',worst)
for img in bpy.data.images:
 if img.name.startswith('T_Facades_'):
  filename=Path(img.filepath_raw).name
  shutil.copyfile(source/filename,out/filename)
  img.filepath_raw='//'+filename
manifest['phase_method']='Shared principal orthogonal facade frame, explicit metre projection; horizontal ledges keep longest-edge frame'
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.data.texts['ATLAS_RECIPE.json'].clear();bpy.data.texts['ATLAS_RECIPE.json'].write(json.dumps(manifest,ensure_ascii=False,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(out/'facades_metric_v003.blend'))

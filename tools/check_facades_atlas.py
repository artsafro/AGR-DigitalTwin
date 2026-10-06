import bpy,json,sys,hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np

out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
N=manifest['atlas_size'];D=manifest['sampling_px_m'];summary={}
def geom_hash(o):
 return hashlib.sha256(json.dumps({'v':[v.co[:] for v in o.data.vertices],
   'f':[p.vertices[:] for p in o.data.polygons],'ids':[p.material_index for p in o.data.polygons],
   'matrix':list(map(list,o.matrix_world))},sort_keys=True).encode()).hexdigest()
for name,meta in manifest['objects'].items():
 o=bpy.data.objects[name];m=o.data
 assert geom_hash(o)==meta['geometry_hash']
 old=np.array([x.uv[:] for x in m.uv_layers[meta['original_uv_layer']].data])
 assert hashlib.sha256(old.tobytes()).hexdigest()==meta['original_uv_hash']
 uv=m.uv_layers[meta['new_uv_layer']];origin=np.array(meta['origin_m'])
 recs=json.loads((out/meta['records_file']).read_text())
 ranges={};err=0.;edge_error=0.;shared=defaultdict(list)
 world=np.array([o.matrix_world@v.co for v in m.vertices])
 for p,r in zip(m.polygons,recs):
  mid=str(p.material_index+1);x0,y0,w,h=manifest['regions_px'][mid]
  coords=np.array([uv.data[i].uv[:] for i in p.loop_indices])*N
  assert (coords.min(0)>=np.array([x0,y0])-.001).all()
  assert (coords.max(0)<=np.array([x0+w,y0+h])+.001).all()
  q=world[list(p.vertices)];tan=np.array(r['tangent']);vert=np.array(r['vertical'])
  metric=(coords-np.array([x0,y0]))/D
  actual=metric+np.array(r['shift_m'])
  expected=np.stack(((q-origin)@tan,(q-origin)@vert),axis=1)
  err=max(err,float(np.max(abs(actual-expected))))
  edge_error=max(edge_error,float(np.max(abs(np.linalg.norm(q-np.roll(q,1,axis=0),axis=1)-np.linalg.norm(metric-np.roll(metric,1,axis=0),axis=1)))))
  if vert[2]>.99:
   for vi,value in zip(p.vertices,metric):shared[(vi,mid)].append((tan,value))
 phase_errors=[]
 for (vi,mid),values in shared.items():
  period=np.array(manifest['panel_dimensions_m'][mid])
  for tan,value in values[1:]:
   ref_tan,ref=values[0]
   if np.dot(tan,ref_tan)>.9999:
    delta=value-ref;wrapped=delta-np.round(delta/period)*period
    phase_errors.append(float(np.max(abs(wrapped))))
 assert err<2e-6
 assert max(phase_errors,default=0)<.00001, 'Adjacent facade texture phases disagree'
 assert edge_error<.0002, 'Metric projection error exceeds 0.2 mm'
 materials=[]
 for mid in range(101,106):
  mat=m.materials[mid-1];imgs=[n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE']
  assert imgs and all(i.packed_file and list(i.size)==[N,N] for i in imgs)
  materials.append(mat.name)
 summary[name]={'faces':len(m.polygons),'geometry_ids_transforms_unchanged':True,'original_uv_preserved':True,
   'all_uv_inside_id_band':True,'max_uv_readback_error_m':err,'max_edge_projection_error_m':edge_error,
   'shared_coplanar_vertex_phase_max_m':max(phase_errors,default=0),
   'phase_samples_over_5mm':sum(e>.005 for e in phase_errors),
   'materials':materials,'packed_atlas':True}
assert hashlib.sha256(Path(manifest['source_blend']).read_bytes()).hexdigest()==manifest['source_sha256']
(out/'readback-qa.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary))

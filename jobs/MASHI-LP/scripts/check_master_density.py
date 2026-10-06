import bpy,json,math,numpy as np
from pathlib import Path
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001');rows=[]
for o in bpy.data.collections['MASTER_Revit_v001'].objects:
 me=o.data;uv=me.uv_layers['TD_1024_TEST'];td=[];bad=[];outside=[]
 for p in me.polygons:
  q=np.array([uv.data[i].uv for i in p.loop_indices]);a=abs(float(np.sum(q[:,0]*np.roll(q[:,1],-1)-q[:,1]*np.roll(q[:,0],-1))))*.5
  density=4096*math.sqrt(a/p.area) if p.area>1e-12 else 0;td.append(density)
  if not 512<=density<=1706:bad.append(p.index)
  if q.min()<.0077 or q.max()>.9923:outside.append(p.index)
 rows.append(dict(name=o.name,td_percentiles=np.percentile(td,[0,1,50,99,100]).tolist(),outside_512_1706=bad,outside_padded_tile=outside,uv_layer='TD_1024_TEST',texture_resolution_assumption=4096))
(out/'density-readback.json').write_text(json.dumps(dict(file=bpy.data.filepath,objects=rows,production_atlas=False),indent=2));print([(r['name'],len(r['outside_512_1706']),len(r['outside_padded_tile']),r['td_percentiles']) for r in rows])

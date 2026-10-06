import bpy,json,sys,math
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np

out=Path(sys.argv[sys.argv.index('--')+1]);result={}
for o in bpy.data.objects:
 if o.type!='MESH':continue
 v=np.array([o.matrix_world@x.co for x in o.data.vertices]);uv=o.data.uv_layers.active
 ids=defaultdict(list);angles=Counter();sizes=[]
 for f in o.data.polygons:
  q=v[list(f.vertices)];tex=np.array([uv.data[i].uv[:] for i in f.loop_indices])
  e=q[1]-q[0];normal=np.array(f.normal)
  if abs(normal[2])<.1:angles[round(math.degrees(math.atan2(normal[1],normal[0]))%180,1)]+=1
  edges=np.roll(q,-1,axis=0)-q
  edgeuv=np.roll(tex,-1,axis=0)-tex
  ids[f.material_index+1].append({'uv':tex.mean(0).tolist(),'span':np.ptp(q,axis=0).tolist(),'uvspan':np.ptp(tex,axis=0).tolist(),
                                'lengths':np.linalg.norm(edges,axis=1).tolist(),'uvlengths':np.linalg.norm(edgeuv,axis=1).tolist()})
 stats={}
 for mid,rows in ids.items():
  img=next(n.image for n in o.data.materials[mid-1].node_tree.nodes if n.type=='TEX_IMAGE')
  pix=np.array(img.pixels[:]).reshape(img.size[1],img.size[0],4)
  colors=[]
  for row in rows:
   u,w=row['uv'];colors.append(tuple(np.round(pix[int(w*img.size[1])%img.size[1],int(u*img.size[0])%img.size[0],:3],3)))
  stats[mid]={'faces':len(rows),'uvcentroid_range':[np.min([r['uv'] for r in rows],axis=0).tolist(),np.max([r['uv'] for r in rows],axis=0).tolist()],
              'colors':[{'rgb':list(c),'count':n} for c,n in Counter(colors).most_common(4)],
              'max_xyz_span':np.max([r['span'] for r in rows],axis=0).tolist()}
 result[o.name]={'normal_angles':angles.most_common(8),'ids':stats,'matrix':list(map(list,o.matrix_world))}
(out/'uv-probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))

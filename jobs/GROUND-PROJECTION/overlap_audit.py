import json, numpy as np, shapely
from pathlib import Path
from shapely import Polygon, STRtree
root=Path(__file__).parent/'outputs/v001'
d=np.load(root/'Ground_arrays.npz');v=d['v'];f=d['f'];m=d['mat']
p=np.array([Polygon(v[t,:2]) for t in f]);tree=STRtree(p)
pairs=tree.query(p,predicate='intersects');pairs=pairs[:,pairs[0]<pairs[1]]
ix=shapely.intersection(p[pairs[0]],p[pairs[1]]);a=shapely.area(ix);k=a>0.001
out=[{'faces':[int(i),int(j)],'ids':[int(m[i]+1),int(m[j]+1)],'area':float(ar)} for (i,j),ar in zip(pairs[:,k].T,a[k])]
out.sort(key=lambda x:-x['area'])
(root/'ground_overlaps.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'count':len(out),'same_id':sum(x['ids'][0]==x['ids'][1] for x in out),'top':out[:12]},indent=2))

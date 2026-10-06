import json,numpy as np,shapely
from pathlib import Path
from shapely.ops import triangulate
from shapely.geometry import Polygon
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011');desc=json.loads((out/'facade-sections.json').read_text());levels=desc['levels'];sections={k:shapely.from_wkt(v) for k,v in desc['sections'].items()}
result=[]
def addshape(shape,z,up,mat):
 for t in shapely.constrained_delaunay_triangles(shape).geoms:
  if t.area<1e-7 or not shape.covers(t.representative_point()):continue
  pts=[[x,y,z] for x,y in list(t.exterior.coords)[:-1]]
  n=np.cross(np.array(pts[1])-pts[0],np.array(pts[2])-pts[0])
  if (n[2]>0)!=up:pts.reverse()
  result.append({'points':pts,'uv':[[p[0]/4.5,p[1]/4.5] for p in pts],'material':mat})
for i,z in enumerate(levels):
 belt=sections[f'{i}_belt'];previous=sections[f'{max(0,i-1)}_window'];window=sections[f'{i}_window']
 addshape(belt.difference(previous),z,False,'<auto>26')
 addshape(belt.difference(window),z+1,True,'<auto>26')
(out/'exterior-ledge-faces.json').write_text(json.dumps(result),encoding='utf-8')
print('Exterior ledge triangles',len(result),'interior areas excluded')

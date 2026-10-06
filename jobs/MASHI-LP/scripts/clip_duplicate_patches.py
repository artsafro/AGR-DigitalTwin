import json
from pathlib import Path
import numpy as np
from shapely.geometry import shape,Polygon,mapping
from shapely.ops import unary_union
out=Path(__file__).resolve().parents[1]/'outputs/model-v002'
patches=json.loads((out/'candidate-patches.json').read_text());accepted=[];removed=0
def polys(g):
    if g.geom_type=='Polygon':return [g]
    return [p for x in getattr(g,'geoms',[]) for p in polys(x)]
for patch in patches:
    n=np.array(patch['normal']);origin=np.array(patch['origin']);u=np.array(patch['u']);v=np.array(patch['v'])
    poly=shape(patch['polygon']);covers=[]
    current_points=origin+u*np.array(poly.exterior.coords)[:,0,None]+v*np.array(poly.exterior.coords)[:,1,None]
    for other in accepted:
        if abs(n@other['_n'])<.999999:continue
        da=np.max(np.abs((other['_points']-origin)@n))
        db=np.max(np.abs((current_points-np.array(other['origin']))@other['_n']))
        if min(da,db)>.003:continue
        rings=[]
        for ring in other['polygon']['coordinates']:
            pts=np.array(other['origin'])+np.array(other['u'])*np.array(ring)[:,0,None]+np.array(other['v'])*np.array(ring)[:,1,None]
            rings.append(np.column_stack(((pts-origin)@u,(pts-origin)@v)))
        projected=Polygon(rings[0],rings[1:])
        if poly.intersects(projected):covers.append(projected)
    if covers:
        clipped=poly.difference(unary_union(covers).buffer(.001,join_style=2));removed+=poly.area-clipped.area
    else:clipped=poly
    for part in polys(clipped):
        if part.area<.03:continue
        row=dict(patch);row['polygon']=mapping(part);row['area']=part.area
        row['_points']=origin+u*np.array(part.exterior.coords)[:,0,None]+v*np.array(part.exterior.coords)[:,1,None]
        row['_n']=n;accepted.append(row)
for p in accepted:p.pop('_points');p.pop('_n')
(out/'candidate-patches.json').write_text(json.dumps(accepted),encoding='utf-8')
print('Clipped coincident imported surfaces',round(removed,5),'m2; patches',len(accepted))

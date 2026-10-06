import json
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union,triangulate
p=Path('jobs/GLB-NPM/outputs/clearance-ab-v005')
fs=json.loads((p/'faces-readback.json').read_text());fs=[f for f in fs if f['object']=='A_<auto>58']
pts=np.concatenate([f['points'] for f in fs]);z0,z1=pts[:,2].min(),pts[:,2].max()
polys=[]
for f in fs:
    q=np.array(f['points'])
    if q[:,2].max()-q[:,2].min()<1e-5:
        poly=Polygon(q[:,:2])
        if poly.area>1e-8:polys.append(poly)
union=unary_union(polys).buffer(.00005,join_style=2).buffer(-.00005,join_style=2).simplify(.0005,preserve_topology=True)
pieces=list(union.geoms) if union.geom_type=='MultiPolygon' else [union]
verts=[];faces=[]
def quad(vs):
    i=len(verts);verts.extend(vs);faces.append(list(range(i,i+4)))
for poly in pieces:
    assert not poly.interiors
    tris=[t for t in triangulate(poly) if poly.covers(t.representative_point()) and t.difference(poly).area<1e-9]
    for tr in tris:
        v=np.array(list(tr.exterior.coords)[:3]);c=v.mean(0)
        for k in range(3):
            xy=[v[k],(v[k]+v[(k+1)%3])/2,c,(v[k]+v[(k-1)%3])/2]
            quad([(x,y,z1) for x,y in xy]);quad([(x,y,z0) for x,y in reversed(xy)])
    ring=list(poly.exterior.coords)
    for a,b in zip(ring,ring[1:]):
        mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
        for x,y in [(a,mid),(mid,b)]:quad([(x[0],x[1],z0),(y[0],y[1],z0),(y[0],y[1],z1),(x[0],x[1],z1)])
(p/'misc-union.json').write_text(json.dumps({'vertices':verts,'faces':faces,'source':'A_<auto>58','simplification_m':.0005}),encoding='utf-8')
print(len(pieces),len(faces))

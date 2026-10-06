"""Plan measured planar extensions, removing projected existing LP coverage."""
import json,math
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,mapping
from shapely.ops import unary_union
from shapely import make_valid,set_precision

out=Path(__file__).resolve().parents[1]/'outputs/model-v002'
planes=json.loads((out/'source-planes.json').read_text())
lp=json.loads((out/'lp-geometry.json').read_text())
raw=json.loads((out/'raw-triangles.json').read_text())
raw_points=np.array([t['coords'] for t in raw]);raw_normals=np.array([t['normal'] for t in raw]);raw_centers=raw_points.mean(axis=1)
lpfaces=[]
for o in lp:
    vv=np.array(o['vertices'])
    for ids,normal in zip(o['faces'],o['normals']):
        lpfaces.append((vv[ids],np.array(normal),o['name']))
def clean(poly):
    return set_precision(make_valid(poly),.001)
def polygons(g):
    if g.geom_type=='Polygon':return [g]
    return [p for x in getattr(g,'geoms',[]) for p in polygons(x)]
patches=[];processed=[]
for source in planes:
    rough=np.array([v for f in source['faces'] for v in f['coords']]);rc=rough.mean(axis=0)
    roof_stair=13<rc[0]<33 and -33<rc[1]<-23 and 31<rc[2]<37
    min_area=.035 if roof_stair else .3
    if source['area']<(.06 if roof_stair else .6):continue
    n=np.array(source['normal'],float);n/=np.linalg.norm(n)
    # Floor undersides and underground interior are outside the external-shell task.
    if n[2]<-.1:continue
    coords=np.array([v for f in source['faces'] for v in f['coords']])
    if coords[:,2].max()<-.1:continue
    d=float(np.mean(coords@n));origin=n*d
    if any(abs(n@pn)>.9999999 and abs(d-(pd if n@pn>0 else -pd))<.003 for pn,pd in processed):continue
    processed.append((n,d))
    if abs(n[2])<.01:u=np.array([-n[1],n[0],0]);u/=np.linalg.norm(u)
    else:u=np.cross([0,1,0],n);u/=np.linalg.norm(u)
    v=np.cross(n,u)
    def project(points):return np.column_stack(((points-origin)@u,(points-origin)@v))
    # Once a plane is established as exterior, recover complete source faces.
    # Centroid visibility alone must never cut triangle-shaped holes in a wall.
    eligible=(np.abs(raw_normals@n)>.999999)&(np.max(np.abs(raw_points@n-d),axis=1)<.003)
    names=set(f['object'] for f in source['faces'])
    ids=[int(i) for i in np.flatnonzero(eligible) if raw[int(i)]['object'] in names]
    exposed=unary_union([clean(Polygon(project(np.array(f['coords'])))) for f in source['faces']])
    src=unary_union([clean(Polygon(project(raw_points[i]))) for i in ids])
    if (n[2]>.1 and not roof_stair) or src.area>4*exposed.area:src=exposed
    covers=[];cover_names=set()
    for points,normal,name in lpfaces:
        if abs(n@normal)<.998:continue
        if np.max(np.abs(points@n-d))>.18:continue
        poly=clean(Polygon(project(points)))
        if not poly.is_empty and src.intersects(poly): covers.append(poly);cover_names.add(name)
    covered=unary_union(covers)
    remaining=src.difference(covered.buffer(.002,join_style=2)) if covers else src
    for poly in polygons(remaining):
        if poly.area<min_area:continue
        # Actual boundary contours only, not triangulation diagonals.
        poly=poly.simplify(.0005,preserve_topology=True)
        if poly.area<min_area:continue
        actual=np.array([origin+u*a+v*b for a,b in poly.exterior.coords]);center=actual.mean(axis=0)
        if center[2]<31 and not (center[0]<8 or center[1]>-33):continue
        patches.append({'plane_id':source['id'],'normal':n.tolist(),'origin':origin.tolist(),'u':u.tolist(),'v':v.tolist(),
            'area':poly.area,'source_area':src.area,'source_objects':sorted(set(f['object'] for f in source['faces'])),
            'covered_by':sorted(cover_names),'polygon':mapping(poly),
            'bounds_world':[actual.min(axis=0).tolist(),actual.max(axis=0).tolist()]})
patches.sort(key=lambda x:-x['area'])
for i,p in enumerate(patches):p['patch_id']=i
(out/'candidate-patches.json').write_text(json.dumps(patches),encoding='utf-8')
for p in patches[:80]:
    print(p['patch_id'],'plane',p['plane_id'],'area',round(p['area'],2),'n',p['normal'],'objects',p['source_objects'],'covered',p['covered_by'],'vertices',len(p['polygon']['coordinates'][0]),'holes',len(p['polygon']['coordinates'])-1,'bounds',[[round(x,2) for x in a] for a in p['bounds_world']])
print('TOTAL',len(patches),round(sum(p['area'] for p in patches),2))

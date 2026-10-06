"""Build editable, unshelled quad patches from measured planar outlines."""
import json,math
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,shape,box
from shapely import constrained_delaunay_triangles
from shapely.ops import unary_union

out=Path(__file__).resolve().parents[1]/'outputs/model-v002'
patches=json.loads((out/'candidate-patches.json').read_text())
def coords(poly):return list(poly.exterior.coords)[:-1]
def signed_area(q):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(q,q[1:]+q[:1]))/2
def merged_values(values,tol=.002):
    groups=[]
    for val in sorted(values):
        if groups and val-groups[-1][-1]<tol:groups[-1].append(val)
        else:groups.append([val])
    return [sum(g)/len(g) for g in groups]
def make_quads(poly):
    points=coords(poly)
    if not poly.interiors and len(points)==4 and poly.area/poly.convex_hull.area>.999:
        return [points],'single_quad'
    rings=[points]+[list(r.coords)[:-1] for r in poly.interiors]
    axial=all(min(abs(a[0]-b[0]),abs(a[1]-b[1]))<.003 for ring in rings for a,b in zip(ring,ring[1:]+ring[:1]))
    if axial:
        xs=merged_values([p[0] for r in rings for p in r]);ys=merged_values([p[1] for r in rings for p in r])
        result=[]
        for x0,x1 in zip(xs,xs[1:]):
            for y0,y1 in zip(ys,ys[1:]):
                cell=box(x0,y0,x1,y1)
                if poly.covers(cell.centroid):result.append([(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
        if unary_union([Polygon(q) for q in result]).symmetric_difference(poly).area<=max(.005,poly.area*.0001):
            return result,'edge_strips_connect'
    # Irregular roof/return outline: merge triangulation diagonals, then perform
    # a planar face split (no smoothing) to retain only quads with shared edges.
    tris=list(constrained_delaunay_triangles(poly).geoms)
    edges={}
    for i,t in enumerate(tris):
        cc=coords(t)
        for a,b in zip(cc,cc[1:]+cc[:1]):edges.setdefault(tuple(sorted((a,b))),[]).append(i)
    options=[]
    for edge,inds in edges.items():
        if len(inds)!=2:continue
        a,b=inds;p=tris[a].union(tris[b])
        if p.geom_type=='Polygon' and len(coords(p))==4 and p.area/p.convex_hull.area>.99999:
            lens=[math.dist(x,y) for x,y in zip(coords(p),coords(p)[1:]+coords(p)[:1])]
            options.append((min(lens)/max(lens),a,b,p))
    used=set();base=[]
    for _,a,b,p in sorted(options,key=lambda x:-x[0]):
        if a not in used and b not in used:used.update([a,b]);base.append(coords(p))
    base.extend(coords(t) for i,t in enumerate(tris) if i not in used)
    if all(len(p)==4 for p in base):return base,'outline_quad_pairing'
    result=[]
    for p in base:
        center=tuple(np.mean(p,axis=0));mids=[tuple((np.array(a)+b)/2) for a,b in zip(p,p[1:]+p[:1])]
        for i,point in enumerate(p):result.append([point,mids[i],center,mids[i-1]])
    return result,'irregular_outline_quad_split'
meshes=[];stats={}
for patch in patches:
    poly=shape(patch['polygon']);quads,method=make_quads(poly)
    origin=np.array(patch['origin']);u=np.array(patch['u']);v=np.array(patch['v'])
    vertices=[];faces=[];lookup={}
    for q in quads:
        if signed_area(q)<0:q=list(reversed(q))
        if Polygon(q).area<1e-7:continue
        ids=[]
        for a,b in q:
            point=origin+u*a+v*b;key=tuple(np.round(point,6))
            if key not in lookup:lookup[key]=len(vertices);vertices.append(point.tolist())
            ids.append(lookup[key])
        if len(set(ids))==4:faces.append(ids)
    if not faces:continue
    reconstructed=unary_union([Polygon(q) for q in quads])
    error=reconstructed.symmetric_difference(poly).area
    if error>max(.015,poly.area*.0005):
        raise RuntimeError(f"Contour changed patch{patch['patch_id']} area error{error}")
    center=np.mean(vertices,axis=0)
    role='roof' if patch['normal'][2]>.2 and center[2]>30 else 'platform' if patch['normal'][2]>.2 else 'facade'
    if patch['source_objects']==['MultiMat_5'] and abs(patch['normal'][2])<.1:role='window_field'
    meshes.append({'name':f"LP_Add_{role}_{patch['patch_id']:03d}",'vertices':vertices,'faces':faces,
        'source_plane':patch['plane_id'],'patch_id':patch['patch_id'],'source_objects':patch['source_objects'],
        'area':poly.area,'method':method,'contour_symdiff_m2':error,'role':role})
    stats[method]=stats.get(method,0)+len(faces)
(out/'new-meshes.json').write_text(json.dumps(meshes),encoding='utf-8')
print('MESHES',len(meshes),'QUADS',sum(len(m['faces']) for m in meshes),'METHODS',stats)

import json,time,collections
from pathlib import Path
import numpy as np
import shapely as sh
from shapely import Polygon, LineString, STRtree
from shapely.ops import split
ROOT=Path(__file__).parent/'outputs/v001';t0=time.time()
def log(s):print(f'{time.time()-t0:.1f}s {s}',flush=True)
d=np.load(ROOT/'partition.npz',allow_pickle=True)
cells=sh.from_wkb(d['wkb']);owners=d['owners'];planes=d['planes'];chosen=d['chosen'];extra=set(d['extrapolated']);grid=float(d['grid'])
gd=np.load(ROOT/'Ground_arrays.npz');gm=gd['mat']
rd=np.load(ROOT/'Relef_arrays.npz');rt=rd['v'][rd['f'][d['relief_ids']]]
rp=np.array([Polygon(t[:,:2]) for t in rt]);rsearch=STRtree(rp)
# Repair the small set where upper terrain planes cross inside an overlay cell.
records=[]
for i,poly in enumerate(cells):
    pieces=[poly]
    if i in set(d['crossing']):
        rs=rsearch.query(poly.representative_point(),predicate='intersects')
        for k,a in enumerate(rs):
            for b in rs[k+1:]:
                eq=planes[a]-planes[b];n=eq[:2];norm=np.linalg.norm(n)
                if norm<1e-12:continue
                ctr=np.array(poly.centroid.coords[0]);base=ctr-n*(np.dot(n,ctr)+eq[2])/(norm*norm)
                vec=np.array([-n[1],n[0]])/norm*50000
                line=LineString([base-vec,base+vec])
                pieces=[q for p in pieces for q in sh.get_parts(split(p,line)) if q.area>1e-10]
    for p in pieces:
        ch=int(chosen[i])
        if len(pieces)>1:
            xy=np.array(p.representative_point().coords[0]);rs=rsearch.query(p.representative_point(),predicate='intersects')
            if len(rs):ch=int(rs[np.argmax(planes[rs,:2]@xy+planes[rs,2])])
        # Same-ID source overlaps can be consolidated without changing any material contour.
        matowners={}
        for f in owners[i]:matowners.setdefault(int(gm[f]),int(f))
        records.append((p,ch,matowners,i in extra))
log(f'records {len(records)}')
# Global noding already provides matching outlines; new crossing cuts are noded again.
# Dissolve only cells with the same original ground face, terrain plane and material.
groups=collections.defaultdict(list);meta={}
for p,ch,mos,ext in records:
    for mat,owner in mos.items():
        key=(owner,ch,ext)
        groups[key].append(p);meta[key]=mat
merged=[]
for key,polys in groups.items():
    u=sh.union_all(polys)
    for p in sh.get_parts(u):
        if p.geom_type=='Polygon' and p.area>1e-10:merged.append((p,key,meta[key]))
log(f'merged {len(merged)}')
# Node all remaining boundaries, including endpoints of crossing-plane cuts.
lines=sh.union_all([p.boundary for p,_,_ in merged],grid_size=grid)
points=np.unique(sh.get_coordinates(lines),axis=0)
ptree=STRtree(sh.points(points))
log(f'boundary points {len(points)}')
vertices=[];faces=[];mats=[];source_faces=[];extrap=[];lookup={};wall_inputs=collections.defaultdict(list)
def vertex(x,y,z):
    # Shared float-safe lattice; conservative 1 mm in source world units.
    key=(round(float(x)/grid),round(float(y)/grid),round(float(z)/grid))
    if key not in lookup:
        lookup[key]=len(vertices);vertices.append(tuple(c*grid for c in key))
    return lookup[key]
def emit(poly,key,mat):
    owner,ch,ext=key;plane=planes[ch]
    # Concave/holed regions are triangulated before corner-to-centre quad construction.
    if poly.interiors or poly.convex_hull.area-poly.area>1e-5:
        parts=sh.get_parts(sh.constrained_delaunay_triangles(poly))
    else:parts=[poly]
    for p in parts:
        p=sh.orient_polygons(p)
        raw=np.array(p.exterior.coords)[:-1];ring=[]
        for a,b in zip(raw,np.roll(raw,-1,axis=0)):
            edge=LineString([a,b]);ids=ptree.query(edge.buffer(grid*1.1))
            delta=b-a;ll=np.dot(delta,delta)
            if ll<1e-18:continue
            t=(points[ids]-a)@delta/ll
            dist=np.abs(delta[0]*(points[ids,1]-a[1])-delta[1]*(points[ids,0]-a[0]))/np.sqrt(ll)
            good=(t>1e-7)&(t<1-1e-7)&(dist<grid*0.71)
            coords=[a]+[points[j] for j in ids[good][np.argsort(t[good])]]
            ring.extend(coords)
        if len(ring)<3:continue
        xy=np.array(ring);center=np.array(p.centroid.coords[0]);z=lambda q:float(q@plane[:2]+plane[2])
        ci=vertex(*center,z(center))
        vi=[vertex(*q,z(q)) for q in xy]
        mids=(xy+np.roll(xy,-1,axis=0))*.5
        mi=[vertex(*q,z(q)) for q in mids]
        for k in range(len(vi)):
            f=[vi[k],mi[k],ci,mi[k-1]]
            if len(set(f))<4:continue
            faces.append(f);mats.append(mat);source_faces.append(owner);extrap.append(ext)
            for a,b in [(vi[k],mi[k]),(mi[k],vi[(k+1)%len(vi)])]:
                va,vb=vertices[a],vertices[b]
                ka=tuple(round(v/grid) for v in va[:2]);kb=tuple(round(v/grid) for v in vb[:2])
                if ka!=kb:wall_inputs[tuple(sorted((ka,kb)))].append((a,b,mat,owner,ext))
for i,(p,k,m) in enumerate(merged):
    emit(p,k,m)
    if i%10000==0:log(f'quad patches {i}/{len(merged)} faces {len(faces)}')
log(f'top quads {len(faces)} verts {len(vertices)}')
# Close height jumps with vertical quads. Material follows the higher surface.
walls=0;ambiguous=[]
for edge,items in wall_inputs.items():
    uniq={tuple(sorted((a,b))):(a,b,m,o,e) for a,b,m,o,e in items}
    vals=list(uniq.values())
    if len(vals)!=2:continue
    a,b,ma,oa,ea=vals[0];c,d,mb,ob,eb=vals[1]
    if np.linalg.norm(np.array(vertices[a][:2])-vertices[c][:2])>grid:
        c,d=d,c
    za=(vertices[a][2]+vertices[b][2])*.5;zb=(vertices[c][2]+vertices[d][2])*.5
    if abs(za-zb)<grid*2:continue
    f=[a,c,d,b]
    if len(set(f))<4:continue
    faces.append(f);mats.append(ma if za>zb else mb);source_faces.append(oa if za>zb else ob);extrap.append(ea or eb);walls+=1
log(f'walls {walls}; all faces {len(faces)}')
np.savez_compressed(ROOT/'quad_mesh.npz',vertices=np.array(vertices),faces=np.array(faces,dtype=np.int32),materials=np.array(mats,dtype=np.int16),source_faces=np.array(source_faces,dtype=np.int32),extrapolated=np.array(extrap),top_faces=len(faces)-walls)
(ROOT/'mesh_construction.json').write_text(json.dumps({'vertices':len(vertices),'quads':len(faces),'vertical_wall_quads':walls,'merged_patches':len(merged),'coordinate_grid':grid,'seconds':time.time()-t0},indent=2))
log('saved')


"""Cut at repeat boundaries; retain the supplied image and metric scale."""
import json, math
from pathlib import Path
import numpy as np
from collections import defaultdict
root=Path(__file__).resolve().parents[1]/'outputs'
d=json.loads((root/'source.json').read_text());plan=json.loads((root/'plan.json').read_text())
v=np.array(d['vertices']);uvs=plan['metric_uv'];scale=1500/4096
polys=[];edge_splits=defaultdict(dict);tris=defaultdict(list)
for tri in d['triangles']:tris[tri['face']].append(tri['vertices'])
def key(p):return tuple(np.round(p,6))
def clip(poly,axis,value,positive):
    out=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        da=(a[1][axis]-value)*(1 if positive else -1);db=(b[1][axis]-value)*(1 if positive else -1)
        ina=da>=-1e-10;inb=db>=-1e-10
        if ina:out.append(a)
        if ina!=inb:
            f=da/(da-db);out.append((a[0]+f*(b[0]-a[0]),a[1]+f*(b[1]-a[1])))
    clean=[]
    for p in out:
        if not clean or np.linalg.norm(p[0]-clean[-1][0])>1e-7:clean.append(p)
    if len(clean)>1 and np.linalg.norm(clean[0][0]-clean[-1][0])<1e-7:clean.pop()
    return clean
for fi,face in enumerate(d['faces']):
    xy=np.array(uvs[fi])*scale;p=[(v[a].copy(),b.copy()) for a,b in zip(face,xy)]
    cross=[]
    for i in range(len(xy)):
        a=xy[(i+1)%len(xy)]-xy[i];bb=xy[(i+2)%len(xy)]-xy[(i+1)%len(xy)];cross.append(a[0]*bb[1]-a[1]*bb[0])
    n=np.array(d['normals'][fi]); nonplanar=np.ptp(v[face]@n)>1e-5
    concave=min(cross)<-1e-9 and max(cross)>1e-9
    chunks=[p]
    if concave or nonplanar:
        chunks=[]
        for tri in tris[fi]:
            coords=np.array([xy[face.index(a)] for a in tri])
            if nonplanar:
                q=v[tri];a=q[1]-q[0];a/=np.linalg.norm(a);normal=np.cross(a,q[2]-q[0]);normal/=np.linalg.norm(normal);bb=np.cross(normal,a)
                coords=np.column_stack(((q-q[0])@a,(q-q[0])@bb))*scale+xy[face.index(tri[0])]
            chunks.append([(v[a].copy(),c.copy()) for a,c in zip(tri,coords)])
        xy=np.array([c for chunk in chunks for _,c in chunk])
    for axis in (0,1):
        for cut in range(math.floor(xy[:,axis].min())+1,math.ceil(xy[:,axis].max()-1e-9)):
            new=[]
            for poly in chunks:
                for positive in (False,True):
                    c=clip(poly,axis,cut,positive)
                    if len(c)>=3 and abs(sum(a[1][0]*b[1][1]-b[1][0]*a[1][1] for a,b in zip(c,c[1:]+c[:1])))>1e-12:new.append(c)
            chunks=new
    for c in chunks:
        shift=np.floor(np.mean([a[1] for a in c],axis=0))
        polys.append(([(a,b-shift) for a,b in c],fi))
        for point,xy in c:
            for a,b in zip(face,face[1:]+face[:1]):
                e=v[b]-v[a];den=e@e
                if den<1e-16:continue
                t=(point-v[a])@e/den
                if -1e-7<t<1+1e-7 and np.linalg.norm(point-(v[a]+t*e))<2e-6:
                    ek=tuple(sorted((key(v[a]),key(v[b]))));edge_splits[ek][key(point)]=point
# Reconcile new points across original shared boundaries before quad subdivision.
outv=[];outf=[];outuv=[];parents=[];lookup={}
def vert(p):
    k=key(p)
    if k not in lookup:lookup[k]=len(outv);outv.append(p.tolist())
    return lookup[k]
for poly,fi in polys:
    expanded=[];face=d['faces'][fi]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        candidates=[];e=b[0]-a[0];den=e@e
        if den<1e-14:continue
        for ia,ib in zip(face,face[1:]+face[:1]):
            oe=v[ib]-v[ia];od=oe@oe
            if od<1e-16:continue
            if all(np.linalg.norm(x[0]-(v[ia]+((x[0]-v[ia])@oe/od)*oe))<2e-6 for x in (a,b)):
                ek=tuple(sorted((key(v[ia]),key(v[ib]))))
                for p in edge_splits[ek].values():
                    t=(p-a[0])@e/den
                    if 1e-6<t<1-1e-6:candidates.append((t,(p,a[1]+t*(b[1]-a[1]))))
        expanded.append(a)
        expanded.extend(x for _,x in sorted(candidates,key=lambda x:x[0]))
    clean=[]
    for x in expanded:
        if not clean or np.linalg.norm(x[0]-clean[-1][0])>4e-6:clean.append(x)
    if len(clean)>1 and np.linalg.norm(clean[0][0]-clean[-1][0])<=4e-6:clean.pop()
    expanded=clean
    center=(np.mean([a[0] for a in expanded],axis=0),np.mean([a[1] for a in expanded],axis=0))
    mids=[((a[0]+b[0])/2,(a[1]+b[1])/2) for a,b in zip(expanded,expanded[1:]+expanded[:1])]
    for i,a in enumerate(expanded):
        q=[a,mids[i],center,mids[i-1]]
        ids=[vert(x[0]) for x in q]
        if len(set(ids))<4:continue
        outf.append(ids);outuv.append([x[1].tolist() for x in q]);parents.append(fi)
result={'vertices':outv,'faces':outf,'uv':outuv,'parents':parents,'source':d['name'],'density':1500,'texture_modified':False,'unresolved_phase_edges':plan['report']['conflicts']}
(root/'build.json').write_text(json.dumps(result),encoding='utf-8')
print(json.dumps({'vertices':len(outv),'quads':len(outf),'phase_edges':len(result['unresolved_phase_edges']),'uv_min':np.min(outuv),'uv_max':np.max(outuv)}))

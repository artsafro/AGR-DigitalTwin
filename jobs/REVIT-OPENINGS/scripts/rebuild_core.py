"""Rebuild measured rectilinear solids; no arbitrary dimensions or remesh grid."""
import json
from pathlib import Path
from collections import Counter
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/library-v001'
OUT.mkdir(parents=True,exist_ok=True)

def components(t):
    p=list(range(len(t['vertices'])))
    def find(i):
        while p[i]!=i:p[i]=p[p[i]];i=p[i]
        return i
    for f in t['faces']:
        for i in f[1:]:p[find(i)]=find(f[0])
    groups={}
    for fi,f in enumerate(t['faces']):groups.setdefault(find(f[0]),[]).append(fi)
    return list(groups.values())

def axis_aligned(v,faces):
    for f in faces:
        for i in range(1,len(f)-1):
            n=np.cross(v[f[i]]-v[f[0]],v[f[i+1]]-v[f[0]])
            length=np.linalg.norm(n)
            if length>1e-12 and max(abs(n))/length<0.999999:return False
    return True

def axes_for(v):
    # 0.01mm coordinate normalization, below FBX source precision at large coordinates.
    return [np.unique(np.round(v[:,a],5)) for a in range(3)]

def volume(v,faces,axes):
    """Signed ray crossings give union occupancy including overlapping source solids."""
    v=np.round(v,5)
    xs,ys,zs=axes
    if min(map(len,axes))<2:raise ValueError('Zero thickness surface')
    x=(xs[:-1]+xs[1:])/2+np.diff(xs)*0.00000123
    z=(zs[:-1]+zs[1:])/2+np.diff(zs)*0.00000234
    y=(ys[:-1]+ys[1:])/2
    X,Z=np.meshgrid(x,z,indexing='ij')
    winding=np.zeros((len(x),len(y),len(z)),dtype=np.int16)
    for f in faces:
        for j in range(1,len(f)-1):
            tri=v[[f[0],f[j],f[j+1]]];a,b,c=tri
            n=np.cross(b-a,c-a)
            if abs(n[1])<1e-12:continue
            den=(b[2]-c[2])*(a[0]-c[0])+(c[0]-b[0])*(a[2]-c[2])
            if abs(den)<1e-16:continue
            u=((b[2]-c[2])*(X-c[0])+(c[0]-b[0])*(Z-c[2]))/den
            w=((c[2]-a[2])*(X-c[0])+(a[0]-c[0])*(Z-c[2]))/den
            mask=(u>=0)&(w>=0)&(u+w<1)
            hit=u*a[1]+w*b[1]+(1-u-w)*c[1]
            winding+=mask[:,None,:]*(y[None,:,None]>hit[:,None,:])*int(np.sign(n[1]))
    return winding!=0

def surface(occ,axes):
    vertices=[];faces=[];index={}
    def vi(q):
        k=tuple(q)
        if k not in index:index[k]=len(vertices);vertices.append([float(axes[a][q[a]]) for a in range(3)])
        return index[k]
    # All surface cells share lattice vertices. No T-junctions, no internal faces.
    cycles=[[(0,0,0),(0,0,1),(0,1,1),(0,1,0)],
            [(1,0,0),(1,1,0),(1,1,1),(1,0,1)],
            [(0,0,0),(1,0,0),(1,0,1),(0,0,1)],
            [(0,1,0),(0,1,1),(1,1,1),(1,1,0)],
            [(0,0,0),(0,1,0),(1,1,0),(1,0,0)],
            [(0,0,1),(1,0,1),(1,1,1),(0,1,1)]]
    for a in range(3):
        for side in range(2):
            neigh=np.zeros_like(occ)
            src=[slice(None)]*3;dst=[slice(None)]*3
            src[a]=slice(None,-1) if side==0 else slice(1,None)
            dst[a]=slice(1,None) if side==0 else slice(None,-1)
            neigh[tuple(dst)]=occ[tuple(src)]
            for q in np.argwhere(occ&~neigh):
                faces.append([vi(q+np.array(d)) for d in cycles[a*2+side]])
    return vertices,faces

def rebuild(t):
    v=np.array(t['vertices']);groups=components(t);parts=[];details=[];fallback=[]
    for ci,fis in enumerate(groups):
        faces=[t['faces'][fi] for fi in fis];ids=sorted(set(i for f in faces for i in f));cv=v[ids]
        dims=np.ptp(cv,axis=0)
        if t['category'] in ['WINDOW','DOOR'] and max(dims)<0.4:
            details.append({'component':ci,'faces':fis});continue
        panel=(t['category']=='PANEL' or (len(ids)==8 and dims[0]>.12 and dims[2]>.12 and dims[1]<=.03501))
        role='PANEL' if panel else ('MULLION' if t['category']=='MULLION' else 'FRAME_LEAF')
        if t['category']=='PANEL':
            role='GLASS' if any(k in t['source'].lower() for k in ['стекл','cтекл']) else 'OPAQUE_PANEL'
        elif panel:role='GLASS_CANDIDATE'
        if not axis_aligned(v,faces):
            fallback.append({'component':ci,'role':role,'faces':fis,'reason':'non_rectilinear_geometry'})
            continue
        ax=axes_for(cv)
        if min(map(len,ax))<2:
            fallback.append({'component':ci,'role':role,'faces':fis,'reason':'zero_thickness'})
            continue
        occ=volume(v,faces,ax)
        if not occ.any():
            fallback.append({'component':ci,'role':role,'faces':fis,'reason':'no_closed_volume'})
            continue
        vv,ff=surface(occ,ax)
        parts.append({'component':ci,'role':role,'vertices':vv,'faces':ff,
                      'source_faces':fis,'source_dimensions':dims.tolist(),
                      'grid_shape':list(occ.shape),'method':'measured_coordinate_solid_reconstruction'})
    return dict(id=t['id'],category=t['category'],source=t['source'],family_hint=t['family_hint'],
                instances=t['instances'],dimensions=t['dimensions'],raw_ids=t['raw_ids'],
                parts=parts,details=details,fallback=fallback,
                material_status='SOURCE_HAS_NO_MATERIALS',visual_acceptance='pending')

if __name__=='__main__':
    types=json.loads((ROOT/'outputs/source-v001/types.json').read_text(encoding='utf-8'))
    result=[rebuild(t) for t in types]
    (OUT/'rebuilt-core.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'types':len(result),'parts':sum(len(t['parts']) for t in result),
                      'fallback':dict(Counter(t['category'] for t in result if t['fallback'])),
                      'details':sum(len(t['details']) for t in result),
                      'faces':sum(len(p['faces']) for t in result for p in t['parts'])}))

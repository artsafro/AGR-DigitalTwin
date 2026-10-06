"""Conforming refinement of the ORIGINAL ground topology, vertical projection in Blender.
All triangulated construction patches are converted to three genuine quads.
"""
import bpy, json, time, collections
import numpy as np
from pathlib import Path
from mathutils.bvhtree import BVHTree
from mathutils import Vector
ROOT=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION/outputs/v002');ROOT.mkdir(parents=True,exist_ok=True)
SRC=ROOT.parent/'v001';t0=time.time()
def log(s):print(f'{time.time()-t0:.1f}s {s}',flush=True)
bpy.ops.wm.open_mainfile(filepath=str(SRC/'source_import.blend'))
gd=np.load(SRC/'Ground_arrays.npz');rd=np.load(SRC/'Relef_arrays.npz')
rv=rd['v'];rf=rd['f'];rt=rv[rf]
n=np.cross(rt[:,1]-rt[:,0],rt[:,2]-rt[:,0]);nz=np.abs(n[:,2])/np.maximum(np.linalg.norm(n,axis=1),1e-30)
valid=nz>.001;rf=rf[valid];n=n[valid];rt=rt[valid]
planes=np.column_stack((-n[:,0]/n[:,2],-n[:,1]/n[:,2],np.einsum('ij,ij->i',n,rt[:,0])/n[:,2]))
bvh=BVHTree.FromPolygons(rv.tolist(),rf.tolist(),all_triangles=True)
nearids=np.flatnonzero(np.abs(n[:,2])/np.linalg.norm(n,axis=1)>.2)
flat=rv.copy();flat[:,2]=0
near=BVHTree.FromPolygons(flat.tolist(),rf[nearids].tolist(),all_triangles=True)
cache={};extra=set();top=float(rv[:,2].max()+100)
def height(x,y):
    key=(round(float(x),8),round(float(y),8))
    if key in cache:return cache[key]
    hit=bvh.ray_cast(Vector((x,y,top)),Vector((0,0,-1)))
    idx=hit[2]
    outside=idx is None
    if outside:idx=int(nearids[near.find_nearest(Vector((x,y,0)))[2]]);extra.add(key)
    p=planes[idx];z=float(p[0]*x+p[1]*y+p[2])
    cache[key]=(z,outside,idx);return cache[key]
verts=[(float(p[0]),float(p[1])) for p in gd['v']]
faces=[tuple(map(int,f)) for f in gd['f']];mats=list(map(int,gd['mat']));parents=list(range(len(faces)))
MAX_EDGE=120.;HEIGHT_ERROR=1.;MIN_EDGE=.5;MAX_TRIANGLES=240000
iteration=[]
for it in range(26):
    arr=np.array(verts);fa=np.array(faces);pts=arr[fa]
    lens=np.linalg.norm(np.roll(pts,-1,axis=1)-pts,axis=2);long=np.argmax(lens,axis=1);maxlen=lens.max(axis=1)
    select=maxlen>MAX_EDGE
    zv=np.array([height(*p)[0] for p in arr]);errors=np.zeros(len(faces))
    for j in np.flatnonzero(~select & (maxlen>MIN_EDGE)):
        p=pts[j];zs=zv[fa[j]];samples=np.vstack((p.mean(axis=0),(p+np.roll(p,-1,axis=0))*.5))
        expected=np.r_[zs.mean(),(zs+np.roll(zs,-1))*.5]
        actual=np.array([height(*q)[0] for q in samples]);errors[j]=np.max(np.abs(actual-expected))
    select|=(errors>HEIGHT_ERROR)&(maxlen>MIN_EDGE)
    row={'iteration':it,'triangles':len(faces),'selected':int(select.sum()),'max_sample_error':float(errors.max()),'max_edge':float(maxlen.max())};iteration.append(row);log(str(row))
    if not select.any() or len(faces)>MAX_TRIANGLES:break
    wanted=set()
    for j in np.flatnonzero(select):
        k=long[j];wanted.add(tuple(sorted((faces[j][k],faces[j][(k+1)%3]))))
    mids={}
    for a,b in sorted(wanted):
        mids[(a,b)]=len(verts);verts.append(tuple((arr[a]+arr[b])*.5))
    nf=[];nm=[];npid=[]
    for face,mat,parent in zip(faces,mats,parents):
        a,b,c=face;ab=mids.get(tuple(sorted((a,b))));bc=mids.get(tuple(sorted((b,c))));ca=mids.get(tuple(sorted((c,a))))
        count=sum(x is not None for x in (ab,bc,ca))
        if count==0:new=[face]
        elif count==3:new=[(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)]
        elif count==1:
            if ab is not None:new=[(a,ab,c),(ab,b,c)]
            elif bc is not None:new=[(b,bc,a),(bc,c,a)]
            else:new=[(c,ca,b),(ca,a,b)]
        else:
            if ca is None:new=[(b,bc,ab),(a,ab,c),(ab,bc,c)]
            elif ab is None:new=[(c,ca,bc),(b,bc,a),(bc,ca,a)]
            else:new=[(a,ab,ca),(c,ca,b),(ca,ab,b)]
        nf.extend(new);nm.extend([mat]*len(new));npid.extend([parent]*len(new))
    faces,mats,parents=nf,nm,npid
# Original source edges are never moved or dissolved. Consistent midpoints join all patches.
arr=np.array(verts);edge_mid={};qfaces=[];qm=[];qp=[]
for face,mat,parent in zip(faces,mats,parents):
    a,b,c=face;tri=arr[list(face)]
    if np.linalg.det(np.array([tri[1]-tri[0],tri[2]-tri[0]]))<0:a,c=c,a
    ids=(a,b,c);mid=[]
    for i in range(3):
        u,w=ids[i],ids[(i+1)%3];key=tuple(sorted((u,w)))
        if key not in edge_mid:edge_mid[key]=len(verts);verts.append(tuple((arr[u]+arr[w])*.5))
        mid.append(edge_mid[key])
    cen=len(verts);verts.append(tuple(tri.mean(axis=0)))
    for i in range(3):qfaces.append((ids[i],mid[i],cen,mid[i-1]));qm.append(mat);qp.append(parent)
xy=np.array(verts);h=[height(*p) for p in xy];world=np.column_stack((xy,np.array([x[0] for x in h])))
# Weld exact coincident positions only, never a broad spatial merge.
unique,inv=np.unique(np.round(world,8),axis=0,return_inverse=True)
outside_vertices=np.array([x[1] for x in h]);outside_faces=outside_vertices[np.array(qfaces)].any(axis=1)
qfaces=inv[np.array(qfaces)];world=unique
np.savez_compressed(ROOT/'quad_mesh.npz',vertices=world,faces=qfaces,materials=np.array(qm),source_faces=np.array(qp),extrapolated=outside_faces,top_faces=len(qfaces))
report={'method':'original-topology conforming adaptive refinement then corner-to-centre quads; vertical Z projection','max_edge_construction':MAX_EDGE,'height_error_target':HEIGHT_ERROR,'minimum_refinement_edge':MIN_EDGE,'triangle_budget':MAX_TRIANGLES,'iterations':iteration,'vertices':len(world),'quads':len(qfaces),'height_cache_samples':len(cache),'extrapolated_samples':len(extra),'seconds':time.time()-t0,'sharp_steps':'continuous quad surface bridges discontinuities over refined narrow strips; not boolean-exact risers','source_overlaps':'retained as instructed'}
(ROOT/'construction.json').write_text(json.dumps(report,indent=2))
log('SAVED '+str((len(world),len(qfaces))))

"""Reconstruct exterior planar contours from Revit, never from user LP."""
import json,ast,math
from pathlib import Path
from collections import Counter
import numpy as np
from shapely.geometry import Polygon,mapping
from shapely.ops import unary_union
from shapely import make_valid,set_precision
base=Path(__file__).resolve().parents[1];out=base/'outputs/master-v001'
planes=json.loads((base/'outputs/model-v002/source-planes.json').read_text())
profile_planes=json.loads((out/'profile-planes.json').read_text())
profile_names={f['object'] for p in profile_planes for f in p['faces']}
for p in planes:p['faces']=[f for f in p['faces'] if f['object'] not in profile_names]
planes=[p for p in planes if p['faces']]+profile_planes
raw=json.loads((base/'outputs/model-v002/raw-triangles.json').read_text())
rp=np.array([f['coords'] for f in raw]);rn=np.array([f['normal'] for f in raw])
# Reuse pure contour-to-quad routines, without executing the LP patch job.
tree=ast.parse((base/'scripts/mesh_patches.py').read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef))],type_ignores=[]),'quad_routines','exec'))
def polygons(g):
 if g.geom_type=='Polygon':return [g]
 return [p for c in getattr(g,'geoms',[]) for p in polygons(c)]
def clean(p):return set_precision(make_valid(p),.001)
meshes=[];processed=[]
for source in planes:
 if source['area']<.0001:continue
 n=np.array(source['normal'],float);n/=np.linalg.norm(n)
 pts=np.array([p for f in source['faces'] for p in f['coords']]);d=float(np.mean(pts@n));origin=n*d
 if pts[:,2].max()<-.1:continue
 u=np.array([-n[1],n[0],0.]) if abs(n[2])<.01 else np.cross([0.,1,0],n);u/=np.linalg.norm(u);v=np.cross(n,u)
 def proj(q):return np.column_stack(((q-origin)@u,(q-origin)@v))
 eligible=[] if source.get('full_profile') else np.flatnonzero((np.abs(rn@n)>.999999)&(np.max(np.abs(rp@n-d),axis=1)<.002))
 occupied=Polygon()
 for name in sorted(set(f['object'] for f in source['faces'])):
  if name in ['MultiMat_5','Material #218','Material #39']:continue
  srcfaces=[f for f in source['faces'] if f['object']==name]
  exposed=unary_union([clean(Polygon(proj(np.array(f['coords'])))) for f in srcfaces])
  ids=[i for i in eligible if raw[int(i)]['object']==name]
  full=exposed if source.get('full_profile') else unary_union([clean(Polygon(proj(rp[i]))) for i in ids])
  # Recover triangles of the same visible panel, not buried floors/interiors.
  src=full if abs(n[2])<.1 else exposed
  if n[2]>.1 and np.mean(pts[:,2])>30:src=full
  if source.get('full_profile'):src=exposed
  src=src.difference(occupied);occupied=unary_union([occupied,src])
  for poly in polygons(src):
   if poly.area<.0001:continue
   poly=poly.simplify(.001,preserve_topology=True)
   try:quads,method=make_quads(poly)
   except Exception as e:print('SKIP',source['id'],str(e));continue
   verts=[];faces=[];lookup={}
   for q in quads:
    if signed_area(q)<0:q=q[::-1]
    if Polygon(q).area<1e-7:continue
    fi=[]
    for a,b in q:
     p=origin+u*a+v*b;key=tuple(np.round(p,6))
     if key not in lookup:lookup[key]=len(verts);verts.append(p.tolist())
     fi.append(lookup[key])
    if len(set(fi))==4:faces.append(fi)
   if not faces:continue
   center=np.mean(verts,axis=0)
   role='roof' if n[2]>.2 and center[2]>30 else 'body'
   if name=='Material #206':role='spandrels'
   meshes.append(dict(vertices=verts,faces=faces,source_plane=source['id'],source_object=name,source_faces=sorted(set(f['face'] for f in srcfaces)),normal=n.tolist(),area=poly.area,role=role,method=method))
(out/'contours.json').write_text(json.dumps(meshes))
print('contours',len(meshes),'quads',sum(len(m['faces']) for m in meshes),'sources',Counter(m['source_object'] for m in meshes))

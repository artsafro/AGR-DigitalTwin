import json,ast
from pathlib import Path
from collections import defaultdict
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely import make_valid,set_precision
base=Path(__file__).resolve().parents[1];out=base/'outputs/master-v001'
tree=ast.parse((base/'scripts/mesh_patches.py').read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef))],type_ignores=[]),'quad_routines','exec'))
def polys(g):
 if g.geom_type=='Polygon':return [g]
 return [p for c in getattr(g,'geoms',[]) for p in polys(c)]
rows=json.loads((out/'glass-panels.json').read_text());groups=defaultdict(list)
for p in rows:groups[tuple(p['normal'])+(p['d'],)].append(p)
meshes=[];rings=0
for key,panels in groups.items():
 n=np.array(key[:3]);n/=np.linalg.norm(n)
 pts=np.array([p for panel in panels for f in panel['faces'] for p in f['coords']]);origin=n*float(np.mean(pts@n))
 u=np.array([-n[1],n[0],0.]) if abs(n[2])<.01 else np.cross([0.,1,0],n);u/=np.linalg.norm(u);v=np.cross(n,u)
 def proj(q):return np.column_stack(((q-origin)@u,(q-origin)@v))
 glass=[];frames=[];sourceids=[]
 for panel in panels:
  poly=unary_union([set_precision(make_valid(Polygon(proj(np.array(f['coords'])))),.001) for f in panel['faces']]).simplify(.001,preserve_topology=True)
  if poly.is_empty:continue
  glass.append(poly);sourceids.extend(f['face'] for f in panel['faces'])
  for part in polys(poly):
   if part.area<.08:continue
   outer=part.buffer(.030,join_style=2);inner=part.buffer(-.010,join_style=2)
   frames.append(outer.difference(inner));rings+=1
 def add(poly,role,depth):
  for part in polys(poly):
   if part.area<1e-7:continue
   quads,method=make_quads(part);verts=[];faces=[];lookup={}
   def vert(a,b,h):
    p=origin+u*a+v*b+n*h;k=tuple(np.round(p,6))
    if k not in lookup:lookup[k]=len(verts);verts.append(p.tolist())
    return lookup[k]
   for q in quads:
    if signed_area(q)<0:q=q[::-1]
    if Polygon(q).area<1e-8:continue
    faces.append([vert(a,b,depth) for a,b in q])
   if role=='frames':
    # Edge extrude from the front ring: no interior caps or duplicate mullions.
    from collections import Counter
    ec=Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]))
    bounds=[(a,b) for f in faces for a,b in zip(f,f[1:]+f[:1]) if ec[tuple(sorted((a,b)))]==1]
    for ia,ib in bounds:
     a=np.array(verts[ia]);b=np.array(verts[ib]);pa=proj(a[None,:])[0];pb=proj(b[None,:])[0]
     faces.append([ib,ia,vert(*pa,-.045),vert(*pb,-.045)])
   meshes.append(dict(vertices=verts,faces=faces,role=role,source_object='MultiMat_5',source_faces=sorted(set(sourceids)),source_plane=-1,normal=n.tolist(),method='measured_glazing_outline_and_edge_extrusion',area=part.area))
 add(unary_union(glass),'glass',0.)
 if frames:add(unary_union(frames),'frames',.035)
(out/'windows.json').write_text(json.dumps(meshes))
(out/'window-design.json').write_text(json.dumps(dict(source_panels=len(rows),rings=rings,profile_width_m=.04,depth_m=.08,glass_recess_m=.035,glass_edge_capture_m=.01,outer_extension_m=.03,dimensions_status='simplified design using repeated LP_old profile dimensions; glazing position measured from Revit'),indent=2))
print('panels',len(rows),'rings',rings,'meshes',len(meshes),'quads',sum(len(m['faces']) for m in meshes))

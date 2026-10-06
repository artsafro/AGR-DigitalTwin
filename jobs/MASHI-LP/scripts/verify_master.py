import bpy,bmesh,json,numpy as np,hashlib
from pathlib import Path
from collections import Counter
from mathutils.kdtree import KDTree
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001')
def fingerprint(o):
 h=hashlib.sha256();h.update(str(tuple(tuple(r) for r in o.matrix_world)).encode())
 if o.type=='MESH':
  for p in o.data.vertices:h.update(str(tuple(p.co)).encode())
  for p in o.data.polygons:h.update(str((tuple(p.vertices),p.material_index)).encode())
  for layer in o.data.uv_layers:
   for u in layer.data:h.update(str(tuple(u.uv)).encode())
 return h.hexdigest()
expected=json.loads((out/'build-report.json').read_text())['original_signatures']
assert all(fingerprint(bpy.data.objects[n])==h for n,h in expected.items())
rows=[];geo=[]
for o in bpy.data.collections['MASTER_Revit_v001'].objects:
 me=o.data;bm=bmesh.new();bm.from_mesh(me);bm.verts.ensure_lookup_table();bm.faces.ensure_lookup_table()
 points=np.array([v.co for v in bm.verts]);tree=KDTree(len(points))
 for i,p in enumerate(points):tree.insert(p,i)
 tree.balance();ts=[]
 for e in bm.edges:
  if not e.is_boundary:continue
  a,b=[v.index for v in e.verts];delta=points[b]-points[a];den=delta@delta
  if den<1e-12:continue
  for co,i,d in tree.find_range((points[a]+points[b])/2,float(np.sqrt(den)/2+2e-5)):
   if i in [a,b]:continue
   t=(points[i]-points[a])@delta/den
   if 1e-5<t<1-1e-5 and np.linalg.norm(points[i]-points[a]-t*delta)<2e-5:ts.append([a,b,i])
 uv=np.array([tuple(p.uv) for p in me.uv_layers['TD_1024_TEST'].data]);lens=[e.calc_length() for e in bm.edges]
 coords=[tuple(round(x,6) for x in v.co) for v in bm.verts]
 duplicate=sum(c-1 for c in Counter(tuple(sorted(coords[v.index] for v in f.verts)) for f in bm.faces).values())
 deg=[f.index for f in bm.faces if f.calc_area()<1e-9]
 row=dict(name=o.name,vertices=len(me.vertices),faces=len(me.polygons),degrees=dict(Counter(len(f.verts) for f in bm.faces)),degenerate_faces=deg,duplicate_faces=duplicate,loose_edges=sum(len(e.link_faces)==0 for e in bm.edges),edges_more_than_two=sum(len(e.link_faces)>2 for e in bm.edges),boundary_edges=sum(e.is_boundary for e in bm.edges),t_junctions=ts,max_edge_m=max(lens),uv_bounds=[uv.min(axis=0).tolist(),uv.max(axis=0).tolist()],material_counts=dict(Counter(p.material_index for p in me.polygons)))
 rows.append(row);bm.free()
 geo.append(dict(name=o.name,vertices=[list(v.co) for v in me.vertices],faces=[list(p.vertices) for p in me.polygons],materials=[p.material_index for p in me.polygons],patches=[d.value for d in me.attributes['source_patch'].data]))
(out/'readback.json').write_text(json.dumps(dict(file=bpy.data.filepath,originals_unchanged=True,objects=rows),indent=2))
(out/'validated-geometry.json').write_text(json.dumps(geo))
for r in rows:print({k:(len(v) if isinstance(v,list) and k in ['t_junctions','degenerate_faces'] else v) for k,v in r.items() if k not in ['material_counts','uv_bounds']},flush=True)

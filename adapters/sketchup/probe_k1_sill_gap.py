"""Read-only local face/edge inventory around the two open upper-sill endpoints."""
import bpy,bmesh,json
from pathlib import Path

root=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(root/'GLB_K1_assembled_v022.blend'))
o=bpy.data.objects['TOP_<auto>26'];bm=bmesh.new();bm.from_mesh(o.data)
bm.verts.ensure_lookup_table();bm.edges.ensure_lookup_table();bm.faces.ensure_lookup_table()
boundary=[e for e in bm.edges if len(e.link_faces)==1]
from collections import Counter
degree=Counter(v.index for e in boundary for v in e.verts)
ends=[v for v in bm.verts if degree[v.index]==1]
rows=[]
for v in ends:
 rows.append({'vertex':v.index,'point':list(v.co),
              'edges':[{'vertices':[list(x.co) for x in e.verts],'link_faces':[f.index for f in e.link_faces]} for e in v.link_edges],
              'faces':[{'index':f.index,'normal':list(f.normal),'points':[list(x.co) for x in f.verts]} for f in v.link_faces]})
(root/'top-sill-gap-v022.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print('GAP='+json.dumps([{'vertex':r['vertex'],'point':r['point'],'edges':len(r['edges']),'faces':len(r['faces'])} for r in rows]))

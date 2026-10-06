"""Read-only topology summary for horizontal source-top elements."""
import bpy, bmesh, json
from pathlib import Path
from collections import Counter

root=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(root/'GLB_K1_assembled_v022.blend'))
rows=[]
for o in bpy.data.objects:
    if not o.name.startswith('TOP_') or o.name.startswith(('TOP_Window','TOP_AC')) or o.type!='MESH':
        continue
    bm=bmesh.new();bm.from_mesh(o.data)
    horizontal=[f for f in bm.faces if abs(f.normal.z)>.98]
    boundary=[e for e in bm.edges if len(e.link_faces)==1]
    zbin=Counter(round(f.calc_center_median().z,3) for f in horizontal)
    bbin=Counter(round((e.verts[0].co.z+e.verts[1].co.z)/2,3) for e in boundary)
    degree=Counter(v.index for e in boundary for v in e.verts)
    dangling=[v for v in bm.verts if degree[v.index]==1]
    rows.append({'name':o.name,'horizontal_faces':len(horizontal),'horizontal_z':zbin.most_common(10),
                 'boundary_edges':len(boundary),'boundary_z':bbin.most_common(10),
                 'nonmanifold_edges':sum(len(e.link_faces)>2 for e in bm.edges),
                 'dangling_boundary_vertices':len(dangling),
                 'dangling_examples':[list(v.co) for v in dangling[:12]]})
    bm.free()
(root/'top-sills-v022-inventory.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print('SILL_SUMMARY='+json.dumps(rows,ensure_ascii=False))

import bpy,bmesh,json
from pathlib import Path
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/v001'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'facade_signs_v001.blend'))
rows=[]
for ob in bpy.data.collections['Facade signs | 30 mm'].objects:
    bm=bmesh.new(); bm.from_mesh(ob.data); bm.faces.ensure_lookup_table()
    tree=BVHTree.FromBMesh(bm,epsilon=0)
    pairs=set()
    for a,b in tree.overlap(tree):
        if a>=b: continue
        if set(bm.faces[a].verts).intersection(bm.faces[b].verts): continue
        pairs.add((a,b))
    coords=[tuple(round(c,8) for c in v.co) for v in bm.verts]
    row=dict(name=ob.name,dimensions_mm=[round(x*1000,4) for x in ob.dimensions],
        vertices=len(bm.verts),faces=len(bm.faces),nonquads=sum(len(f.verts)!=4 for f in bm.faces),
        nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
        inconsistent_edges=sum(not e.is_contiguous for e in bm.edges),
        zero_faces=sum(f.calc_area()<1e-12 for f in bm.faces),
        duplicate_vertices=len(coords)-len(set(coords)),
        nonadjacent_intersection_candidates=len(pairs),volume=bm.calc_volume(signed=True))
    rows.append(row); bm.free()
result={'readback':'verified','objects':rows,'visual_acceptance':'pending',
 'scope':'Editable signs only; no AGR delivery claim. BVH check excludes adjacent faces.',
 'reference_packed':bool(bpy.data.images.get('reference.png').packed_file)}
(OUT/'qa.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))

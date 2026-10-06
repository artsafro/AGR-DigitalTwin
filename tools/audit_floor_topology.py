"""Read-only topology inventory. Exact duplicates do not cover all face intersections."""
import bpy, bmesh, json, sys, hashlib
from pathlib import Path
from collections import Counter

p=Path(sys.argv[sys.argv.index('--')+1]).resolve()
blend=p/'OBR22_K02_typical_floor_v001.blend'
before=hashlib.sha256(blend.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(blend))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.visible_get()]
all_vertices={}; all_faces={}; records=[]; duplicate_face_examples=[]
for o in objects:
    coords=[tuple(float(x) for x in (o.matrix_world@v.co)) for v in o.data.vertices]
    own_coords=Counter(coords)
    cross_vertices=0
    for c in set(coords):
        if c in all_vertices: cross_vertices+=1
        else: all_vertices[c]=o.name
    own_faces=set(); same_faces=other_faces=0
    for f in o.data.polygons:
        # Cyclic order matters: ignore only rotation and winding, not arbitrary sorting.
        loop=[coords[i] for i in f.vertices]
        anchor=min(range(len(loop)),key=lambda i:loop[i])
        a=tuple(loop[anchor:]+loop[:anchor])
        reverse=list(reversed(loop)); k=min(range(len(reverse)),key=lambda i:reverse[i])
        key=min(a,tuple(reverse[k:]+reverse[:k]))
        if key in own_faces: same_faces+=1
        elif key in all_faces:
            other_faces+=1
            if len(duplicate_face_examples)<30:
                duplicate_face_examples.append({'a':all_faces[key],'b':{'object':o.name,'polygon':f.index}})
        else: all_faces[key]={'object':o.name,'polygon':f.index}
        own_faces.add(key)
    bm=bmesh.new(); bm.from_mesh(o.data)
    boundary=sum(e.is_boundary for e in bm.edges)
    multi=sum(len(e.link_faces)>2 for e in bm.edges)
    wire=sum(e.is_wire for e in bm.edges)
    bm.free()
    hist=Counter(len(f.vertices) for f in o.data.polygons)
    records.append({'object':o.name,'revit_id':o.get('revit_element_id'),
        'vertices':len(coords),'faces':len(o.data.polygons),'face_degrees':dict(hist),
        'exact_duplicate_vertices_within':sum(n-1 for n in own_coords.values()),
        'exact_coincident_positions_across_objects':cross_vertices,
        'exact_duplicate_faces_within':same_faces,'exact_duplicate_faces_across_objects':other_faces,
        'boundary_edges':boundary,'edges_with_more_than_2_faces':multi,'wire_edges':wire,
        'zero_area_faces':sum(f.area<=1e-12 for f in o.data.polygons)})
totals={key:sum(x[key] for x in records) for key in records[0] if key not in ['object','revit_id','face_degrees']}
hist=Counter()
for r in records: hist.update(r['face_degrees'])
totals.update(mesh_objects=len(objects),triangles=hist[3],quads=hist[4],ngons=sum(n for degree,n in hist.items() if degree>4))
totals['quad_percent']=100*totals['quads']/totals['faces']
after=hashlib.sha256(blend.read_bytes()).hexdigest()
result={'verdict':'does_not_meet_requested_clean_mesh_requirements',
        'scope':'visible floor meshes only; hidden source/context excluded',
        'duplicate_method':'exact floating point world coordinates and identical cyclic polygon loops, both windings',
        'limits':['partial coplanar overlaps and non-coplanar intersections NOT tested',
                  'coincident vertices across objects can be intended contacts or split boundaries',
                  'four vertices alone does not prove regular or square quad quality'],
        'totals':totals,'blend_sha256':before,'source_unchanged':before==after,
        'duplicate_face_examples':duplicate_face_examples,'objects':records}
(p/'topology-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['objects','duplicate_face_examples']},ensure_ascii=True))
assert before==after

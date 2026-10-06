import bpy,bmesh,json,os
from pathlib import Path
from collections import Counter
root=Path('C:/Users/artsafro/.AGR_Project/jobs/REVIT-OPENINGS')
new=os.environ.get('AGR_OPENINGS_V003')=='1'
out=root/('outputs/openings-v003' if new else 'outputs/simple-v002')
bpy.ops.wm.open_mainfile(filepath=str(out/('SOSH1150_Openings_v003.blend' if new else 'Simple_Openings_v002.blend')))
models=bpy.data.collections['OPENING_TYPES' if new else 'SIMPLE_OPENINGS_MODELS_v002'].objects
report=[];geometry=[]
for o in models:
    me=o.data;bm=bmesh.new();bm.from_mesh(me)
    verts=[tuple(round(c,7) for c in v.co) for v in me.vertices]
    canonical=[tuple(sorted(verts[i] for i in f.vertices)) for f in me.polygons]
    degrees=Counter(len(f.vertices) for f in me.polygons)
    boundary=[e for e in bm.edges if e.is_boundary]
    expected_boundary=all(abs(v.co.y)<1e-6 and (abs(v.co.x)<1e-6 or abs(v.co.x-o.dimensions.x)<1e-6 or abs(v.co.z)<1e-6 or abs(v.co.z-o.dimensions.z)<1e-6) for e in boundary for v in e.verts)
    zero_uv=0
    for p in me.polygons:
        uv=[me.uv_layers.active.data[i].uv for i in p.loop_indices]
        area=abs(sum(a.x*b.y-b.x*a.y for a,b in zip(uv,uv[1:]+uv[:1])))/2
        zero_uv+=area<1e-12
    r={'name':o.name,'vertices':len(verts),'polygons':len(me.polygons),'degrees':dict(degrees),'material_ids':sorted(set(p.material_index+1 for p in me.polygons)),
       'duplicate_vertices':len(verts)-len(set(verts)),'duplicate_faces':len(canonical)-len(set(canonical)),
       'zero_area_faces':sum(p.area<1e-10 for p in me.polygons),'nonmanifold_edges':sum(len(e.link_faces)>2 for e in bm.edges),
       'loose_edges':sum(len(e.link_faces)==0 for e in bm.edges),'boundary_edges':len(boundary),'boundary_is_only_outer_perimeter':expected_boundary,
       'euler_characteristic':len(bm.verts)-len(bm.edges)+len(bm.faces),'zero_uv_faces':zero_uv,'dimensions':list(o.dimensions)}
    report.append(r);geometry.append({'name':o.name,'vertices':verts,'faces':[list(p.vertices) for p in me.polygons]});bm.free()
(out/'readback.json').write_text(json.dumps(report,indent=2),encoding='utf-8');(out/'readback-geometry.json').write_text(json.dumps(geometry),encoding='utf-8')
wiremat=bpy.data.materials.new('QA_WIRE');wiremat.diffuse_color=(.015,.025,.03,1)
for o in models:
    d=bpy.data.curves.new(o.name+'_wire','CURVE');d.dimensions='3D';d.bevel_depth=.0018;d.bevel_resolution=0;d.resolution_u=1
    for e in o.data.edges:
        s=d.splines.new('POLY');s.points.add(1)
        for q,vi in zip(s.points,e.vertices):
            p=o.data.vertices[vi].co;q.co=(p.x,p.y-.002,p.z,1)
    d.materials.append(wiremat);obj=bpy.data.objects.new(o.name+'_wire',d);bpy.context.scene.collection.objects.link(obj);obj.location=o.location
bpy.context.scene.render.filepath=str(out/('blender-wire.png' if new else 'samples-wire.png'));bpy.ops.render.render(write_still=True)
print(json.dumps(report))

import bpy,json,hashlib,bmesh
from pathlib import Path
from collections import Counter
import numpy as np
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/model-v002')
expected=json.loads((out/'build-report.json').read_text())
def fingerprint(o):
    h=hashlib.sha256();h.update(str(tuple(tuple(r) for r in o.matrix_world)).encode())
    if o.type=='MESH':
        for v in o.data.vertices:h.update(str(tuple(v.co)).encode())
        for p in o.data.polygons:h.update(str((tuple(p.vertices),p.material_index)).encode())
        for layer in o.data.uv_layers:
            for uv in layer.data:h.update(str(tuple(uv.uv)).encode())
    return h.hexdigest()
preserved=all(fingerprint(bpy.data.objects[n])==h for n,h in expected['preserved_object_signatures'].items())
assert preserved
rows=[]; tj=[];allfacekeys=Counter();export=[]
for o in bpy.data.collections['LP'].objects:
    if o.type!='MESH':continue
    isnew=o.name.startswith('LP_Add_');bm=bmesh.new();bm.from_mesh(o.data);bm.verts.ensure_lookup_table();bm.edges.ensure_lookup_table()
    export.append({'name':o.name,'vertices':[list(o.matrix_world@v.co) for v in o.data.vertices],
        'faces':[list(p.vertices) for p in o.data.polygons],'new':isnew})
    pp=np.array([tuple(v.co) for v in bm.verts]);facekeys=Counter(tuple(sorted(tuple(round(x,6) for x in v.co) for v in f.verts)) for f in bm.faces)
    if isnew:
        for e in bm.edges:
            if not e.is_boundary:continue
            a=np.array(e.verts[0].co);b=np.array(e.verts[1].co);vec=b-a;den=vec@vec
            if den<1e-12:continue
            t=((pp-a)@vec)/den
            mask=(t>1e-5)&(t<1-1e-5)
            ids=np.flatnonzero(mask&(np.linalg.norm(pp-(a+t[:,None]*vec),axis=1)<2e-5))
            if len(ids):tj.append({'object':o.name,'edge':e.index,'vertices':ids.tolist(),
                'a':a.tolist(),'b':b.tolist(),'points':pp[ids].tolist(),'faces':[f.index for f in e.link_faces]})
    rows.append({'name':o.name,'new':isnew,'quads':sum(len(f.verts)==4 for f in bm.faces),'nonquads':sum(len(f.verts)!=4 for f in bm.faces),
      'zero_area':sum(f.calc_area()<1e-10 for f in bm.faces),'zero_edges':sum(e.calc_length()<1e-7 for e in bm.edges),
      'duplicate_faces':sum(c-1 for c in facekeys.values()),'edges_over_two_faces':sum(len(e.link_faces)>2 for e in bm.edges),
      'loose_edges':sum(len(e.link_faces)==0 for e in bm.edges),'boundary_edges':sum(e.is_boundary for e in bm.edges),
      'has_modifiers':len(o.modifiers),'coordinate_duplicate_excess':len(pp)-len(set(tuple(v) for v in pp))})
    bm.free()
report={'file':bpy.data.filepath,'original_objects_unchanged':preserved,'readback':True,'objects':rows,'new_t_junction_candidates':tj,
    'scope':'new quad surfaces; original draft topology retained','delivery_passed':False}
(out/'readback-v002.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(out/'validated-geometry.json').write_text(json.dumps(export),encoding='utf-8')
print('PRESERVED',preserved,'NEW',json.dumps([r for r in rows if r['new']]),'Tjunctions',len(tj),flush=True)
import sys
if '--qa-only' in sys.argv:raise SystemExit(0)
# A wire preview of new surfaces. Diagnostic objects are never saved.
from mathutils import Vector
scene=bpy.context.scene;scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1200;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
shade=scene.display.shading;shade.light='STUDIO';shade.color_type='OBJECT';shade.show_shadows=True;shade.show_cavity=True;shade.background_type='WORLD';scene.world.color=(.12,.12,.12)
curve=bpy.data.curves.new('QA_wire','CURVE');curve.dimensions='3D';curve.bevel_depth=.012;curve.resolution_u=1;curve.bevel_resolution=0
for o in list(bpy.context.scene.objects):
    if o.type!='MESH':continue
    o.hide_render=o.name not in bpy.data.collections['LP'].objects
    o.color=(.68,.7,.74,1)
    if o.name.startswith('LP_Add_'):
        o.color=(.28,.6,.62,1)
        for e in o.data.edges:
            s=curve.splines.new('POLY');s.points.add(1)
            for target,index in zip(s.points,e.vertices):target.co=(*o.data.vertices[index].co,1)
w=bpy.data.objects.new('QA_wire',curve);scene.collection.objects.link(w);w.color=(.04,.06,.065,1)
c=bpy.data.cameras.new('QA_camera');cam=bpy.data.objects.new('QA_camera',c);scene.collection.objects.link(cam);scene.camera=cam;c.type='ORTHO';c.ortho_scale=85
target=Vector((22,-43,16));cam.location=target+Vector((-100,100,70));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(out/'LP-new-wire.png');bpy.ops.render.render(write_still=True)

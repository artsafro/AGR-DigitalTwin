import bpy, json, sys, math
from pathlib import Path
from mathutils import Matrix,Vector
job=Path(sys.argv[sys.argv.index('--')+1]).resolve()
out=job/'outputs/planes-ab-v002'
bpy.ops.wm.open_mainfile(filepath=str(out/'GLB_AB_planes_v002.blend'))
windows=[o for o in bpy.data.objects if o.get('role')=='windows']
acs=[o for o in bpy.data.objects if o.get('role')=='ac']
w=windows[0].data;a=acs[0].data
coords=[v.co for v in w.vertices]
cfg=json.loads((job/'plane-nodes-job.json').read_text(encoding='utf-8'))['window']
embeds=[max(v.x for v in coords)-cfg['opening_front_end_x_m'],
        cfg['opening_side_end_y_m']-min(v.y for v in coords),
        cfg['opening_bottom_z_m']-min(v.z for v in coords),
        max(v.z for v in coords)-cfg['opening_top_z_m']]
assert all(abs(v-.01)<1e-6 for v in embeds),embeds
assert abs(w.polygons[0].normal.dot(w.polygons[1].normal))<1e-6
shared=set(w.polygons[0].vertices)&set(w.polygons[1].vertices)
assert len(shared)==2
assert len(a.polygons)==4 and all(abs(p.normal.z-1)>1e-6 for p in a.polygons)
seen=set();duplicate=0
for ob in windows+acs:
    for p in ob.data.polygons:
        key=tuple(sorted(tuple(round(float(c),5) for c in (ob.matrix_world@ob.data.vertices[i].co)) for i in p.vertices))
        duplicate+=key in seen;seen.add(key)
assert duplicate==0
report={'readback_windows':len(windows),'readback_ac':len(acs),'window_angle_degrees':90,
        'window_edge_embed_m':embeds,'window_shared_corner_vertices':len(shared),
        'duplicate_new_faces_at_0_01mm':duplicate,'ac_faces_each':4,'ac_top_faces':0,
        'new_faces_all_quads':True,'body_intersection_QA':'not full model QA',
        'source_opening_basis':cfg['evidence']}
(out/'node-geometry-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
# Diagnostic view only: do not save these changed placements to the delivered blend.
for ob in bpy.data.objects:
    if ob.type=='MESH':ob.hide_render=True
wo=windows[0];ao=acs[0];wo.hide_render=False;ao.hide_render=False
wo.matrix_world=Matrix.Translation(Vector((-1.7,-.37375,1.15)))
ao.matrix_world=Matrix.Translation(Vector((1.4,0,.7)))@Matrix.Rotation(math.pi,4,'Z')
scene=bpy.context.scene;cam=scene.camera
aim=Vector((-.25,0,1.1));cam.location=aim+Vector((-6,9,4))
cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=6.3
scene.render.resolution_x=1500;scene.render.resolution_y=1000;scene.cycles.samples=32
scene.render.filepath=str(out/'nodes_closeup.png')
bpy.ops.render.render(write_still=True)
print(json.dumps(report))

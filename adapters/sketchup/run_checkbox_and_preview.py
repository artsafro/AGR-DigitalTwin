import bpy,bmesh,json,sys,hashlib
from pathlib import Path
from mathutils import Vector
version = sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'v006'
job=Path('jobs/GLB-NPM').resolve();out=job/f'outputs/clearance-ab-{version}'
bpy.ops.wm.open_mainfile(filepath=str(out/f'GLB_AB_clearance_{version}.blend'))
addon=Path('C:/Users/artsafro/AppData/Roaming/Blender Foundation/Blender/4.4/scripts/addons')
sys.path.insert(0,str(addon))
from CheckToolBox_v1_5.core.total_operator import CheckTool
from CheckToolBox_v1_5.core.mesh_helpers import bmesh_check_self_intersect_object
checker=CheckTool();results=[]
for ob in bpy.data.objects:
    if ob.type!='MESH':continue
    bm=bmesh.new();bm.from_mesh(ob.data)
    doubles=checker.find_doubles_cot(bm,.005);bm.free()
    intersections=list(bmesh_check_self_intersect_object(ob))
    results.append({'object':ob.name,'duplicate_vertices_at_5mm':doubles,'intersection_faces':intersections})
# Same native intersection check on an ephemeral joined world-space copy.
verts=[];faces=[]
for ob in bpy.data.objects:
    if ob.type!='MESH':continue
    start=len(verts);verts.extend(tuple(ob.matrix_world@v.co) for v in ob.data.vertices)
    faces.extend(tuple(start+i for i in p.vertices) for p in ob.data.polygons)
mesh=bpy.data.meshes.new('TEMP_CHECKBOX_JOINED');mesh.from_pydata(verts,[],faces);mesh.update()
ob=bpy.data.objects.new('TEMP_CHECKBOX_JOINED',mesh);bpy.context.scene.collection.objects.link(ob)
joined=list(bmesh_check_self_intersect_object(ob));bm=bmesh.new();bm.from_mesh(mesh)
doubles_joined=checker.find_doubles_cot(bm,.005);bm.free()
bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(mesh)
report={'plugin':'Installed CheckToolBox_v1_5','native_functions_called':['CheckTool.find_doubles_cot','bmesh_check_self_intersect_object'],
        'vertex_threshold_m':.005,'native_intersection_epsilon_m':.00001,
        'joined_duplicate_vertices':doubles_joined,'joined_intersection_face_count':len(joined),
        'joined_intersection_faces':joined,'objects':results,
        'limits':['Native vertex test is not face clearance.','Native intersection check also reports authorized volume penetration.',
                  'Source BODY has unwelded per-face vertices.','No claim that all CheckToolBox checks pass.']}
(out/'CheckToolBox-native-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
# Shape/topology of the newly rebuilt nodes and window insertion, after saved-file reopen.
node_checks=[]
for ob in bpy.data.objects:
    if ob.type!='MESH' or ob.get('role') not in ['windows','ac','simple_sills']:continue
    me=ob.data
    assert all(len(p.vertices)==4 and p.area>1e-9 for p in me.polygons)
    if ob.get('role')=='windows':
        co=[v.co for v in me.vertices]
        assert abs(max(v.z for v in co)-1.17)<1e-6 and abs(min(v.z for v in co)+1.15)<1e-6
        if version == 'v006':
            assert abs(max(v.x for v in co)-.96625)<1e-6 and abs(min(v.y for v in co)+.68625)<1e-6
    node_checks.append({'object':ob.name,'quads':len(me.polygons)})
(out/'node-readback.json').write_text(json.dumps({'nodes':node_checks,'new_faces_non_degenerate_quads':True,'window_edges_verified':True},indent=2),encoding='utf-8')
scene=bpy.context.scene;scene.cycles.samples=24;scene.render.filepath=str(out/f'AB_clearance_{version}.png')
bpy.ops.render.render(write_still=True)
win=next(o for o in bpy.data.objects if o.get('role')=='windows' and o.name.startswith('A_'))
aim=win.matrix_world@Vector((0,.1,-.3));direction=win.matrix_world.to_3x3()@Vector((-1,1,.55)).normalized()
cam=scene.camera;cam.location=aim+direction*7;cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=4.2
scene.render.resolution_x=1500;scene.render.resolution_y=1100;scene.render.filepath=str(out/'window_closeup.png')
bpy.ops.render.render(write_still=True)
print('CHECKBOX_NATIVE '+json.dumps({'objects':len(results),'joined_intersection_faces':len(joined),'joined_duplicate_vertices':doubles_joined,'node_quads_checked':len(node_checks)}))

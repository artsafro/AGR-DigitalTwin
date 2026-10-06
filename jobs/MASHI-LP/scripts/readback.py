import bpy,json,hashlib,bmesh
from pathlib import Path
from collections import Counter
from mathutils import Vector
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/audit-v001')
expected=json.loads((out/'organization.json').read_text())
def signature(o):
    h=hashlib.sha256(); h.update(str(tuple(tuple(r) for r in o.matrix_world)).encode())
    if o.type=='MESH':
        for v in o.data.vertices: h.update(str(tuple(v.co)).encode())
        for p in o.data.polygons: h.update(str((tuple(p.vertices),p.material_index)).encode())
        for u in o.data.uv_layers:
            for d in u.data: h.update(str(tuple(d.uv)).encode())
    return h.hexdigest()
actual={o.name:signature(o) for o in bpy.context.scene.objects}
assert actual==expected['signatures']
assert all(sorted(o.name for o in bpy.data.collections[n].objects)==sorted(names) for n,names in expected['mapping'].items())
rows=[]
for o in bpy.data.collections['LP'].objects:
    if o.type!='MESH':continue
    coords=[tuple(o.matrix_world @ v.co) for v in o.data.vertices]
    count=Counter(coords)
    faces=Counter(tuple(sorted(coords[i] for i in p.vertices)) for p in o.data.polygons)
    rows.append(dict(name=o.name,coincident_vertex_excess=sum(v-1 for v in count.values()),exact_duplicate_faces=sum(v-1 for v in faces.values()),uv_layers=len(o.data.uv_layers)))
old=[]
for o in bpy.data.collections['LP_old'].objects:
    old.append(dict(name=o.name,materials=[m.name if m else None for m in o.data.materials],face_material_counts=dict(Counter(p.material_index for p in o.data.polygons)),uv_layers=[u.name for u in o.data.uv_layers]))
report=dict(saved_file_readback_matches=True,objects=len(actual),LP_checks=rows,old_materials=old,
    not_checked=['partial coplanar overlaps','self intersections','normal orientation','boundary intent','geometric 2mm compliance'])
(out/'readback.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
scene=bpy.context.scene; scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=1000; scene.render.resolution_y=900; scene.render.resolution_percentage=100
shade=scene.display.shading; shade.light='STUDIO'; shade.color_type='MATERIAL'; shade.show_shadows=True; shade.show_cavity=True
shade.background_type='WORLD'; scene.world.color=(.12,.12,.12)
camdata=bpy.data.cameras.new('AuditCamera');cam=bpy.data.objects.new('AuditCamera',camdata);scene.collection.objects.link(cam);scene.camera=cam
camdata.type='ORTHO';camdata.ortho_scale=85
target=Vector((35.75,13,33.77));cam.location=target+Vector((90,-110,85));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
for o in bpy.context.scene.objects:
    if o.type=='MESH':o.hide_render=o.name not in expected['mapping']['LP_old']
scene.render.filepath=str(out/'LP_old-A.png');bpy.ops.render.render(write_still=True)

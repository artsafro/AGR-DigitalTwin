import bpy,json,hashlib
from pathlib import Path
from mathutils import Vector
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/model-v002')
report=json.loads((out/'build-report.json').read_text());qa=json.loads((out/'readback-v002.json').read_text())
assert qa['readback'] and qa['original_objects_unchanged'] and not qa['new_t_junction_candidates']
assert not json.loads((out/'overlap-check.json').read_text())['findings']
assert not json.loads((out/'crossing-check.json').read_text())['findings']
def fingerprint(o):
    h=hashlib.sha256();h.update(str(tuple(tuple(r) for r in o.matrix_world)).encode())
    if o.type=='MESH':
        for v in o.data.vertices:h.update(str(tuple(v.co)).encode())
        for p in o.data.polygons:h.update(str((tuple(p.vertices),p.material_index)).encode())
        for layer in o.data.uv_layers:
            for uv in layer.data:h.update(str(tuple(uv.uv)).encode())
    return h.hexdigest()
changed=[n for n,h in report['preserved_object_signatures'].items() if n not in bpy.data.objects or fingerprint(bpy.data.objects[n])!=h]
assert not changed, 'Live scene changed during modelling: '+str(changed)
assert not any(o.name.startswith('LP_Add_') for o in bpy.context.scene.objects)
path=str(out/'LP_completed-v002.blend')
with bpy.data.libraries.load(path,link=False) as (source,dest):
    dest.objects=[n for n in source.objects if n.startswith('LP_Add_')]
assert len(dest.objects)==5
for o in dest.objects:
    bpy.data.collections['LP'].objects.link(o);o.hide_set(False);o.hide_render=False
for name in ['LP','Revit','LP_old']:
    for o in bpy.data.collections[name].objects:
        o.hide_set(name!='LP');o.hide_render=name!='LP';o.select_set(o.name.startswith('LP_Add_'))
bpy.context.view_layer.objects.active=dest.objects[0]
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        sp=area.spaces.active;sp.region_3d.view_perspective='ORTHO';sp.region_3d.view_location=Vector((22,-43,16));sp.region_3d.view_distance=85
        sp.region_3d.view_rotation=Vector((100,-100,-70)).to_track_quat('-Z','Y');sp.shading.type='SOLID'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'LP_working-v002.blend'))
(out/'live-receipt.json').write_text(json.dumps({'file':bpy.data.filepath,'originals_unchanged':not changed,'new_objects':[o.name for o in dest.objects],'quads':sum(len(o.data.polygons) for o in dest.objects)},indent=2),encoding='utf-8')
print((out/'live-receipt.json').read_text())

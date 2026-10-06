import bpy, json, hashlib
from pathlib import Path
from mathutils import Vector
root=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/audit-v001')
assert not (root/'organized-v001.blend').exists(), 'Do not overwrite version'
source=root/'source-snapshot.blend'
assert not source.exists(), 'Snapshot exists'
bpy.ops.wm.save_as_mainfile(filepath=str(source),copy=True)
def signature(o):
    h=hashlib.sha256()
    h.update(str(tuple(tuple(r) for r in o.matrix_world)).encode())
    if o.type=='MESH':
        for v in o.data.vertices: h.update(str(tuple(v.co)).encode())
        for p in o.data.polygons: h.update(str((tuple(p.vertices),p.material_index)).encode())
        for u in o.data.uv_layers:
            for d in u.data: h.update(str(tuple(d.uv)).encode())
    return h.hexdigest()
before={o.name:signature(o) for o in bpy.context.scene.objects}
revit_objects={'Object003','Object004','Object007','Object009','Object015','Object016','Object018','Object020','Object029','Object030'}
groups={n:[] for n in ['LP','Revit','LP_old']}
for o in bpy.context.scene.objects:
    if o.name.startswith('SM_MashiPoryvaevoj_34_004_'): group='LP_old'
    elif o.name.startswith(('Material #','MultiMat_')) or o.name in revit_objects: group='Revit'
    elif o.name.startswith(('Shape','Plane')) or o.name in {'Object019','Object022','Object023','Object031','Object032'}: group='LP'
    else: raise RuntimeError('Unmapped '+o.name)
    groups[group].append(o)
for name, objects in groups.items():
    c=bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(c)
    for o in objects:
        c.objects.link(o)
        for old in list(o.users_collection):
            if old!=c: old.objects.unlink(o)
after={o.name:signature(o) for o in bpy.context.scene.objects}
assert before==after
report={'mapping':{n:[o.name for o in oo] for n,oo in groups.items()},'signatures':after,
    'geometry_transform_material_indices_uv_unchanged':before==after,
    'missing_from_screenshot':['window_001..window_007','Plane006','second Plane011','second Object031','second Object032','second Object030'],
    'notes':['Shape006 is EMPTY, not mesh','LP_old is spatially offset; not realigned']}
(root/'organization.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(root/'organized-v001.blend'))
print(json.dumps({'counts':{n:len(oo) for n,oo in groups.items()},'unchanged':before==after,'saved':bpy.data.filepath}))

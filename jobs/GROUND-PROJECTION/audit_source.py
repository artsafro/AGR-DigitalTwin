import bpy, json, collections, hashlib
from pathlib import Path
from mathutils import Vector

root=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION')
src=Path(r'C:/Users/artsafro/Downloads/Telegram Desktop/GROUND.fbx')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(src), use_image_search=False)
out={'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'blender':bpy.app.version_string,'objects':[]}
for o in bpy.context.scene.objects:
    if o.type!='MESH': continue
    m=o.data
    pts=[o.matrix_world@v.co for v in m.vertices]
    bbox=[[min(v[i] for v in pts),max(v[i] for v in pts)] for i in range(3)]
    out['objects'].append({'name':o.name,'vertices':len(m.vertices),'edges':len(m.edges),'faces':len(m.polygons),'polygon_sizes':dict(collections.Counter(len(p.vertices) for p in m.polygons)),'bbox_world_m':bbox,'matrix':[list(r) for r in o.matrix_world],'materials':[s.name if s else None for s in m.materials],'face_material_counts':dict(collections.Counter(p.material_index for p in m.polygons)),'uv_layers':[u.name for u in m.uv_layers], 'area':sum(p.area for p in m.polygons)})
    data={'vertices':[list(v) for v in pts],'faces':[list(p.vertices) for p in m.polygons],'materials':[p.material_index for p in m.polygons]}
    (root/'outputs/v001'/('source_'+o.name+'.json')).write_text(json.dumps(data),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(root/'outputs/v001/source_import.blend'))
(root/'outputs/v001/source_audit.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))

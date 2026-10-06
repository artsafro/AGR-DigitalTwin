"""Independent saved .blend readback against recorded pre-transform mesh bounds."""
import json, math, sys
from pathlib import Path
import bpy
from mathutils import Matrix
p=Path(sys.argv[sys.argv.index('--')+1]).resolve()
report=json.loads((p/'build-report.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=report['blend'])
scene=bpy.context.scene
inverse=Matrix(json.loads(scene['local_to_revit_internal_m']))
errors=[]; max_error=0.0; identities=0; material_refs=0; visible_wall_ids=set()
for rec in report['records']:
    o=scene.objects.get(rec['name'])
    if o is None or o.type!='MESH':
        errors.append({'name':rec['name'],'error':'missing mesh'}); continue
    if o.get('revit_element_id'): identities+=1
    if o.get('revit_structural_material_id'): material_refs+=1
    if rec['collection']=='02_Стены': visible_wall_ids.add(o.get('revit_element_id'))
    points=[inverse @ o.matrix_world @ v.co for v in o.data.vertices]
    if not all(math.isfinite(x) for v in points for x in v): errors.append({'name':o.name,'error':'nonfinite'})
    actual=[[min(v[i] for v in points) for i in range(3)],[max(v[i] for v in points) for i in range(3)]]
    error=max(abs(actual[j][i]-rec['source_bounds_m'][j][i]) for j in range(2) for i in range(3))
    max_error=max(max_error,error)
    if error>0.00025: errors.append({'name':o.name,'error':'placement/bounds drift','meters':error})
    if len(o.data.polygons)!=rec['polygons']: errors.append({'name':o.name,'error':'polygon count drift'})
    if o.data.validate(verbose=False): errors.append({'name':o.name,'error':'mesh required repair on readback'})
    expected_hidden=rec['collection'].startswith(('70_','71_','80_','90_','91_'))
    c=bpy.data.collections[rec['collection']]
    if c.hide_render!=expected_hidden or c.hide_viewport!=expected_hidden: errors.append({'name':o.name,'error':'visibility'})
src=json.loads(json.loads((p/'walls.json').read_text())['content'][0]['text'])['data']['elements']
expected_wall_ids={str(x['id']) for x in src}
if visible_wall_ids!=expected_wall_ids:
    errors.append({'error':'wall IDs differ from source typical plan','missing':sorted(expected_wall_ids-visible_wall_ids),'extra':sorted(visible_wall_ids-expected_wall_ids)})
result={'status':'pass' if not errors else 'fail','scope':'saved Blender artifact, not regulatory/project acceptance',
        'blender':bpy.app.version_string,'mesh_objects':len(report['records']),
        'single_revit_id_objects':identities,'structural_material_parameter_objects':material_refs,
        'visible_wall_ids':len(visible_wall_ids),'expected_plan_wall_ids':len(expected_wall_ids),
        'max_inverse_placement_bbox_error_m':max_error,'bound_tolerance_m':0.00025,'errors':errors}
(p/'readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
if errors: raise RuntimeError('Readback failed')

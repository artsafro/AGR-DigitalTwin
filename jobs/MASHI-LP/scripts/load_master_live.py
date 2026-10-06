import bpy,json,hashlib
from pathlib import Path
from mathutils import Vector
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/master-v001')
def fingerprint(o):
 h=hashlib.sha256();h.update(str(tuple(tuple(r) for r in o.matrix_world)).encode())
 if o.type=='MESH':
  for p in o.data.vertices:h.update(str(tuple(p.co)).encode())
  for p in o.data.polygons:h.update(str((tuple(p.vertices),p.material_index)).encode())
  for layer in o.data.uv_layers:
   for u in layer.data:h.update(str(tuple(u.uv)).encode())
 return h.hexdigest()
expected=json.loads((out/'build-report.json').read_text())['original_signatures']
assert bpy.context.mode=='OBJECT','User is editing; leave live scene intact.'
assert all(n in bpy.data.objects and fingerprint(bpy.data.objects[n])==h for n,h in expected.items()),'Live originals changed; do not overwrite.'
assert 'MASTER_Revit_v001' not in bpy.data.collections
with bpy.data.libraries.load(str(out/'MASTER-trial-v001.blend'),link=False) as (src,dst):dst.collections=['MASTER_Revit_v001']
col=dst.collections[0];bpy.context.scene.collection.children.link(col)
original_mats=list(bpy.data.objects['SM_MashiPoryvaevoj_34_004_Main.002'].data.materials)
for o in col.objects:
 for i,m in enumerate(original_mats):o.data.materials[i]=m
 assert o.library is None and o.data.library is None
for o in bpy.context.scene.objects:
 o.select_set(False)
 if o.type=='MESH':
  visible=(o in col.objects[:]) or (o in bpy.data.collections['LP'].objects[:]);o.hide_set(not visible);o.hide_render=not visible
for o in col.objects:o.select_set(True)
bpy.context.view_layer.objects.active=bpy.data.objects['MASTER_body']
for area in bpy.context.screen.areas:
 if area.type=='VIEW_3D':
  space=area.spaces.active;space.shading.type='SOLID';space.shading.color_type='MATERIAL';space.clip_end=1000
  space.region_3d.view_location=Vector((72,-43,17));space.region_3d.view_distance=145;space.region_3d.view_perspective='ORTHO';space.region_3d.view_rotation=Vector((90,-110,80)).to_track_quat('Z','Y')
assert all(fingerprint(bpy.data.objects[n])==h for n,h in expected.items())
text=bpy.data.texts.new('MASTER_TRIAL_README');text.write('Independent Revit mid-poly trial beside preserved LP (+100m X).\nQA NOT PASSED. Known partial overlaps/intersections remain.\nSee jobs/MASHI-LP/MASTER_TRIAL_REPORT.md.\nTD_1024_TEST is diagnostic UV, not a finish atlas.\n')
path=out/'MASHI-comparison-trial-v001.blend';assert not path.exists()
bpy.ops.wm.save_as_mainfile(filepath=str(path))
receipt=dict(file=bpy.data.filepath,objects=[o.name for o in col.objects],originals_unchanged=True,offset=[100,0,0],status='trial_qa_not_passed')
(out/'live-receipt.json').write_text(json.dumps(receipt,indent=2));print(receipt)

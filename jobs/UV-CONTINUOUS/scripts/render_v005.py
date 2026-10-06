import bpy,json,importlib,inspect
from pathlib import Path
root=Path('C:/Users/artsafro/.AGR_Project/jobs/UV-CONTINUOUS/outputs')
area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
region=next(r for r in area.regions if r.type=='WINDOW')
bpy.context.scene.render.filepath=str(root/'walls_view_v005.png')
with bpy.context.temp_override(area=area,region=region):bpy.ops.render.opengl(write_still=True,view_context=True)
module=importlib.import_module('bl_ext.user_default.sintez_agr_checker.scripts.autochecks.check_utils')
result=module.CheckUtils._calculate_td(bpy.context.active_object,{1001:4096},True)
rep={'td_less':list(result[5]),'td_greater':list(result[6]),'margin_failures':list(result[7]),'checker_module':module.__file__,'scope':'installed AGR TD/UV margin only; not full certification'}
(root/'agr_scoped_v005.json').write_text(json.dumps(rep,indent=2))
print(json.dumps({**rep,'td_less':len(rep['td_less']),'td_greater':len(rep['td_greater']),'margin_failures':len(rep['margin_failures'])}))

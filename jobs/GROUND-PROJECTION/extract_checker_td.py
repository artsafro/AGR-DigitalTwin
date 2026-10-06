"""Read-only snapshot of installed checker functions used for targeted2.6.1 QA."""
import ast,hashlib,json
from pathlib import Path
P=Path(r'C:/Users/artsafro/AppData/Roaming/Blender Foundation/Blender/4.4/extensions/user_default/sintez_agr_checker/scripts')
R=Path(__file__).parent/'outputs/v004';blocks=[];hashes={}
for path,names in [(P/'core_utils/utils.py',{'uv_polygon_area','texel_density'}),(P/'autochecks/check_utils.py',{'_calculate_td'})]:
 text=path.read_text(encoding='utf-8-sig');hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
 for node in ast.walk(ast.parse(text)):
  if isinstance(node,ast.FunctionDef) and node.name in names:
   node.decorator_list=[];blocks.append(ast.unparse(node))
header='import array, math, mathutils, bpy\nfrom types import SimpleNamespace\nconstants=SimpleNamespace(UDIM_MARGIN_UV=1/256)\n'
(R/'checker_td_snapshot.py').write_text(header+'\n\n'.join(blocks)+'\nutils=SimpleNamespace(uv_polygon_area=uv_polygon_area,texel_density=texel_density)\n',encoding='utf-8')
(R/'checker_source_hashes.json').write_text(json.dumps(hashes,indent=2))
print('Extracted installed functions:',len(blocks))

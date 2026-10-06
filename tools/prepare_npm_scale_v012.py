"""NPM OKS: material dimensions and phase match approved VPM, no Ground TD gate."""
import copy
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import prepare_floor_shared_uv as shared

root=Path(sys.argv[1]).resolve();out=root/'npm_v012';out.mkdir(exist_ok=True)
source=json.loads((root/'shared_v011/shared-uv-manifest.json').read_text(encoding='utf-8'))
old=json.loads((root/'uv_trial/uv-manifest.json').read_text(encoding='utf-8'))
shared.NPM_DENSITY=96.  # Sampling choice for readability; not an OKS regulatory target.
atlas=np.array(Image.open(source['source_images'][-1]['path']).convert('RGB'))
for ident,(name,_,(top,bottom)) in shared.MATERIALS.items():
    path=next(Path(r['path']) for r in source['source_images'] if Path(r['path']).name==name)
    shared.bake_region(atlas,(0,top,2048,bottom),shared.NPM_DENSITY,ident,np.array(Image.open(path).convert('RGB'),dtype=float))
Image.fromarray(atlas).save(out/'NPM_ATLAS_Diffuse.png')
result=copy.deepcopy(source);npm=result['variants']['NPM_ATLAS'];result['variants']={'NPM_ATLAS':npm}
vpm=source['variants']['VPM_UDIM'];phase_errors=[]
for entry in npm['entries']:
    ident=entry['finish_id']
    if ident not in shared.MATERIALS:continue
    mesh=old['meshes'][entry['mesh']];q=np.array(mesh['vertices'])[mesh['faces'][entry['face']]]
    period=np.array([.260,.150] if ident==5 else [.605,1.205])
    vpm_bias=np.array(vpm['phase_offsets_m'][str(ident)])
    bias=vpm_bias+32/1024-8/shared.NPM_DENSITY
    uv,region,density=shared.map_face(q,ident,'NPM_ATLAS',bias)
    entry.update(uv=uv,region_px=region,density=density)
    npm['phase_offsets_m'][str(ident)]=bias.tolist()
    actual=(np.array(uv)*2048-region[:2])/density
    projected=shared.project(q)
    expected=projected+vpm_bias+32/1024
    residual=np.mod(actual-expected+period/2,period)-period/2
    phase_errors.append(float(np.max(abs(residual))))
assert max(phase_errors)<1e-9
result['policy']='NPM OKS exempt from Ground density per PDF10 section6. Match accepted VPM material sizes and joint phase.'
result['approved_vpm_sha256']=shared.sha(root/'shared_v011/OBR22_K02_v011_VPM_UDIM.blend')
result['approved_vpm_texture_sha256']={p.name:shared.sha(p) for p in (root/'shared_v011').glob('VPM_Diffuse.*.png')}
result['npm_oks_density_requirement']='not_applicable'
result['max_planned_phase_error_m']=max(phase_errors)
(out/'shared-uv-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('NPM_SCALE_PREPARED:96 sampling px/m, same physical recipe and VPM phase')

"""Compare actual saved NPM UVs to approved VPM at matching physical face centers."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np

root=Path(sys.argv[sys.argv.index('--')+1]).resolve();out=root/'npm_v012'
d=json.loads((out/'shared-uv-manifest.json').read_text(encoding='utf-8'))
old=json.loads((root/'uv_trial/uv-manifest.json').read_text(encoding='utf-8'))
regions={e['face']:e['region_px'] for e in d['variants']['NPM_ATLAS']['entries'] if e['mesh']==0}

def read(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    m=bpy.data.meshes['BODY']
    return [{'q':np.array([list(m.vertices[i].co) for i in f.vertices]),
             'uv':np.array([list(m.uv_layers.active.data[i].uv) for i in f.loop_indices]),
             'id':m.attributes['finish_id'].data[f.index].value} for f in m.polygons]

npm=read(out/'OBR22_K02_v012_NPM_ATLAS.blend')
vpm_path=root/'shared_v011/OBR22_K02_v011_VPM_UDIM.blend'
vpm=read(vpm_path)
errors=[];scales=[]
for index,face in enumerate(vpm):
    ident=face['id']
    if ident not in (2,4,5):continue
    parent=old['vpm_meshes'][0]['parent_faces'][index];n=npm[parent]
    axis=int(np.argmin(np.ptp(n['q'],axis=0)))
    if axis==2:continue  # horizontal rims may choose another valid material direction
    axes=[a for a in (0,1,2) if a!=axis]
    transform=np.linalg.lstsq(np.c_[n['q'][:,axes],np.ones(4)],n['uv'],rcond=None)[0]
    center=face['q'].mean(0)
    n_uv=np.r_[center[axes],1.]@transform
    tile={4:1001,2:1002,5:1004}[ident]
    n_metric=(n_uv*2048-regions[parent][:2])/96
    v_metric=(face['uv'].mean(0)-[tile-1001,0])*4096/1024
    period=np.array([.260,.150] if ident==5 else [.605,1.205])
    delta=np.mod(n_metric-v_metric+period/2,period)-period/2
    errors.append(float(np.max(abs(delta))))
    singular=np.linalg.svd(transform[:2]*2048/96,compute_uv=False)
    scales.extend(singular.tolist())
assert max(errors)<2e-5,(max(errors))
assert max(abs(np.array(scales)-1))<2e-5
assert hashlib.sha256(vpm_path.read_bytes()).hexdigest()==d['approved_vpm_sha256']
for name,h in d['approved_vpm_texture_sha256'].items():
    assert hashlib.sha256((root/'shared_v011'/name).read_bytes()).hexdigest()==h
report={'scope':'saved vertical facade/reveal faces at matching coordinates; horizontal rims excluded from phase comparison',
        'compared_faces':len(errors),'max_phase_error_m':max(errors),'material_scale_ratio_min_max':[min(scales),max(scales)],
        'approved_vpm_and_four_maps_unchanged':True,'npm_oks_density_requirement':'not_applicable',
        'brick_face_m':[.25,.065],'tile_face_m':[.6,1.2],'source_pdf_page':10}
(out/'npm-vpm-scale-qa.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('NPM_VPM_SCALE_MATCH',len(errors),max(errors))

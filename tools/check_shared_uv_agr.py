"""Scoped invocation of the INSTALLED AGR Checker TD engine; never saves the scene."""
import importlib
import json
from pathlib import Path
import sys

import bpy

args=sys.argv[sys.argv.index('--')+1:]
out=Path(args[0]).resolve();addon=Path(args[1]).resolve()
sys.path.insert(0,str(addon.parent))
checker=importlib.import_module(addon.name+'.scripts.autochecks.check_utils').CheckUtils
report={'scope':'installed AGR Checker _calculate_td on BODY only; not full checker/export validation','variants':{}}
for variant in ('NPM_ATLAS','VPM_UDIM'):
    if variant=='NPM_ATLAS':
        report['variants'][variant]={'density_status':'not_applicable','reason':'OKS exempt: source PDF10 section6 item2. Ground-only density must not gate architecture.'}
        continue
    bpy.ops.wm.open_mainfile(filepath=str(out/f'OBR22_K02_v011_{variant}.blend'))
    obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.data.name=='BODY')
    known={p.index for p in obj.data.polygons if obj.data.attributes['finish_id'].data[p.index].value in (2,3,4,5)}
    resolutions={1001:2048} if variant=='NPM_ATLAS' else {i:4096 for i in range(1001,1005)}
    r=checker._calculate_td(obj,resolutions,variant=='VPM_UDIM')
    record={'body_faces':len(obj.data.polygons),'textured_faces':len(known),
            'known_td_less':sorted(known.intersection(r[5])), 'known_td_greater':sorted(known.intersection(r[6])),
            'known_margin_failures':sorted(known.intersection(r[7])),
            'all_td_less':list(r[5]),'all_td_greater':list(r[6]),'all_margin_failures':list(r[7]),
            'unused_tiles':r[4], 'unresolved_faces':len(obj.data.polygons)-len(known)}
    assert not record['known_td_less'] and not record['known_td_greater'] and not record['known_margin_failures'],record
    report['variants'][variant]=record
(out/'agr-scoped-qa.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('AGR_SCOPED_TD_OK')

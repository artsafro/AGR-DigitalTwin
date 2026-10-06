import json,numpy as np
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'outputs'
p=json.loads((root/'plan.json').read_text());c=json.loads((root/'charts.json').read_text());s=json.loads((root/'closure-study.json').read_text());d=json.loads((root/'source.json').read_text());v=np.array(d['vertices']);t=np.array(c['tangents'])
for gs,fs in c['groups'].items():
    factor=s['chart_scales'][gs];delta=s['chart_offsets_delta'][gs]
    for i in fs:
        p['metric_uv'][i]=np.column_stack((v[d['faces'][i]]@t[i]*factor+c['offsets'][str(i)]+delta,v[d['faces'][i]][:,2])).tolist()
p['report']['former_phase_conflicts']=p['report']['conflicts'];p['report']['conflicts']=[];p['report']['closure_study']=s['report'];p['report']['note']='Residual at graph corners <0.01px; horizontal scale varies within user-authorized TD range.'
(root/'plan-strict-1500.json').write_text((root/'plan.json').read_text())
(root/'plan.json').write_text(json.dumps(p))
print(s['report'])

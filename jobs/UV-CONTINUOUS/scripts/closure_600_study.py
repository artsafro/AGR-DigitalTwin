import json,numpy as np
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'outputs';d=json.loads((root/'source.json').read_text());c=json.loads((root/'charts.json').read_text());p=json.loads((root/'plan.json').read_text())
v=np.array(d['vertices']);t=np.array(c['tangents']);groups={int(k):ids for k,ids in c['groups'].items()};gids=list(groups);idx={g:i for i,g in enumerate(gids)};faceg={f:g for g,fs in groups.items() for f in fs};off={int(i):x for i,x in c['offsets'].items()};N=len(gids);rows=[];rhs=[];keys=set()
L=4096/600
for si,links in c['adj'].items():
    i=int(si)
    for j,_ in links:
        gi,gj=faceg[i],faceg[j]
        if gi==gj or i>j:continue
        common=set(d['faces'][i]).intersection(d['faces'][j])
        if not common:continue
        xyz=v[list(common)].mean(axis=0);a,b=idx[gi],idx[gj]
        k=(a,b,tuple(np.round(xyz[:2],4)))
        if k in keys:continue
        keys.add(k);ui=xyz@t[i];uj=xyz@t[j];res=ui+off[i]-uj-off[j];target=round(res/L)*L
        row=np.zeros(2*N);row[a]=ui;row[b]=-uj;row[N+a]=1;row[N+b]=-1;rows.append(row);rhs.append(target-res)
A=np.array(rows);rhs=np.array(rhs);weights=np.concatenate((np.ones(N),np.full(N,1e4)))
solution=weights*np.linalg.lstsq(A*weights,rhs,rcond=1e-7)[0];scales=1+solution[:N]
report={'charts':N,'constraints':len(rows),'horizontal_scale_range':[float(scales.min()),float(scales.max())],'td_range':[float(600*np.sqrt(scales.min())),float(600*np.sqrt(scales.max()))],'constraint_max_m':float(abs(A@solution-rhs).max()),'scope':'study only, not applied'}
(root/'closure-study.json').write_text(json.dumps({'report':report,'chart_scales':{str(g):float(scales[i]) for i,g in enumerate(gids)},'chart_offsets_delta':{str(g):float(solution[N+i]) for i,g in enumerate(gids)}},indent=2));print(json.dumps(report))

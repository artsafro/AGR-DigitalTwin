"""All-face near-parallel overlap check, both orientations; not Check Box Tool."""
import json,sys
from pathlib import Path
from collections import Counter
import numpy as np
from shapely.geometry import Polygon
src=Path(sys.argv[1]);out=Path(sys.argv[2]);tol=.005
fs=json.loads(src.read_text(encoding='utf-8'));pts=[np.array(f['points']) for f in fs]
ns=[]
for p in pts:
    # Welded/conformed borders can start with several collinear vertices.
    # Use the whole polygon area vector, not just its first three corners.
    q=p-p.mean(0)
    n=np.cross(q,np.roll(q,-1,axis=0)).sum(0);l=np.linalg.norm(n)
    ns.append(n/l if l>1e-12 else np.zeros(3))
ns=np.array(ns);centers=np.array([p.mean(0) for p in pts]);pairs=[]
lows=np.array([p.min(0) for p in pts]);highs=np.array([p.max(0) for p in pts])
for i,f in enumerate(fs):
    n=ns[i]
    if np.linalg.norm(n)<.9:continue
    dot=ns@n
    candidates=np.where((abs(dot)>.999999)&(abs((centers-pts[i][0])@n)<tol+1e-5))[0]
    drop=np.argmax(abs(n));axes=[k for k in range(3) if k!=drop];a=Polygon(pts[i][:,axes])
    candidates=candidates[np.all(np.minimum(highs[candidates][:,axes],highs[i,axes]) >
                                np.maximum(lows[candidates][:,axes],lows[i,axes]),axis=1)]
    for j in candidates:
        if j<=i:continue
        b=Polygon(pts[j][:,axes]);inter=a.intersection(b)
        area=inter.area
        if area<1e-7:continue
        dist=abs(float((centers[j]-pts[i][0])@n))
        if dist>=tol-1e-7:continue
        pairs.append({'a':[f['object'],f['index']],'b':[fs[j]['object'],fs[j]['index']],
          'distance_m':dist,'same_direction':bool(dot[j]>0),'projected_area_m2':float(area)})
def role(name):
    return 'window' if '_windows_' in name else 'ac' if '_ac_' in name else 'sill' if 'Sills' in name else 'body'
summary=Counter('/'.join(sorted([role(p['a'][0]),role(p['b'][0])])) for p in pairs)
report={'tool':'independent near-parallel area-overlap test (not Check Box Tool)',
        'tolerance_m':tol,'parallel_cosine_min':.999999,'area_threshold_m2':1e-7,
        'face_count':len(fs),'pair_count':len(pairs),'categories':dict(summary),
        'same_direction':sum(p['same_direction'] for p in pairs),'opposite_direction':sum(not p['same_direction'] for p in pairs),'pairs':pairs}
out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='pairs'}))

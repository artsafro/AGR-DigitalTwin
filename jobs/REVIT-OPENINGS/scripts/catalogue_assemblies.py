import json,hashlib
from pathlib import Path
from collections import Counter
import numpy as np
root=Path(__file__).resolve().parents[1];src=root/'outputs/source-v001';out=root/'outputs/library-v001'
inventory={r['name']:r for r in json.loads((src/'inventory.json').read_text(encoding='utf-8'))['objects']}
types=json.loads((src/'types-raw.json').read_text(encoding='utf-8'))
raw_by_name={n:t for t in types for n in t['instances']}
type_by_name=json.loads((src/'instance-types.json').read_text(encoding='utf-8'))
assemblies=json.loads((src/'assemblies-proximity.json').read_text(encoding='utf-8'))['assemblies']
transforms={}
for n,r in raw_by_name.items():
    m=np.array(inventory[n]['matrix']);sc=np.linalg.norm(m[:3,:3],axis=0)
    if np.linalg.det(m[:3,:3])<0:sc=-sc
    m[:3,:3]/=sc
    m[:3,3]+=m[:3,:3]@np.array(r['local_min'])
    transforms[n]=m
groups={}
for a in assemblies:
    variants=[]
    for k in range(4):
        ang=k*np.pi/2;c=round(np.cos(ang));s=round(np.sin(ang))
        R=np.array([[c,-s,0],[s,c,0],[0,0,1]])
        bb=np.array([[x,y,z] for x in [a['min'][0],a['max'][0]] for y in [a['min'][1],a['max'][1]] for z in [a['min'][2],a['max'][2]]])@R.T
        if np.ptp(bb,axis=0)[0]<np.ptp(bb,axis=0)[1]:continue
        origin=bb.min(axis=0)
        align=np.eye(4);align[:3,:3]=R;align[:3,3]=-origin
        sig=[];members=[]
        for n in a['members']:
            m=align@transforms[n];q=m.copy();q[:3,:3]=np.round(q[:3,:3],5);q[:3,3]=np.round(q[:3,3],4)
            sig.append((type_by_name[n],tuple(q[:3,:].flatten())))
            members.append({'source':n,'type':type_by_name[n],'matrix':m.tolist()})
        sig=repr(sorted(sig));variants.append((sig,align,members,(bb.max(axis=0)-origin).tolist()))
    sig,align,members,dims=min(variants,key=lambda x:x[0]);key=hashlib.sha256(sig.encode()).hexdigest()
    if key not in groups:groups[key]={'source_assembly':a['id'],'members':members,'dimensions':dims,'placements':[],'counts':{k:a[k] for k in ['panels','mullions','windows','doors']}}
    groups[key]['placements'].append({'assembly':a['id'],'to_world':np.linalg.inv(align).tolist(),'source_members':a['members']})
catalogue=list(groups.values())
catalogue.sort(key=lambda t:(-len(t['placements']),-len(t['members']),t['dimensions']))
for i,t in enumerate(catalogue,1):t['id']=f'CW_{i:03d}'
(out/'curtain-types.json').write_text(json.dumps(catalogue,ensure_ascii=False),encoding='utf-8')
(out/'source-transforms.json').write_text(json.dumps({n:m.tolist() for n,m in transforms.items()},ensure_ascii=False),encoding='utf-8')
print(json.dumps({'assemblies':len(assemblies),'types':len(catalogue),'singletons':sum(len(t['members'])==1 for t in catalogue),'frequent':[(t['id'],len(t['placements']),len(t['members']),[round(x,3) for x in t['dimensions']]) for t in catalogue[:10]]}))

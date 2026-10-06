import json, math
from pathlib import Path
from collections import Counter
import numpy as np
from PIL import Image, ImageDraw, ImageFont

root=Path(__file__).resolve().parents[1]
out=root/'outputs/source-v001'
types=json.loads((out/'types-raw.json').read_text(encoding='utf-8'))
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)

def components(t):
    v=np.array(t['vertices']); parents=list(range(len(v)))
    def find(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]]; i=parents[i]
        return i
    for f in t['faces']:
        for i in f[1:]: parents[find(i)]=find(f[0])
    groups={}
    for fi,f in enumerate(t['faces']): groups.setdefault(find(f[0]),[]).append(fi)
    result=[]
    for fis in groups.values():
        ids=sorted(set(i for fi in fis for i in t['faces'][fi])); p=v[ids]
        result.append({'faces':fis,'vertices':ids,'min':p.min(axis=0).tolist(),'max':p.max(axis=0).tolist(),
                       'dimensions':np.ptp(p,axis=0).tolist()})
    return result

comp={t['id']:components(t) for t in types}
(out/'components.json').write_text(json.dumps(comp),encoding='utf-8')
for cat in ['WINDOW','DOOR']:
    ts=sorted([t for t in types if t['category']==cat],key=lambda t:t['id'])
    for page in range(math.ceil(len(ts)/30)):
        image=Image.new('RGB',(1500,1200),'#f3f5f7'); d=ImageDraw.Draw(image)
        for ii,t in enumerate(ts[page*30:(page+1)*30]):
            x=(ii%6)*250;y=(ii//6)*240; v=np.array(t['vertices']); w,dep,h=t['dimensions']
            scale=min(214/max(w,0.1),172/max(h,0.1))
            def pt(p):return (x+125+(p[0]-w/2)*scale,y+185-p[2]*scale)
            for c in comp[t['id']]:
                cv=v[c['vertices']]; bounds=np.array([c['min'],c['max']]); dw,dd,dh=c['dimensions']
                is_panel=dw>0.12 and dh>0.12 and dd<0.06 and len(c['vertices'])<=12
                fill='#b9d6e5' if is_panel else '#b2b9c2'
                polys=[]
                for fi in c['faces']:
                    f=t['faces'][fi]; p=v[f]; n=np.cross(p[1]-p[0],p[2]-p[0]);
                    if abs(n[1])>1e-10: polys.append((float(p[:,1].mean()),[pt(q) for q in p]))
                for _,p in sorted(polys,reverse=True): d.polygon(p,fill=fill)
                # Draw only non-coplanar geometric feature edges.
                edges={}
                for fi in c['faces']:
                    f=t['faces'][fi];p=v[f];n=np.cross(p[1]-p[0],p[2]-p[0]); n=n/max(np.linalg.norm(n),1e-30)
                    for a,b in zip(f,f[1:]+f[:1]):edges.setdefault(tuple(sorted((a,b))),[]).append(n)
                for (a,b),ns in edges.items():
                    if len(ns)!=2 or abs(float(np.dot(ns[0],ns[1])))<0.99999:
                        d.line([pt(v[a]),pt(v[b])],fill='#343f4a',width=1)
            d.text((x+12,y+192),f"{t['id']}  ×{len(t['instances'])}",font=font,fill='#152334')
            d.text((x+12,y+214),f'{w*1000:.0f} × {h*1000:.0f} / {dep*1000:.0f} mm',font=small,fill='#495664')
        image.save(out/f'{cat.lower()}-source-{page+1:02d}.png')
for tid in ['WINDOW_021','WINDOW_034','WINDOW_027','DOOR_146','DOOR_096','DOOR_047']:
    print(tid,len(comp[tid]),[(len(c['vertices']),len(c['faces']),[round(x,4) for x in c['dimensions']]) for c in comp[tid]])

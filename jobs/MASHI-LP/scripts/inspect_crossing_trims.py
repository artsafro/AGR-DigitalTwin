import json
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,LineString
from shapely.ops import split
out=Path(__file__).resolve().parents[1]/'outputs/model-v002'
objects={o['name']:o for o in json.loads((out/'validated-geometry.json').read_text())}
report=json.loads((out/'crossing-check.json').read_text());rows=[];current={};skipped=[];connects=[]
def face_points(name,fi):
    if (name,fi) in current:return np.array(current[(name,fi)]['vertices'])
    obj=objects[name];return np.array(obj['vertices'])[obj['faces'][fi]]
for row in report['findings']:
    options=[]
    directions=[(row['a'],row['af'],row['b'],row['bf'])]
    if row['kind']=='new-new':directions.append((row['b'],row['bf'],row['a'],row['af']))
    for name,fi,other,oi in directions:
        pp=face_points(name,fi);qq=face_points(other,oi)
        n=np.cross(pp[1]-pp[0],pp[2]-pp[0]);n/=np.linalg.norm(n);nb=np.cross(qq[1]-qq[0],qq[2]-qq[0]);nb/=np.linalg.norm(nb)
        direct=np.cross(n,nb);direct/=np.linalg.norm(direct);origin=np.linalg.lstsq(np.array([n,nb,direct]),np.array([n@pp[0],nb@qq[0],0]),rcond=None)[0]
        u=(pp[1]-pp[0]);u/=np.linalg.norm(u);v=np.cross(n,u);poly=Polygon(np.column_stack(((pp-origin)@u,(pp-origin)@v)))
        d=np.array([direct@u,direct@v]);pieces=list(split(poly,LineString([-d*300,d*300])).geoms)
        if len(pieces)<2:continue
        keep=max(pieces,key=lambda p:p.area);loss=poly.area-keep.area
        verts=[(origin+u*x+v*y).tolist() for x,y in list(keep.exterior.coords)[:-1]]
        options.append({'object':name,'face':fi,'loss_m2':loss,'fraction':loss/poly.area,'vertices':verts})
    if options:
        best=min(options,key=lambda r:r['fraction'])
        if row['kind']=='new-old' and best['fraction']>.3:
            skipped.append(best)
            qq=face_points(row['b'],row['bf']);nn=np.cross(qq[1]-qq[0],qq[2]-qq[0]);nn/=np.linalg.norm(nn)
            connects.append({'object':row['a'],'face':row['af'],'normal':nn.tolist(),'point':qq[0].tolist(),'old_object':row['b'],'old_face':row['bf']})
            continue
        current[(best['object'],best['face'])]=best
rows=list(current.values())
(out/'trim-candidates.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
(out/'joint-connects.json').write_text(json.dumps(connects,indent=2),encoding='utf-8')
for r in rows:print(r['object'],r['face'],round(r['loss_m2'],5),round(r['fraction'],3),len(r['vertices']))
print('SKIPPED',len(skipped),[(r['object'],r['face'],round(r['fraction'],2)) for r in skipped])

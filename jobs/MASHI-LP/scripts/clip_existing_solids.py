"""Trim only new surfaces against the existing closed LP components."""
import json
from pathlib import Path
from collections import Counter
import numpy as np
from shapely.geometry import Polygon,LineString,shape,mapping
from shapely.ops import unary_union,polygonize
from shapely import set_precision,make_valid
out=Path(__file__).resolve().parents[1]/'outputs/model-v002'
old=json.loads((out/'lp-geometry.json').read_text());patches=json.loads((out/'candidate-patches.json').read_text())
solids=[]
for o in old:
    edges=Counter(tuple(sorted((a,b))) for f in o['faces'] for a,b in zip(f,f[1:]+f[:1]))
    if all(c==2 for c in edges.values()):solids.append((o['name'],np.array(o['vertices']),o['faces']))
def polygons(g):
    if g.geom_type=='Polygon':return [g]
    return [p for item in getattr(g,'geoms',[]) for p in polygons(item)]
cache={};result=[];cut_area=0;trimmed=[]
for patch in patches:
    n=np.array(patch['normal']);origin=np.array(patch['origin']);u=np.array(patch['u']);v=np.array(patch['v'])
    key=patch['plane_id']
    if key not in cache:
        masks=[]
        for name,pp,faces in solids:
            dist=(pp-origin)@n
            if dist.min()>-.00001 or dist.max()<.00001:continue
            lines=[];segments=[]
            for ids in faces:
                dd=dist[ids]
                if dd.min()>1e-7 or dd.max()<-1e-7:continue
                if np.max(np.abs(dd))<1e-7:continue
                points=[]
                for a,b in zip(ids,ids[1:]+ids[:1]):
                    da,db=dist[a],dist[b]
                    if abs(da)<1e-7:points.append(pp[a])
                    if da*db<-1e-14:points.append(pp[a]+(pp[b]-pp[a])*da/(da-db))
                unique={tuple(np.round(p,7)):p for p in points};points=list(unique.values())
                if len(points)<2:continue
                direction=points[1]-points[0];points.sort(key=lambda p:p@direction)
                for a,b in zip(points[::2],points[1::2]):
                    ab=np.array([[float((p-origin)@u),float((p-origin)@v)] for p in [a,b]])
                    if np.linalg.norm(ab[1]-ab[0])<1e-7:continue
                    line=set_precision(LineString(ab),.00001)
                    if not line.is_empty:lines.append(line)
            if not lines:continue
            network=unary_union(lines)
            parts=list(getattr(network,'geoms',[network]))
            for part in parts:
                if part.geom_type!='LineString':continue
                cc=list(part.coords);segments.extend(zip(cc,cc[1:]))
            regions=[]
            for poly in polygonize(network):
                pt=poly.representative_point();x,y=pt.x,pt.y;crosses=0
                for (ax,ay),(bx,by) in segments:
                    if (ay>y)!=(by>y) and x<ax+(y-ay)*(bx-ax)/(by-ay):crosses+=1
                if crosses%2:regions.append(poly)
            if regions:masks.append(unary_union(regions))
        cache[key]=unary_union(masks)
    poly=shape(patch['polygon']);mask=cache[key]
    remaining=make_valid(poly.difference(mask.buffer(.0002,join_style=2))) if not mask.is_empty else poly
    lost=max(0,poly.area-remaining.area);cut_area+=lost
    if lost>.00001:trimmed.append({'patch_id':patch['patch_id'],'removed_area_m2':lost})
    for part in polygons(remaining):
        if part.area<.02:continue
        row=dict(patch);row['polygon']=mapping(part.simplify(.0001,preserve_topology=True));row['area']=part.area;result.append(row)
(out/'candidate-patches-before-solids.json').write_text(json.dumps(patches),encoding='utf-8')
(out/'candidate-patches.json').write_text(json.dumps(result),encoding='utf-8')
(out/'solid-trim-report.json').write_text(json.dumps({'solids':[s[0] for s in solids],'removed_area_m2':cut_area,'trimmed':trimmed},indent=2),encoding='utf-8')
(out/'trim-candidates-before-solids.json').write_text((out/'trim-candidates.json').read_text(),encoding='utf-8')
(out/'trim-candidates.json').write_text('[]',encoding='utf-8')
print('SOLID_TRIM',len(trimmed),'patches',round(cut_area,3),'m2, output patches',len(result))

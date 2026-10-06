"""Measure source sill envelopes and identify existing wall reveal faces."""
import json,sys
from pathlib import Path
import numpy as np
from shapely.geometry import MultiPoint,Polygon
from shapely.ops import unary_union
from inspect_nodes import D,flatten
job=Path('jobs/GLB-NPM');out=job/'outputs/sills-ab-v003';out.mkdir(parents=True,exist_ok=True)
cfg={'reveal_definitions':[54944,121872],
     'sill_definitions':[143489,143674,143745,147514,146798,143480],
     'source_window_definition':77179,'source_ac_definition':146223}
floorcfg=json.loads((job/'reference-job.json').read_text(encoding='utf-8'))
excluded=set(cfg['reveal_definitions']+cfg['sill_definitions']+[77179,146223])
def instances(did,m=None):
    m=np.eye(4) if m is None else m
    for e in D[did]:
        if e['hidden'] or not e['layer_visible']:continue
        if 'definition_id' not in e:continue
        t=m@np.array(e['transform_inches']).reshape(4,4,order='F')
        if e['definition_id'] in excluded:yield e,t
        else:yield from instances(e['definition_id'],t)
def body_faces(did,m=None,mat=None):
    m=np.eye(4) if m is None else m
    for e in D[did]:
        if e['hidden'] or not e['layer_visible']:continue
        if 'definition_id' in e:
            if e['definition_id'] not in excluded:
                yield from body_faces(e['definition_id'],m@np.array(e['transform_inches']).reshape(4,4,order='F'),e.get('material') or mat)
        elif e['type']=='Face':
            p=np.array(e['points_inches']);p=(np.c_[p,np.ones(len(p))]@m.T)[:,:3]*.0254
            yield e,p
result={'excluded_definitions':sorted(excluded),'floors':{}}
for f in floorcfg['floors']:
    rows=list(body_faces(f['definition_id']));sills=[];reveals=[]
    for e,t in instances(f['definition_id']):
        d=e['definition_id']
        if d in cfg['sill_definitions']:
            pts=np.concatenate([p for q,p,mat in flatten(d,t)])
            hull=MultiPoint(np.round(pts[:,:2],6)).convex_hull.simplify(.00001,preserve_topology=True)
            xy=list(hull.exterior.coords)[:-1]
            assert len(xy)==4,(d,len(xy))
            zmin,zmax=pts[:,2].min(),pts[:,2].max()
            offset=f['z_offset_m']-floorcfg['definition_base_z_m']
            sills.append({'source_pid':e['persistent_id'],'definition_id':d,'xy':xy,
                          'bottom':float(zmin+offset),'top':float(zmax+offset)})
        elif d==77179:
            # Window family's original lower sills (495/10235) were removed with
            # the detailed frame in v002. Restore their common envelope as two
            # simple joined quads, omitting the 2.5 mm corner return detail.
            pts=[]
            for child in D[77179]:
                if child.get('definition_id') in [495,10235]:
                    ct=np.array(child['transform_inches']).reshape(4,4,order='F')
                    pts.extend(p for q,p,mat in flatten(child['definition_id'],ct))
            raw=np.concatenate(pts);mn,mx=raw.min(0),raw.max(0)
            cx,cy=-.65375,.37375
            quads=[[(mn[0],mn[1]),(cx,mn[1]),(cx,cy),(mn[0],mx[1])],
                   [(cx,cy),(mx[0],cy),(mx[0],mx[1]),(mn[0],mx[1])]]
            for j,xy in enumerate(quads):
                pts=np.array([(x,y,z) for z in [mn[2],mx[2]] for x,y in xy])
                tm=t.copy();tm[:3,3]*=.0254
                pts=(np.c_[pts,np.ones(len(pts))]@tm.T)[:,:3]
                offset=f['z_offset_m']-floorcfg['definition_base_z_m']
                sills.append({'source_pid':e['persistent_id'],'definition_id':[495,10235][j],
                  'xy':pts[:4,:2].tolist(),'bottom':float(pts[:,2].min()+offset),
                  'top':float(pts[:,2].max()+offset),'role':'window_lower_sill'})
        elif d in cfg['reveal_definitions']:
            tm=t.copy();tm[:3,3]*=.0254;iv=np.linalg.inv(tm);matches=[]
            for q,p in rows:
                local=(np.c_[p,np.ones(len(p))]@iv.T)[:,:3]
                mn,mx=local.min(0),local.max(0)
                if np.max(abs(local[:,0]))>.011 or mx[0]-mn[0]>.00001:continue
                if mn[1]<-.121 or mx[1]>.121:continue
                if mn[2]<-1.17 or mx[2]>1.19:continue
                if mx[1]-mn[1]<.23 or mx[2]-mn[2]<2.27:continue
                matches.append(q['persistent_id'])
            assert matches,('No underlying wall face',e['persistent_id'])
            reveals.append({'removed_instance_pid':e['persistent_id'],'existing_wall_face_pids':matches})
    window_sills=[s for s in sills if s.get('role')=='window_lower_sill']
    clipped=0
    for s in sills:
        if s.get('role'):continue
        cutters=[Polygon(w['xy']) for w in window_sills if min(w['top'],s['top'])>max(w['bottom'],s['bottom'])+1e-7]
        before=Polygon(s['xy']);after=before.difference(unary_union(cutters))
        if before.area-after.area>1e-7:
            assert after.geom_type=='Polygon' and len(after.interiors)==0
            xy=list(after.exterior.coords)[:-1]
            assert len(xy)==4,(s['source_pid'],len(xy))
            s['xy']=xy;s['trimmed_at_window_join']=True;clipped+=1
    result['floors'][f['label']]={'sills':sills,'reveals':reveals,'facade_sills_trimmed_at_window':clipped}
(out/'measured-sills-and-reveals.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
(job/'sill-reveal-job.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8')
print({k:{'sills':len(v['sills']),'reveal_overlays':len(v['reveals']),'wall_faces':len({i for r in v['reveals'] for i in r['existing_wall_face_pids']})} for k,v in result['floors'].items()})

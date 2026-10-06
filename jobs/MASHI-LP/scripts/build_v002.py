import bpy,json,hashlib,bmesh
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/model-v002')
assert Path(bpy.data.filepath).name=='input.blend'
data=json.loads((out/'new-meshes.json').read_text())
trims=json.loads((out/'trim-candidates.json').read_text()) if (out/'trim-candidates.json').exists() else []
joint_connects=json.loads((out/'joint-connects.json').read_text()) if (out/'joint-connects.json').exists() else []
def fingerprint(o):
    h=hashlib.sha256();h.update(str(tuple(tuple(r) for r in o.matrix_world)).encode())
    if o.type=='MESH':
        for v in o.data.vertices:h.update(str(tuple(v.co)).encode())
        for p in o.data.polygons:h.update(str((tuple(p.vertices),p.material_index)).encode())
        for layer in o.data.uv_layers:
            for uv in layer.data:h.update(str(tuple(uv.uv)).encode())
    return h.hexdigest()
before={o.name:fingerprint(o) for o in bpy.context.scene.objects}
groups=defaultdict(list)
def connect_boundary_junctions(vv,ff,src,pid):
    splits=0;welds=0
    while splits<500:
        edges=defaultdict(list)
        for fi,face in enumerate(ff):
            for k in range(4):edges[tuple(sorted((face[k],face[(k+1)%4])))].append((fi,k))
        points=np.array(vv);request=None
        for (ia,ib),links in edges.items():
            if len(links)!=1:continue
            a=points[ia];b=points[ib];delta=b-a;den=delta@delta
            if den<1e-12:continue
            t=((points-a)@delta)/den
            mask=(t>1e-5)&(t<1-1e-5)&(np.linalg.norm(points-(a+t[:,None]*delta),axis=1)<2e-5)
            mids=np.flatnonzero(mask)
            if len(mids):request=(*links[0],int(mids[0]));break
        if request is None:
            used=sorted({v for face in ff for v in face});mapping={v:i for i,v in enumerate(used)}
            vv[:]=[vv[i] for i in used];ff[:]=[[mapping[v] for v in face] for face in ff]
            return {'splits':splits,'near_endpoint_welds':welds}
        fi,k,mid=request;face=ff[fi];a,b,c,d=[face[(k+j)%4] for j in range(4)]
        close=min([a,b],key=lambda j:np.linalg.norm(points[mid]-points[j]))
        if np.linalg.norm(points[mid]-points[close])<.001 and not any(mid in f and close in f for f in ff):
            ff[:]=[[close if j==mid else j for j in f] for f in ff];vv[mid]=vv[close];welds+=1
            continue
        t=float((points[mid]-points[a])@(points[b]-points[a])/np.linalg.norm(points[b]-points[a])**2)
        q=points[d]+t*(points[c]-points[d]);near=np.flatnonzero(np.linalg.norm(points-q,axis=1)<2e-5)
        if len(near):op=int(near[0])
        else:op=len(vv);vv.append(q.tolist())
        assert len({a,mid,op,d})==4 and len({mid,b,c,op})==4
        ff[fi]=[a,mid,op,d];ff.append([mid,b,c,op]);src.append(src[fi]);pid.append(pid[fi]);splits+=1
    raise RuntimeError('Connect propagation limit')
for m in data:
    center=[sum(p[a] for p in m['vertices'])/len(m['vertices']) for a in range(3)]
    role=m['role']
    if role=='facade':role='courtyard_west' if center[0]<8 else 'courtyard_north'
    groups[role].append(m)
created=[]
for role,parts in groups.items():
    vv=[];ff=[];src=[];pid=[];lookup={}
    for part in parts:
        ids=[]
        for xyz in part['vertices']:
            key=tuple(round(v,5) for v in xyz)
            if key not in lookup:lookup[key]=len(vv);vv.append(xyz)
            ids.append(lookup[key])
        for face in part['faces']:
            ff.append([ids[i] for i in face]);src.append(part['source_plane']);pid.append(part['patch_id'])
    connects=connect_boundary_junctions(vv,ff,src,pid)
    trim_count=0
    selected={t['face']:t for t in trims if t['object']=='LP_Add_'+role}
    for cut in joint_connects:
        if cut['object']=='LP_Add_'+role and cut['face'] not in selected:
            selected[cut['face']]={'face':cut['face'],'vertices':[vv[i] for i in ff[cut['face']]]}
    for trim in selected.values():
        fi=trim['face'];poly=[np.array(p) for p in trim['vertices']]
        old=[np.array(vv[i]) for i in ff[fi]];normal=np.cross(old[1]-old[0],old[2]-old[0])
        if np.cross(poly[1]-poly[0],poly[2]-poly[0])@normal<0:poly=list(reversed(poly))
        polygons=[poly]
        for cut in joint_connects:
            if cut['object']!='LP_Add_'+role or cut['face']!=fi:continue
            n=np.array(cut['normal']);point=np.array(cut['point']);divided=[]
            for poly in polygons:
                ds=[float((p-point)@n) for p in poly]
                if min(ds)>-1e-5 or max(ds)<1e-5:divided.append(poly);continue
                for sign in [-1,1]:
                    part=[]
                    for a,b,da,db in zip(poly,poly[1:]+poly[:1],ds,ds[1:]+ds[:1]):
                        if sign*da>=-1e-7:part.append(a)
                        if da*db<-1e-14:part.append(a+(b-a)*da/(da-db))
                    if len(part)>=3:divided.append(part)
            polygons=divided
        quads=[]
        for poly in polygons:
            if len(poly)==4:quads.append(poly)
            else:
                center=np.mean(poly,axis=0);mids=[(a+b)/2 for a,b in zip(poly,poly[1:]+poly[:1])]
                quads.extend([[p,mids[i],center,mids[i-1]] for i,p in enumerate(poly)])
        replacement=[]
        for quad in quads:
            ids=[]
            for p in quad:
                near=np.flatnonzero(np.linalg.norm(np.array(vv)-p,axis=1)<1e-5)
                if len(near):ids.append(int(near[0]))
                else:ids.append(len(vv));vv.append(p.tolist())
            replacement.append(ids)
        ff[fi]=replacement[0]
        for extra in replacement[1:]:ff.append(extra);src.append(src[fi]);pid.append(pid[fi])
        trim_count+=1
    if trim_count:connects['after_trim']=connect_boundary_junctions(vv,ff,src,pid)
    mesh=bpy.data.meshes.new('LP_Add_'+role);mesh.from_pydata(vv,[],ff);mesh.update()
    assert all(len(p.vertices)==4 for p in mesh.polygons)
    a=mesh.attributes.new('revit_source_plane','INT','FACE');a.data.foreach_set('value',src)
    a=mesh.attributes.new('audit_patch_id','INT','FACE');a.data.foreach_set('value',pid)
    obj=bpy.data.objects.new('LP_Add_'+role,mesh);bpy.data.collections['LP'].objects.link(obj)
    obj['model_stage']='quad_surface_no_shell';obj['reference']='Revit current; source mapping model-v002/new-meshes.json'
    bm=bmesh.new();bm.from_mesh(mesh)
    created.append({'name':obj.name,'vertices':len(vv),'quads':len(ff),'joint_trims':trim_count,'connect_splits':connects,'zero_area':sum(f.calc_area()<1e-9 for f in bm.faces),
        'nonmanifold_more_than_two':sum(len(e.link_faces)>2 for e in bm.edges),'boundary_edges':sum(e.is_boundary for e in bm.edges)})
    bm.free()
assert all(fingerprint(bpy.data.objects[n])==h for n,h in before.items())
for c in ['LP','Revit','LP_old']:
    for o in bpy.data.collections[c].objects:o.hide_set(c!='LP');o.hide_render=c!='LP';o.select_set(False)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'LP_completed-v002.blend'))
(out/'build-report.json').write_text(json.dumps({'preserved_object_signatures':before,'created':created,'originals_unchanged':True,'no_shell':True},indent=2),encoding='utf-8')
print(json.dumps(created),flush=True)
# Reuse the same diagnostic cameras and coverage code as the first audit.
script=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/scripts/audit_offline.py').read_text()
script=script.replace('outputs/audit-v001','outputs/model-v002')
exec(compile(script,'audit_offline_v002','exec'))

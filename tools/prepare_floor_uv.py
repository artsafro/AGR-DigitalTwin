"""Source-traced instancing and atlas/UDIM layout experiment, not final PBR delivery."""
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from quad_connect import subdivide

PALETTE={0:[220,50,170],2:[214,214,214],4:[106,106,114],5:[181,154,143],6:[69,73,78],7:[69,73,78],90:[100,137,151]}
ID_COLORS={0:[255,0,255],2:[60,200,80],4:[80,110,240],5:[230,130,30],6:[240,230,60],7:[160,70,230],90:[30,200,230]}


def pack(rectangles,size,pad,density,one_tile=False):
    boxes=[]
    for index,(width,height) in enumerate(rectangles):
        effective=min(density,(size-2*pad-1)/max(width,height))
        w=max(1,math.ceil(width*effective));h=max(1,math.ceil(height*effective))
        boxes.append((index,w+2*pad,h+2*pad,effective))
    shelves=[];result={}
    for index,w,h,effective in sorted(boxes,key=lambda b:(-b[2],-b[1],b[0])):
        selected=None
        for shelf in shelves:
            if h<=shelf['h'] and shelf['x']+w<=size:
                selected=shelf;break
        if selected is None:
            tiles=sorted({s['tile'] for s in shelves}) or [0]
            for tile in tiles:
                y=max((s['y']+s['h'] for s in shelves if s['tile']==tile),default=0)
                if y+h<=size:
                    selected={'tile':tile,'y':y,'h':h,'x':0};shelves.append(selected);break
            if selected is None:
                if one_tile:return None
                selected={'tile':max(tiles)+1,'y':0,'h':h,'x':0};shelves.append(selected)
        result[index]={'tile':selected['tile'],'x':selected['x']+pad,'y':selected['y']+pad,
                       'width':w-2*pad,'height':h-2*pad,'density':effective}
        selected['x']+=w
    return result


def main(p):
    out=p/'uv_trial';out.mkdir(exist_ok=True)
    source=json.loads((p/'shell-windows-optimized.json').read_text(encoding='utf-8'))
    profiles=json.loads((p/'exterior-surface.json').read_text(encoding='utf-8'))
    walls=json.loads((p/'body-build.json').read_text(encoding='utf-8'))['wall_records']
    angle=source['angle'];R=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    body=source['meshes'][0];v=np.array(body['vertices']);v[:,:2]=v[:,:2]@R
    run_ids=[];run_records=[]
    for ri,run in enumerate(profiles['profiles'],1):
        names=[walls[i-1]['props'].get('revit_type_name','') for i in run['source_ids']]
        candidates=set()
        for name in names:
            if '(кирп)' in name.lower():candidates.add(5)
            if '(Бел)' in name:candidates.add(2)
            if '(Син)' in name:candidates.add(4)
        finish=next(iter(candidates)) if len(candidates)==1 else 0
        run_records.append({'run':ri,'finish_id':finish,'candidates':sorted(candidates),'source_wall_indices':run['source_ids'],
                            'source_type_names':sorted(set(names)),'status':'candidate_from_Revit_type_and_PDF_legend' if finish else 'mixed_gable_finish_requires_spatial_mask'})
    for fi,face in enumerate(body['faces']):
        q=v[face]
        if fi<profiles['quads']:ri=int(np.load(p/'exterior-surface.npz')['facade_indices'][fi])
        else:
            candidates=[]
            for index,run in enumerate(profiles['profiles'],1):
                a,u=run['axis'],run['along_axis'];on=q[abs(q[:,a]-run['start'][a])<5e-6]
                if len(on)<2:continue
                lo,hi=sorted([run['start'][u],run['end'][u]])
                if on[:,u].min()>=lo-5e-6 and on[:,u].max()<=hi+5e-6:candidates.append(index)
            ri=candidates[0] if len(candidates)==1 else 0
        run_ids.append(ri)
    body={**body,'vertices':v.tolist(),'finish_ids':[run_records[ri-1]['finish_id'] if ri else 0 for ri in run_ids],
          'facade_runs':run_ids,'key':'BODY'}
    meshes=[body];instances=[];types={};errors=[]
    for mesh,w in zip(source['meshes'][1:],source['windows']):
        q=np.array(mesh['vertices']);q[:,:2]=q[:,:2]@R
        a,u,sg=w['axis'],w['along_axis'],w['outward_sign'];t=sg if a==1 else -sg
        x0,z0,x1,z1=w['opening_bounds'];center=(x0+x1)/2
        local=np.stack([(q[:,u]-center)*t,(q[:,a]-w['frame_plane'])*sg,q[:,2]-z0],axis=1)
        if w['type'] not in types:
            key='WINDOW_TYPE_'+str(len(types)+1);types[w['type']]=len(meshes)
            frame_id=7 if 'лоджия' in w['type'] else 6
            meshes.append({**mesh,'vertices':local.tolist(),'key':key,'name':key,
                           'finish_ids':[90 if m==2 else frame_id for m in mesh['materials']],
                           'source_type':w['type'],'representative_revit_id':w['id']})
        index=types[w['type']];reference=np.array(meshes[index]['vertices'])
        scale=np.ones(3);scale[[0,2]]=np.ptp(local,axis=0)[[0,2]]/np.ptp(reference,axis=0)[[0,2]]
        shift=local.min(0)-reference.min(0)*scale;shift[1]=0
        fitted=reference*scale+shift
        distances=np.linalg.norm(fitted[:,None]-local[None,:],axis=2)
        error=float(max(distances.min(0).max(),distances.min(1).max()));assert error<.001,(w['id'],error,scale.tolist(),shift.tolist())
        M=np.eye(4);M[:3,:3]=0;M[u,0]=t;M[a,1]=sg;M[2,2]=1;M[u,3]=center;M[a,3]=w['frame_plane'];M[2,3]=z0
        fit=np.eye(4);fit[:3,:3]=np.diag(scale);fit[:3,3]=shift
        world=np.eye(4);world[:2,:2]=R;M=world@M@fit
        instances.append({'name':mesh['name'],'mesh_key':meshes[index]['key'],'matrix':M.tolist(),'revit_id':w['id'],
                          'source_type':w['type'],'normalization_max_error_m':error})
        errors.append(error)
    world=np.eye(4);world[:2,:2]=R
    instances.insert(0,{'name':body['name'],'mesh_key':'BODY','matrix':world.tolist()})
    # User-authorized VPM Connect cuts; master and NPM keep accepted topology.
    vpm_meshes=[]
    for mesh in meshes:
        vv,ff,parents=subdivide(mesh['vertices'],mesh['faces'],3.9)
        vpm_meshes.append({**mesh,'vertices':vv.tolist(),'faces':ff.tolist(),
                           'materials':[mesh['materials'][i] for i in parents],
                           'finish_ids':[mesh['finish_ids'][i] for i in parents],'parent_faces':parents})
    def islands_for(selected):
        rectangles=[];islands=[]
        for mi,mesh in enumerate(selected):
            vv=np.array(mesh['vertices'])
            for fi,face in enumerate(mesh['faces']):
                q=vv[face];axis=int(np.argmin(np.ptp(q,axis=0)));uv=q[:,[a for a in range(3) if a!=axis]].copy()
                signed=np.sum(uv[:,0]*np.roll(uv[:,1],-1)-uv[:,1]*np.roll(uv[:,0],-1))
                if signed<0:uv[:,0]*=-1
                uv-=uv.min(0);size=uv.max(0);assert min(size)>0
                rectangles.append(tuple(size));islands.append({'mesh':mi,'face':fi,'local_uv':uv.tolist(),'finish_id':mesh['finish_ids'][fi]})
        return rectangles,islands
    rectangles,islands=islands_for(meshes)
    low,high=1.,100.
    for _ in range(20):
        mid=(low+high)/2
        if pack(rectangles,2048,8,mid,True):low=mid
        else:high=mid
    layouts={}
    for variant,size,pad,density in [('NPM_ATLAS',2048,8,low),('VPM_UDIM',4096,32,514.)]:
        rectangles,islands=islands_for(vpm_meshes if variant=='VPM_UDIM' else meshes)
        placed=pack(rectangles,size,pad,density,variant=='NPM_ATLAS');entries=[]
        for i,island in enumerate(islands):
            box=placed[i];uv=np.array(island['local_uv'])*box['density'];uv+=np.array([box['x'],box['y']]);uv/=size
            # Glass has separate untextured material in VPM: its UV remains in1001.
            tile=0 if variant=='VPM_UDIM' and island['finish_id']==90 else box['tile']
            uv+=np.array([tile%10,tile//10])
            entries.append({**island,**box,'tile':tile,'udim':1001+tile,'uv':uv.tolist()})
        used=sorted({e['tile'] for e in entries if not (variant=='VPM_UDIM' and e['finish_id']==90)})
        assert used==list(range(max(used)+1)) and max(used)<100
        for tile in used:
            img=Image.new('RGB',(size,size),(35,35,35));ids=Image.new('RGB',(size,size),(0,0,0));draw=ImageDraw.Draw(img);iddraw=ImageDraw.Draw(ids)
            for entry in entries:
                if entry['tile']!=tile or (variant=='VPM_UDIM' and entry['finish_id']==90):continue
                points=[(int((u-tile%10)*size),int((1-(v-tile//10))*size)) for u,v in entry['uv']]
                # Dilate the whole island boundary into the reserved padding.
                for target,color in [(draw,PALETTE[entry['finish_id']]),(iddraw,ID_COLORS[entry['finish_id']])]:
                    target.polygon(points,fill=tuple(color));target.line(points+[points[0]],fill=tuple(color),width=2*pad)
            name=f'{variant}_Diffuse_PREVIEW.{1001+tile}.png';img.save(out/name)
            if variant=='NPM_ATLAS':ids.save(out/'NPM_MaterialID_preview.png')
        layouts[variant]={'size':size,'padding':pad,'density_target':density,'tiles':[1001+t for t in used],
                         'density_exceptions':[{'mesh':e['mesh'],'face':e['face'],'density':e['density']} for e in entries if variant=='VPM_UDIM' and e['density']<511.99 and e['finish_id']!=90],
                         'entries':entries}
    result={'meshes':meshes,'vpm_meshes':vpm_meshes,'instances':instances,'layouts':layouts,'run_material_candidates':run_records,
            'palette':PALETTE,'id_colors':ID_COLORS,'instance_types':{name:meshes[index]['key'] for name,index in types.items()},
            'normalization_max_error_m':max(errors),'source_pdf_pages':[14,15],'printed_sheet_numbers':[15,16],
            'master_material_slots':[{'blender_index':i,'material_id_1based':i+1,'finish_id':ident,'pdf_reference':ident if ident in [2,4,5,6,7] else None} for i,ident in enumerate(PALETTE)],
            'material_policy':'User selected PDF14-15 over conflicting PDF18/Revit material descriptions',
            'material_assignment_status':'Revit type-to-PDF legend proposals; mixed gables remain UNRESOLVED magenta',
            'texture_status':'Diffuse colour layout previews only; not calibrated RAL or final PBR. No invented ERM/Normal.',
            'source_geometry_accepted_by_user':True,'passed':False}
    (out/'uv-manifest.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'types':len(types),'instances':len(instances)-1,'max_normalization_m':max(errors),
                      'atlas_density':low,'udims':layouts['VPM_UDIM']['tiles'],'density_exceptions':len(layouts['VPM_UDIM']['density_exceptions']),
                      'unresolved_body_faces':Counter(body['finish_ids'])[0]}))


if __name__=='__main__':main(Path(sys.argv[1]))

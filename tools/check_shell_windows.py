"""Plane-pair overlap/intersection audit for orthogonal saved shell/window meshes."""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon, LineString, Point
from shapely import union_all, hausdorff_distance


def audit(data):
    angle=data['angle'];R=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    polygons=[];axes=[];planes=[];owners=[];bounds=[];projections=[]
    invalid=duplicate_vertices=duplicate_faces=bad_edges=bad_boundaries=bad_winding=0
    all_vertices=[];minimum_edge=float('inf')
    for mi,mesh in enumerate(data['meshes']):
        v=np.array(mesh['vertices']);v[:,:2]=v[:,:2]@R
        all_vertices.extend(v.tolist())
        f=np.array(mesh['faces']);assert f.shape[1]==4
        duplicate_vertices+=len(v)-len(np.unique(np.round(v,6),axis=0))
        duplicate_faces+=len(f)-len(np.unique(np.sort(f,axis=1),axis=0))
        edges=np.sort(np.stack([f,np.roll(f,-1,axis=1)],axis=2).reshape(-1,2),axis=1)
        unique,inverse,counts=np.unique(edges,axis=0,return_inverse=True,return_counts=True);bad_edges+=int((counts>2).sum())
        directed=np.stack([f,np.roll(f,-1,axis=1)],axis=2).reshape(-1,2)
        winding=np.bincount(inverse,weights=np.where(directed[:,0]<directed[:,1],1,-1))
        bad_winding+=int(((counts==2)&(winding!=0)).sum())
        minimum_edge=min(minimum_edge,float(np.linalg.norm(v[unique[:,1]]-v[unique[:,0]],axis=1).min()))
        boundary=unique[counts==1];_,degree=np.unique(boundary,return_counts=True)
        bad_boundaries+=int((degree!=2).sum())
        if mi:
            w=data['windows'][mi-1];u=w['along_axis'];a=w['axis'];x0,z0,x1,z1=w['opening_bounds']
            for edge in boundary:
                q=v[edge];on_outline=(np.all(abs(q[:,u]-(x0-.01))<5e-6) or np.all(abs(q[:,u]-(x1+.01))<5e-6) or np.all(abs(q[:,2]-(z0-.01))<5e-6) or np.all(abs(q[:,2]-(z1+.01))<5e-6))
                bad_boundaries+=int(not on_outline or np.any(abs(q[:,a]-w['frame_plane'])>5e-6))
        for face in f:
            q=v[face];axis=int(np.argmin(np.ptp(q,axis=0)));projection=[a for a in range(3) if a!=axis]
            poly=Polygon(q[:,projection]);normal=np.cross(q[1]-q[0],q[2]-q[0])
            invalid+=int(np.ptp(q[:,axis])>5e-6 or not poly.is_valid or poly.area<1e-10 or poly.convex_hull.area-poly.area>1e-7)
            polygons.append(poly);axes.append(axis);planes.append(q[:,axis].mean());owners.append(mi)
            bounds.append([q.min(0),q.max(0)]);projections.append(projection)
    bounds=np.array(bounds);axes=np.array(axes);planes=np.array(planes);owners=np.array(owners)
    overlaps=[];crossings=[];embedded=[]
    for i,p in enumerate(polygons):
        candidates=np.where(np.all(bounds[i,1]+5e-6>=bounds[:,0],axis=1)&np.all(bounds[:,1]+5e-6>=bounds[i,0],axis=1)&(np.arange(len(polygons))>i))[0]
        for j in candidates:
            q=polygons[j]
            if axes[i]==axes[j]:
                if abs(planes[i]-planes[j])<5e-6:
                    area=p.intersection(q).area
                    if area>1e-7:overlaps.append([i,int(j),float(area),int(owners[i]),int(owners[j])])
                continue
            c=3-axes[i]-axes[j]
            low=max(bounds[i,0,c],bounds[j,0,c]);high=min(bounds[i,1,c],bounds[j,1,c])
            if high-low<1e-5:continue
            # Exact intersection along the shared axis, then exclude boundary-only contact.
            def line(index):
                a=np.zeros(3);b=np.zeros(3)
                a[axes[i]]=b[axes[i]]=planes[i];a[axes[j]]=b[axes[j]]=planes[j]
                a[c]=low;b[c]=high
                return LineString([a[projections[index]],b[projections[index]]])
            pi=p.intersection(line(i));qj=q.intersection(line(j))
            if pi.is_empty or qj.is_empty:continue
            def intervals(g,index):
                geoms=[g] if g.geom_type=='LineString' else list(getattr(g,'geoms',[]))
                k=projections[index].index(c)
                return [(min(t[k] for t in h.coords),max(t[k] for t in h.coords)) for h in geoms if h.geom_type=='LineString']
            for l,h in intervals(pi,i):
                for ll,hh in intervals(qj,j):
                    lo,hi=max(l,ll),min(h,hh)
                    if hi-lo<1e-5:continue
                    point=np.zeros(3);point[axes[i]]=planes[i];point[axes[j]]=planes[j];point[c]=(lo+hi)/2
                    if not p.buffer(-5e-6).contains(Point(point[projections[i]])) or not q.buffer(-5e-6).contains(Point(point[projections[j]])):continue
                    record=[i,int(j),float(hi-lo),int(owners[i]),int(owners[j])]
                    # Deliberate 10mm lateral frame embed is distinct from coplanar overlap.
                    if min(owners[i],owners[j])==0 and max(owners[i],owners[j])>0:
                        wi=max(owners[i],owners[j])-1;w=data['windows'][wi]
                        window_face=i if owners[i]>0 else j
                        u=w['along_axis'];x0,z0,x1,z1=w['opening_bounds']
                        on_jamb=min(abs(point[u]-x0),abs(point[u]-x1),abs(point[2]-z0),abs(point[2]-z1))<5e-6
                        if on_jamb and axes[window_face]==w['axis'] and abs(planes[window_face]-w['frame_plane'])<5e-6 and 0<w['recess_m']<.4 and w['lateral_embed_m']>=.01:
                            embedded.append(record);continue
                    crossings.append(record)
    global_duplicates=len(all_vertices)-len(np.unique(np.round(all_vertices,6),axis=0))
    result={'quads':len(polygons),'objects':len(data['meshes']),'invalid_or_nonconvex_faces':invalid,
            'global_duplicate_vertices':global_duplicates,'invalid_boundary_vertices_or_edges':bad_boundaries,
            'inconsistent_shared_edge_winding':bad_winding,'minimum_edge_m':minimum_edge,
            'duplicate_vertices':duplicate_vertices,'duplicate_faces':duplicate_faces,'edges_with_more_than_two_faces':bad_edges,
            'coplanar_overlaps':overlaps,'unapproved_crossings':crossings,'documented_frame_embed_crossings':len(embedded),
            'passed':False,'scope':'Orthogonal faces; 5um plane/edge tolerance, 1e-7m2 overlap area threshold'}
    result['geometry_checks_passed']=not(any([invalid,duplicate_vertices,duplicate_faces,global_duplicates,bad_edges,bad_boundaries,bad_winding]) or overlaps or crossings)
    return result


def compare_surfaces(original,changed):
    def groups(data,reference=None):
        angle=data['angle'];R=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        result=defaultdict(list)
        for mi,m in enumerate(data['meshes']):
            v=np.array(m['vertices']);v[:,:2]=v[:,:2]@R
            for face,material in zip(m['faces'],m['materials']):
                q=v[face];axis=int(np.argmin(np.ptp(q,axis=0)));projection=[a for a in range(3) if a!=axis]
                plane=float(q[:,axis].mean());key=(mi,material,axis,round(plane,4))
                if reference is not None:
                    candidates=[k for k in reference if k[:3]==key[:3]]
                    key=min(candidates,key=lambda k:abs(k[3]-plane))
                    assert abs(key[3]-plane)<.000055
                result[key].append(Polygon(q[:,projection]))
        return {key:union_all(polys) for key,polys in result.items()}
    before=groups(original);after=groups(changed,before)
    assert before.keys()==after.keys()
    error=max(float(hausdorff_distance(before[k],after[k])) for k in before)
    assert error<5e-6,error
    return {'surface_groups_compared':len(before),'surface_hausdorff_m':error,'source_surfaces_preserved':True}


if __name__=='__main__':
    p=Path(sys.argv[1]);name='shell-windows-readback.json' if '--readback' in sys.argv else 'shell-windows.json'
    if '--optimized' in sys.argv:name=name.replace('shell-windows','shell-windows-optimized')
    data=json.loads((p/name).read_text(encoding='utf-8'));result=audit(data)
    if '--optimized' in sys.argv:
        result.update(compare_surfaces(json.loads((p/'shell-windows.json').read_text(encoding='utf-8')),data))
    (p/('shell-windows-optimized-qa.json' if '--optimized' in sys.argv else 'shell-windows-qa.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({**result,'coplanar_overlaps':result['coplanar_overlaps'][:5],'unapproved_crossings':result['unapproved_crossings'][:5]}))
    sys.exit(0 if result['geometry_checks_passed'] else 1)

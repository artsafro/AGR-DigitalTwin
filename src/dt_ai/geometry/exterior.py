"""Parameterized exterior-only surface, before Shell: measured perimeter and openings.

Source solid is used only to extract outward-most vertical profiles. Interior
walls never become output faces. Sub-millimetre coordinate noise is consolidated
with a recorded 1 mm budget; real 50 mm+ perimeter steps remain.
"""

import numpy as np
import shapely
from shapely.geometry import Polygon, Point
from shapely.geometry.polygon import orient

from dt_ai.geometry.grid_patches import rectangles


def clustered(values, span=.001):
    groups=[]
    for value in sorted(set(map(float,values))):
        if not groups or value-groups[-1][0]>span:
            groups.append([value])
        else:
            groups[-1].append(value)
    return {v:(g[0]+g[-1])/2 for g in groups for v in g}


def clean_ring(coords, span=.001):
    q=np.array(coords[:-1])
    mappings=[clustered(q[:,a], span) for a in range(2)]
    q=[tuple(mappings[a][v[a]] for a in range(2)) for v in q]
    q=[v for i,v in enumerate(q) if v!=q[i-1]]
    polygon=Polygon(q)
    if not polygon.is_valid:
        # Snapped sub-mm jogs may collapse to zero-width spikes. Keep the area
        # component only; the independent boundary-distance gate below remains.
        fixed=shapely.make_valid(polygon)
        polygon=shapely.union_all(parts(fixed))
    if polygon.geom_type!='Polygon' or polygon.interiors or not polygon.is_valid:
        raise ValueError('Perimeter normalization changed the outline topology')
    polygon=orient(polygon.simplify(1e-10,preserve_topology=True),sign=1)
    return polygon


def parts(geometry):
    if geometry.geom_type=='Polygon':return [geometry]
    return [p for p in geometry.geoms if p.geom_type=='Polygon']


def extract_exterior(data, windows, *, height_m, coordinate_budget_m,
                     microgap_closure_m, opening_match_m, window_plane_distance_m,
                     wall_top_policy, units, height_basis):
    """Prepared local occupancy grid -> exterior quads/provenance, no file I/O.

    windows: explicit source IDs and local (grid-axis) min/max bounds.
    Grid z=0 is floor base. Only one orthogonal outside perimeter is supported.
    """
    import math
    if units != 'm' or not height_basis.strip():
        raise ValueError('Metres and an explicit height basis are required')
    if wall_top_policy != 'extend_to_height_record_unmatched_top_gaps':
        raise ValueError('Unsupported wall-top policy; manual decision required')
    for value in (height_m, coordinate_budget_m, opening_match_m, window_plane_distance_m):
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Height and tolerances must be finite and positive')
    if not math.isfinite(microgap_closure_m) or microgap_closure_m < 0:
        raise ValueError('Invalid microgap closure')
    axes=[np.asarray(data[k],dtype=float) for k in 'xyz']
    if any(a.ndim!=1 or len(a)<2 or not np.isfinite(a).all() or not (np.diff(a)>0).all() for a in axes):
        raise ValueError('Grid axes must be finite and strictly increasing')
    owner=np.asarray(data['owner']).copy()
    if owner.shape != tuple(len(a)-1 for a in axes) or not np.issubdtype(owner.dtype,np.integer) or (owner<0).any():
        raise ValueError('Invalid grid ownership shape or labels')
    if not np.isfinite(float(data['angle'])) or axes[2][0]>0 or axes[2][-1]<=0:
        raise ValueError('Grid requires finite rotation and local floor base z=0')
    for w in windows:
        lo,hi=np.asarray(w['min']),np.asarray(w['max'])
        if not isinstance(w['id'],str) or not w['id'] or lo.shape!=(3,) or hi.shape!=(3,) or not np.isfinite([lo,hi]).all() or (lo>hi).any():
            raise ValueError('Invalid explicitly selected window bounds')
    if len({w['id'] for w in windows}) != len(windows):
        raise ValueError('Duplicate selected window ID')
    height=float(height_m)
    owner[:,:,axes[2][:-1]<-1e-8]=0
    footprint=shapely.union_all([shapely.box(axes[0][a],axes[1][c],axes[0][b],axes[1][d])
                               for a,b,c,d,_ in rectangles((owner>0).any(axis=2))])
    if footprint.geom_type!='Polygon':
        raise ValueError('Multiple source footprint components require explicit selection')
    raw_footprint=footprint
    # A sub-mm source gap must not route the outside contour through a room.
    # Repair only the footprint used for exterior classification; keep the
    # measured vertical profiles as the opening/height source.
    footprint=footprint.buffer(microgap_closure_m/2,join_style='mitre').buffer(-microgap_closure_m/2,join_style='mitre')
    if footprint.geom_type!='Polygon':raise ValueError('Exterior footprint repair split the component')
    repair_area=float(footprint.symmetric_difference(raw_footprint).area)
    original=orient(Polygon(footprint.exterior),sign=1)
    contour=clean_ring(list(original.exterior.coords), coordinate_budget_m)
    distance=float(shapely.hausdorff_distance(original.boundary,contour.boundary))
    if distance>coordinate_budget_m:
        raise ValueError('Perimeter changed beyond configured precision budget')
    corners=np.array(contour.exterior.coords[:-1])
    runs=[]
    for start,end in zip(corners,np.roll(corners,-1,axis=0)):
        direction=end-start
        u=int(np.argmax(abs(direction)));a=1-u
        if abs(direction[a])>1e-9:raise ValueError('Non-orthogonal exterior segment')
        sign=1 if direction[u]>0 else -1
        outward=np.array([direction[1],-direction[0]])/np.linalg.norm(direction)
        run={'start':start.tolist(),'end':end.tolist(),'axis':a,'along_axis':u,
             'outward':outward.tolist(),'length_m':float(np.linalg.norm(direction)),
             'raw_profiles':[],'source_ids':set()}
        # Recover each raw perimeter piece assigned to the normalized run.
        raw=np.array(original.exterior.coords)
        for s,e in zip(raw[:-1],raw[1:]):
            du=e-s
            if abs(du[a])>1e-10 or abs(s[a]-start[a])>coordinate_budget_m:continue
            low=max(min(s[u],e[u]),min(start[u],end[u]))
            high=min(max(s[u],e[u]),max(start[u],end[u]))
            if high-low<1e-8:continue
            plane=int(np.argmin(abs(axes[a]-s[a])))
            # CCW perimeter interior is on its left side.
            index=plane-1 if outward[a]>0 else plane
            arr=owner[index,:,:] if a==0 else owner[:,index,:]
            cuts=np.searchsorted(axes[u],[low,high])
            lo=int(np.argmin(abs(axes[u]-low)));hi=int(np.argmin(abs(axes[u]-high)))
            mask=arr[lo:hi,:]>0
            for i0,i1,z0,z1,_ in rectangles(mask):
                x0,x1=axes[u][lo+i0],axes[u][lo+i1]
                # Limit to the original source segment and map tiny endpoint noise.
                x0=max(low,x0);x1=min(high,x1)
                if x1-x0<=1e-9:continue
                if abs(x0-min(start[u],end[u]))<coordinate_budget_m:x0=min(start[u],end[u])
                if abs(x1-max(start[u],end[u]))<coordinate_budget_m:x1=max(start[u],end[u])
                run['raw_profiles'].append(shapely.box(x0,axes[2][z0],x1,axes[2][z1]))
                run['source_ids'].update(map(int,np.unique(arr[lo+i0:lo+i1,z0:z1])))
        if not run['raw_profiles']:raise ValueError('No measured facade profile for perimeter run')
        raw_profile=shapely.union_all(run.pop('raw_profiles'))
        # Coordinate cleanup is based on profile boundaries, never all source grid coordinates.
        coords=np.concatenate([np.array(r.coords)[:-1] for poly in parts(raw_profile) for r in [poly.exterior,*poly.interiors]])
        umap,zmap=clustered(coords[:,0], coordinate_budget_m),clustered(coords[:,1], coordinate_budget_m)
        def ring(r):return [(umap[x],zmap[z]) for x,z in list(r.coords)[:-1]]
        profile=shapely.union_all([Polygon(ring(poly.exterior),[ring(r) for r in poly.interiors]) for poly in parts(raw_profile)])
        if not profile.is_valid:raise ValueError('Invalid facade profile after precision consolidation')
        # Remove collinear source-grid vertices. Only actual silhouette/opening corners remain.
        profile=profile.simplify(1e-10,preserve_topology=True)
        run['profile']=profile
        run['profile_error_m']=float(shapely.hausdorff_distance(raw_profile,profile))
        if run['profile_error_m']>coordinate_budget_m:raise ValueError('Profile normalization exceeds configured budget')
        run['source_ids']=sorted(run['source_ids']-{0})
        runs.append(run)
    # The façade spans the measured level-to-level height, not individual wall
    # tops hidden by slabs. Preserve wall openings, including clipped stair
    # windows at the floor boundaries. An unmatched wall-top gap is recorded,
    # not promoted to a new window/opening by the mesher.
    excluded_gaps=[]
    for ri,run in enumerate(runs,1):
        profile=run['profile'];low,zlow,high,ztop=profile.bounds
        voids=shapely.box(low,0,high,ztop).difference(profile)
        openings=[]
        for gap in parts(voids):
            if gap.is_empty:continue
            x0,z0,x1,z1=gap.bounds
            at_top=abs(z1-ztop)<1e-6
            at_bottom=z0<1e-6
            a,u=run['axis'],run['along_axis']
            matching=[w['id'] for w in windows if abs(w['min'][u]-x0)<opening_match_m and abs(w['max'][u]-x1)<opening_match_m
                      and min(abs(w['min'][a]-run['start'][a]),abs(w['max'][a]-run['start'][a]))<window_plane_distance_m]
            if at_top and not matching:
                excluded_gaps.append({'facade_run':ri,'source_bounds_m':[x0,z0,x1,z1],
                                      'reason':'unmatched wall-top termination; façade uses full level height'})
                continue
            if at_top:
                gap=shapely.box(x0,z0,x1,height)
            openings.append({'geometry':gap,'source_window_ids':matching,'kind':'clipped_at_top' if at_top else 'clipped_at_bottom' if at_bottom else 'closed'})
        run['profile']=shapely.box(low,0,high,height).difference(shapely.union_all([o['geometry'] for o in openings]))
        run['openings']=[{'geometry_geojson':shapely.to_geojson(o['geometry']),'source_window_ids':o['source_window_ids'],'kind':o['kind']} for o in openings]
    # Height cuts originate only in measured opening/silhouette corners. Shared
    # corner cuts are recorded explicitly, not inherited from the interior grid.
    zvalues=set()
    for run in runs:
        for poly in parts(run['profile']):
            for ring in [poly.exterior,*poly.interiors]:
                zvalues.update(z for x,z in ring.coords)
    zmap=clustered(zvalues, coordinate_budget_m)
    zcuts=np.array(sorted(set(zmap.values())))
    vertices,faces,labels,lookup=[],[],[],{}
    profiles=[]
    for ri,run in enumerate(runs,1):
        profile=run['profile']
        uvalues=set()
        for poly in parts(profile):
            for ring in [poly.exterior,*poly.interiors]:
                uvalues.update(x for x,z in ring.coords)
        ucuts=np.array(sorted(uvalues))
        for i in range(len(ucuts)-1):
            for j in range(len(zcuts)-1):
                if not profile.covers(Point((ucuts[i]+ucuts[i+1])/2,(zcuts[j]+zcuts[j+1])/2)):continue
                q=[]
                for x,z in [(ucuts[i],zcuts[j]),(ucuts[i+1],zcuts[j]),(ucuts[i+1],zcuts[j+1]),(ucuts[i],zcuts[j+1])]:
                    xyz=[0.,0.,z];xyz[run['axis']]=run['start'][run['axis']];xyz[run['along_axis']]=x
                    q.append(xyz)
                q=np.array(q)
                normal=np.cross(q[1]-q[0],q[2]-q[0])
                if np.dot(normal[:2],run['outward'])<0:q=q[::-1]
                f=[]
                for xyz in q:
                    key=tuple(np.round(xyz,10))
                    if key not in lookup:lookup[key]=len(vertices);vertices.append(xyz)
                    f.append(lookup[key])
                faces.append(f);labels.append(ri)
        profiles.append({**{k:v for k,v in run.items() if k!='profile'},'profile_geojson':shapely.to_geojson(profile),
                         'u_cuts_m':ucuts.tolist(),'closed_openings':sum(len(poly.interiors) for poly in parts(profile))})
    vertices=np.array(vertices)
    angle=float(data['angle']);rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    vertices[:,:2]=vertices[:,:2]@rotation.T
    report={'method':'Outermost measured footprint boundary; exterior vertical profiles only; no interior faces',
            'vertices':len(vertices),'quads':len(faces),'facade_runs':len(runs),
            'perimeter_hausdorff_m':distance,'coordinate_precision_budget_m':coordinate_budget_m,
            'profile_hausdorff_max_m':max(r['profile_error_m'] for r in runs),
            'classification_footprint_repair_area_m2':repair_area,
            'classification_microgap_closure_m':microgap_closure_m,
            'z_cuts_m':zcuts.tolist(),'normalization_not_a_customer_dimension_tolerance':True,
            'contour_geojson':shapely.to_geojson(contour),'profiles':profiles,
            'shell_applied':False,
            'surface_height_m':height,'height_basis':height_basis,'wall_top_policy':wall_top_policy,
            'excluded_wall_top_gaps':excluded_gaps,
            'scope':'Exterior perimeter surface only. No interior, rear balcony infill, slab caps, windows or thickness.',
            'status':'Exterior surface prototype; readback and local cut audit pending'}
    if not len(faces):raise ValueError('No exterior faces produced')
    return {'vertices':vertices,'faces':np.array(faces,dtype=np.int32),
            'facade_indices':np.array(labels,dtype=np.int32)}, report

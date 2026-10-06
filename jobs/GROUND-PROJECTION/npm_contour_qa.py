import numpy as np,json
from pathlib import Path
import shapely as sh
from shapely import Polygon
R=Path(__file__).parent/'outputs/v008';S=R.parent/'v001';D=np.load(R/'readback_QUADS.npz');G=np.load(S/'Ground_arrays.npz')
v=D['vertices'];f=D['faces'];m=D['materials'];pts=v[f];sp=np.array([Polygon(p[:,:2]/100) for p in G['v'][G['f']]])
op=np.array([Polygon(p[:,:2]) for p in pts]);rows=[]
edges=np.sort(np.concatenate([f[:,[i,(i+1)%4]] for i in range(4)]),axis=1);labels=np.column_stack((np.tile(m,4),edges));le,lc=np.unique(labels,axis=0,return_counts=True)
for mat in range(18):
 old=sh.union_all(sp[G['mat']==mat],grid_size=.001);new=sh.union_all(sh.make_valid(op[m==mat]),grid_size=.001)
 boundary=le[(le[:,0]==mat)&(lc==1),1:];p=v[boundary,:2];sample=np.concatenate((p.reshape(-1,2),p.mean(axis=1)))
 dist=sh.distance(sh.points(sample),old.boundary)
 # Raw Hausdorff can amplify near-zero source sliver holes, so preserve both measures.
 rows.append({'id':mat+1,'source_area_m2':old.area,'result_area_m2':new.area,'symmetric_difference_m2':old.symmetric_difference(new).area,'boundary_samples_max_m':float(dist.max()),'samples_beyond_2mm':int((dist>.002).sum()),'source_to_result_boundary_m':float(old.boundary.hausdorff_distance(new.boundary))})
normal=np.cross(pts[:,1]-pts[:,0],pts[:,2]-pts[:,0])+np.cross(pts[:,2]-pts[:,0],pts[:,3]-pts[:,0]);slope=np.degrees(np.arccos(np.clip(normal[:,2]/np.linalg.norm(normal,axis=1),-1,1)))
areas=sh.area(op);edge_lengths=np.linalg.norm(pts-np.roll(pts,-1,axis=1),axis=2)
result={'materials':rows,'max_slope_degrees':float(slope.max()),'slope_quantiles':np.quantile(slope,[.5,.9,.99,1]).tolist(),'edge_length_m_quantiles':np.quantile(edge_lengths,[.25,.5,.75,.9,.95,1]).tolist(),'area_with_longest_edge_2_to_4m_fraction':float(areas[(edge_lengths.max(axis=1)>=2)&(edge_lengths.max(axis=1)<=4)].sum()/areas.sum()),'area_weighted_average_edge_m':float(np.sum(areas*edge_lengths.mean(axis=1))/areas.sum()),'total_surface_plan_area_with_overlaps_m2':float(areas.sum())}
(R/'contour_qa.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))



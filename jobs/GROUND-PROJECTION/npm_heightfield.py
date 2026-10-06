import bpy,numpy as np,json,time
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION/outputs/v004');R.mkdir(parents=True,exist_ok=True)
S=R.parent/'v001';d=np.load(S/'Relef_arrays.npz');v=d['v']/100;f=d['f'];t=v[f]
n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);nz=np.abs(n[:,2])/np.maximum(np.linalg.norm(n,axis=1),1e-30)
valid=nz>.2;f=f[valid];n=n[valid];t=t[valid]
planes=np.column_stack((-n[:,0]/n[:,2],-n[:,1]/n[:,2],np.einsum('ij,ij->i',n,t[:,0])/n[:,2]))
bvh=BVHTree.FromPolygons(v.tolist(),f.tolist(),all_triangles=True)
flat=v.copy();flat[:,2]=0;near=BVHTree.FromPolygons(flat.tolist(),f.tolist(),all_triangles=True)
g=np.load(S/'Ground_arrays.npz')['v']/100
step=.5;low=np.floor(g[:,:2].min(axis=0)/step)*step-12;high=np.ceil(g[:,:2].max(axis=0)/step)*step+12
xs=np.arange(low[0],high[0]+step/2,step);ys=np.arange(low[1],high[1]+step/2,step);raw=np.empty((len(ys),len(xs)))
missing=0
for j,y in enumerate(ys):
 for i,x in enumerate(xs):
  idx=bvh.ray_cast(Vector((x,y,20)),Vector((0,0,-1)))[2]
  if idx is None:idx=near.find_nearest(Vector((x,y,0)))[2];missing+=1
  p=planes[idx];raw[j,i]=p[0]*x+p[1]*y+p[2]
# Suppress isolated curbs/slivers, quantize insignificant elevations, then build C1 terrain.
pad=np.pad(raw,2,mode='edge');neighbours=np.stack([pad[j:j+len(ys),i:i+len(xs)] for j in range(5) for i in range(5)])
height=np.round(np.median(neighbours,axis=0)/.25)*.25
sigma=1.6/step;radius=int(np.ceil(3*sigma));x=np.arange(-radius,radius+1);kernel=np.exp(-.5*(x/sigma)**2);kernel/=kernel.sum()
for axis in [0,1]:
 shape=[(0,0),(0,0)];shape[axis]=(radius,radius);p=np.pad(height,shape,mode='edge')
 height=np.apply_along_axis(lambda row:np.convolve(row,kernel,mode='valid'),axis,p)
np.savez_compressed(R/'heightfield.npz',xs=xs,ys=ys,raw=raw,height=height)
(R/'heightfield.json').write_text(json.dumps({'source_world_to_m':.01,'step_m':step,'median_window_m':2.5,'height_quantization_m':.25,'gaussian_sigma_m':1.6,'range_m':[float(height.min()),float(height.max())],'samples':int(raw.size),'outside_samples_including_margin':missing},indent=2))
print('HEIGHTFIELD',raw.shape, height.min(),height.max())

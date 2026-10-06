import json,time,collections
from pathlib import Path
import numpy as np
import shapely as sh
from shapely import Polygon,LineString,STRtree,box
from npm_surface import Field
R=Path(__file__).parent/'outputs/v008';S=R.parent/'v001';t0=time.time()
def log(s):print(f'{time.time()-t0:.1f}s {s}',flush=True)
field=Field(R/'heightfield.npz');gd=np.load(S/'Ground_arrays.npz');gv=gd['v'][:,:2]/100;gf=gd['f'];gm=gd['mat']
GRID=.001
src=np.array([Polygon(v) for v in gv[gf]])
regions=[sh.union_all(src[gm==m],grid_size=GRID) for m in range(18)]
domain=sh.union_all(regions);bounds=domain.bounds
cells=[]
def subdiv(x,y,size,depth=0):
 b=box(x,y,x+size,y+size)
 if not b.intersects(domain):return
 points=np.array([[x,y],[x+size,y],[x+size,y+size],[x,y+size],[x+size/2,y+size/2],[x+size/2,y],[x+size,y+size/2],[x+size/2,y+size],[x,y+size/2]])
 z=field.sample(points);estimate=np.array([z[:4].mean(),(z[0]+z[1])/2,(z[1]+z[2])/2,(z[2]+z[3])/2,(z[3]+z[0])/2]);err=np.abs(z[4:]-estimate).max()
 if size>3 and z.max()-z.min()>.3 and err>.15:
  for dx,dy in [(0,0),(.5,0),(0,.5),(.5,.5)]:subdiv(x+size*dx,y+size*dy,size/2,depth+1)
 else:cells.append((b,size,depth))
for x in np.arange(np.floor(bounds[0]/6)*6,bounds[2],6):
 for y in np.arange(np.floor(bounds[1]/6)*6,bounds[3],6):subdiv(x,y,6)
log(f'grid cells {len(cells)}')
# Shared coarse control surface. Flat triangles support narrow finish patches;
# uncut cells still become4 editable quads with the same support diagonals.
support_xy=[];support_z=[];support_planes=[];supports_by_cell=[]
coarse_edges=[]
for b,size,depth in cells:
 if size==6:
  x,y,x1,y1=b.bounds
  for a,c in [(np.array([x,y]),np.array([x1,y])),(np.array([x1,y]),np.array([x1,y1])),(np.array([x1,y1]),np.array([x,y1])),(np.array([x,y1]),np.array([x,y]))]:coarse_edges.append((a,c))
ca=np.array([e[0] for e in coarse_edges]);cb=np.array([e[1] for e in coarse_edges]);cd=cb-ca;cl=np.sum(cd*cd,axis=1);cz0=field.sample(ca);cz1=field.sample(cb);control_cache={}
def control_z(p):
 key=tuple(p)
 if key in control_cache:return control_cache[key]
 delta=p-ca;tt=np.sum(delta*cd,axis=1)/cl;cross=np.abs(cd[:,0]*delta[:,1]-cd[:,1]*delta[:,0]);ids=np.flatnonzero((tt>1e-9)&(tt<1-1e-9)&(cross<1e-8))
 value=float(cz0[ids[0]]*(1-tt[ids[0]])+cz1[ids[0]]*tt[ids[0]]) if len(ids) else float(field.sample(p))
 control_cache[key]=value;return value
for b,size,depth in cells:
 x,y,x1,y1=b.bounds;c=np.array([(x+x1)/2,(y+y1)/2]);ring=np.array([[x,y],[x1,y],[x1,y1],[x,y1]])
 z=np.array([control_z(p) for p in ring]);zc=float(field.sample(c));indices=[]
 for j in range(4):
  p=np.array([ring[j],ring[(j+1)%4],c]);zz=np.array([z[j],z[(j+1)%4],zc]);plane=np.linalg.solve(np.column_stack((p,np.ones(3))),zz)
  indices.append(len(support_xy));support_xy.append(p);support_z.append(zz);support_planes.append(plane)
 supports_by_cell.append(indices)
support_polys=np.array([Polygon(p) for p in support_xy]);support_tree=STRtree(support_polys);support_planes=np.array(support_planes)
patches=[]
for cell_index,(b,size,depth) in enumerate(cells):
 for mat,reg in enumerate(regions):
  if not b.intersects(reg):continue
  inter=sh.intersection(b,reg)
  if inter.equals(b):patches.append((b,mat,size));continue
  for si in supports_by_cell[cell_index]:
   for p in sh.get_parts(sh.intersection(inter,support_polys[si])):
    if p.geom_type=='Polygon' and p.area>1e-12:patches.append((p,mat,size))
log(f'clipped patches {len(patches)}')
# Re-node the entire planar arrangement on a1mm lattice. This prevents subpixel
# intersections of near-coincident source/support edges from returning later.
patch_polys=np.array([p for p,_,_ in patches]);patch_mats=np.array([m for _,m,_ in patches]);patch_sizes=np.array([s for _,_,s in patches]);patch_tree=STRtree(patch_polys)
network=sh.union_all(sh.boundary(patch_polys),grid_size=GRID);arrangement=sh.get_parts(sh.polygonize(sh.get_parts(network)))
rp=sh.point_on_surface(arrangement);pairs=patch_tree.query(rp,predicate='intersects');labels=[set() for _ in arrangement];cell_sizes=np.full(len(arrangement),6.)
for a,b in pairs.T:labels[a].add(int(patch_mats[b]));cell_sizes[a]=min(cell_sizes[a],patch_sizes[b])
assigned=[(p,frozenset(ids),size) for p,ids,size in zip(arrangement,labels,cell_sizes) if ids]
arr_polys=np.array([p for p,_,_ in assigned]);arr_tree=STRtree(arr_polys);gone=set();merge_count=0
for i,(p,ids,size) in enumerate(assigned):
 if i in gone:continue
 w=max(p.bounds[2]-p.bounds[0],p.bounds[3]-p.bounds[1])
 if p.area/max(w,1e-30)>=.00015:continue
 candidates=[int(j) for j in arr_tree.query(p,predicate='intersects') if j!=i and j not in gone and assigned[j][1]==ids]
 if candidates:
  j=max(candidates,key=lambda j:p.boundary.intersection(assigned[j][0].boundary).length)
  if p.boundary.intersection(assigned[j][0].boundary).length>1e-8:
   assigned[j]=(sh.union_all([p,assigned[j][0]],grid_size=GRID),ids,min(size,assigned[j][2]));gone.add(i);merge_count+=1
patches=[]
for i,(p,ids,size) in enumerate(assigned):
 if i in gone:continue
 for q in sh.get_parts(p):
  for mat in ids:patches.append((q,mat,size))
log(f'arrangement {len(assigned)}, merged slivers {merge_count}')
# Collapse sub0.1mm slivers in the planar network BEFORE making quad midpoints.
# Shared vertices move together; neighbours close the collapsed strip.
base=[]
for p,mat,size in patches:
 parts=sh.get_parts(sh.constrained_delaunay_triangles(p)) if p.interiors or p.convex_hull.area-p.area>1e-9 else [p]
 for q in parts:base.append((q,mat,size))
coords=[];index={};bf=[]
for p,mat,size in base:
 ids=[]
 for xy in np.array(p.exterior.coords)[:-1]:
  key=tuple(np.round(xy,8))
  if key not in index:index[key]=len(coords);coords.append(key)
  ids.append(index[key])
 bf.append((ids,mat,size))
coords=np.array(coords);original_coords=coords.copy();drop=set();proposals=collections.defaultdict(list)
for k,(ids,mat,size) in enumerate(bf):
 p=coords[ids];center=p.mean(axis=0);_,_,vt=np.linalg.svd(p-center,full_matrices=False);axis=vt[0];perp=np.array([-axis[1],axis[0]]);offset=(p-center)@perp
 if np.ptp(offset)<.0001:
  drop.add(k)
  for idx,xy,t in zip(ids,p,offset):proposals[idx].append(xy-t*perp)
for idx,values in proposals.items():coords[idx]=np.mean(values,axis=0)
pt=sh.points(coords);ptree=STRtree(pt);pairs=ptree.query(pt,predicate='dwithin',distance=.0001);parent=np.arange(len(coords))
def root(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
for a,b in pairs.T:
 ra,rb=root(a),root(b)
 if ra!=rb:parent[max(ra,rb)]=min(ra,rb)
clusters=collections.defaultdict(list)
for i in range(len(coords)):clusters[root(i)].append(i)
for ids in clusters.values():coords[ids]=coords[ids].mean(axis=0)
patches=[]
for k,(ids,mat,size) in enumerate(bf):
 if k in drop:continue
 ring=[]
 for xy in coords[ids]:
  if not ring or np.linalg.norm(xy-ring[-1])>1e-8:ring.append(xy)
 if len(ring)>2:
  p=Polygon(ring)
  for q in sh.get_parts(sh.make_valid(p)):
   if q.geom_type=='Polygon' and q.area>1e-12:patches.append((q,mat,size))
conditioning_max=float(np.linalg.norm(coords-original_coords,axis=1).max());log(f'conditioned {len(drop)} sub0.1mm patches; max shift {conditioning_max:.8f}m')
linework=sh.union_all([p.boundary for p,_,_ in patches])
nodes=np.unique(sh.get_coordinates(linework),axis=0);tree=STRtree(sh.points(nodes))
def ring_node(ring):
 raw=np.array(ring.coords)[:-1];out=[]
 for a,b in zip(raw,np.roll(raw,-1,axis=0)):
  delta=b-a;ll=delta@delta
  if ll<1e-18:continue
  ids=tree.query(LineString([a,b]).buffer(1e-7));q=nodes[ids]-a
  ts=q@delta/ll;dist=np.abs(delta[0]*q[:,1]-delta[1]*q[:,0])/np.sqrt(ll)
  good=(ts>1e-8)&(ts<1-1e-8)&(dist<1e-8)
  out.append(a)
  out.extend(nodes[ids[good][np.argsort(ts[good])]])
 # Remove repeated nodes only; do not simplify curved finish contours.
 keep=[]
 for p in out:
  if not keep or np.linalg.norm(p-keep[-1])>1e-8:keep.append(p)
 return keep
verts=[];faces=[];mats=[];sizes=[];lookup={};tiny=[]
def vertex(p):
 key=tuple(round(float(x),7) for x in p)
 if key not in lookup:lookup[key]=len(verts);verts.append(key)
 return lookup[key]
for k,(p,mat,size) in enumerate(patches):
 p=Polygon(ring_node(p.exterior),[ring_node(r) for r in p.interiors]);p=sh.orient_polygons(p)
 if p.interiors or p.convex_hull.area-p.area>1e-9:
  parts=sh.get_parts(sh.constrained_delaunay_triangles(p))
 else:parts=[p]
 for poly in parts:
  poly=sh.orient_polygons(poly);xy=np.array(poly.exterior.coords)[:-1]
  # A different interior centre avoids exact duplicate quads in retained material overlaps.
  center=np.array(poly.centroid.coords[0]);blend=.0001*(mat+1);center=center*(1-blend)+xy[mat%len(xy)]*blend
  ci=vertex(center);vi=[vertex(v) for v in xy];mi=[vertex(q) for q in (xy+np.roll(xy,-1,axis=0))*.5]
  for j in range(len(xy)):
   f=[vi[j],mi[j],ci,mi[j-1]]
   if len(set(f))<4:tiny.append(k);continue
   faces.append(f);mats.append(mat);sizes.append(size)
xy=np.array(verts);z=np.zeros(len(xy));pairs=support_tree.query(sh.points(xy),predicate='intersects');chosen=np.full(len(xy),-1,dtype=int);chosen[pairs[0]]=pairs[1]
missing=chosen<0
if missing.any():chosen[missing]=support_tree.nearest(sh.points(xy[missing]))
planes=support_planes[chosen];z=np.sum(xy*planes[:,:2],axis=1)+planes[:,2]
z=field.sample(xy)
world=np.column_stack((xy,z));faces=np.array(faces,dtype=np.int32)
used=np.unique(faces);remap=np.full(len(world),-1);remap[used]=np.arange(len(used));world=world[used];faces=remap[faces]
# Limit artificial cross-slope of extremely narrow finish fragments by the
# minimum height correction; XY, material boundaries and connectivity stay fixed.
tri=np.concatenate((faces[:,[0,1,2]],faces[:,[0,2,3]]));p=world[tri,:2]
u=p[:,1]-p[:,0];w=p[:,2]-p[:,0];det=u[:,0]*w[:,1]-u[:,1]*w[:,0]
B=np.zeros((len(tri),2,3));B[:,0,1]=w[:,1]/det;B[:,0,2]=-u[:,1]/det;B[:,1,1]=-w[:,0]/det;B[:,1,2]=u[:,0]/det;B[:,:,0]=-B[:,:,1]-B[:,:,2]
z0=world[:,2].copy()
for iteration in range(1000):
 grad=np.einsum('nij,nj->ni',B,world[tri,2]);mag=np.linalg.norm(grad,axis=1);bad=mag>1.5
 if not bad.any():break
 ids=tri[bad];a=np.einsum('nij,ni->nj',B[bad],grad[bad]/mag[bad,None]);delta=-a*((mag[bad]-1.49)/np.sum(a*a,axis=1))[:,None]
 sums=np.bincount(ids.ravel(),weights=delta.ravel(),minlength=len(world));counts=np.bincount(ids.ravel(),minlength=len(world));world[:,2]+=sums/np.maximum(counts,1)
log(f'sliver slope conditioning: {iteration} iterations, maximum height correction {np.max(np.abs(world[:,2]-z0)):.6f}m, max tangent {mag.max():.4f}')

assert len(faces)<50000,len(faces)
np.savez_compressed(R/'quad_mesh.npz',vertices=world,faces=faces,materials=np.array(mats),cell_size=np.array(sizes))
np.savez_compressed(R/'material_regions.npz',wkb=sh.to_wkb(np.array(regions)))
report={'vertices':len(world),'quads':len(faces),'triangles_after_export':2*len(faces),'grid_cells':len(cells),'patches':len(patches),'parent_cell_sizes':dict(collections.Counter(sizes)),'base_quad_side_m':3,'refinement_criteria':'height range >0.3m AND midpoint interpolation error >0.15m; minimum parent cell3m','same_id_union':True,'different_id_overlaps':'preserved','precision_grid_m':GRID,'collapsed_patches':len(tiny),'seconds':time.time()-t0}
(R/'construction.json').write_text(json.dumps(report,indent=2));log(str(report))






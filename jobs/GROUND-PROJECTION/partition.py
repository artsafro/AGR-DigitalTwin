"""Planar overlay only; Blender performs mesh assembly, export and readback.

All coordinates retain source FBX world units. No source files are modified.
"""
import json, time
from pathlib import Path
import numpy as np
import shapely as sh
from shapely import Polygon, STRtree

ROOT=Path(__file__).parent/'outputs/v001'
GRID=0.001  # source-world units; below the source's large-coordinate float resolution
t0=time.time()
def log(s): print(f'{time.time()-t0:.1f}s {s}',flush=True)
gd=np.load(ROOT/'Ground_arrays.npz');rd=np.load(ROOT/'Relef_arrays.npz')
gv,gf,gm=gd['v'],gd['f'],gd['mat'];rv,rf=rd['v'],rd['f']
gp=sh.set_precision(np.array([Polygon(t[:,:2]) for t in gv[gf]]),GRID)
rt=rv[rf];n=np.cross(rt[:,1]-rt[:,0],rt[:,2]-rt[:,0])
keep=(np.abs(n[:,2])>1e-7)&(np.abs(n[:,2])/np.maximum(np.linalg.norm(n,axis=1),1e-30)>0.001)
ri=np.flatnonzero(keep);rt=rt[keep];n=n[keep]
planes=np.column_stack((-n[:,0]/n[:,2],-n[:,1]/n[:,2], np.einsum('ij,ij->i',n,rt[:,0])/n[:,2]))
rp=sh.set_precision(np.array([Polygon(t[:,:2]) for t in rt]),GRID)
ok=~sh.is_empty(rp);rp=rp[ok];planes=planes[ok];ri=ri[ok]
gdomain=sh.union_all(gp)
use=sh.intersects(rp,gdomain);rp=rp[use];planes=planes[use];ri=ri[use]
log(f'ground {len(gp)} relief nonvertical {len(rp)}')
lines=sh.union_all(np.concatenate((sh.boundary(gp),sh.boundary(rp))),grid_size=GRID)
log('linework noded')
cells=sh.get_parts(sh.polygonize(sh.get_parts(lines)))
pts=sh.point_on_surface(cells)
inside=sh.covers(gdomain,pts);cells=cells[inside];pts=pts[inside]
log(f'cells {len(cells)}')
gtree=STRtree(gp);rtree=STRtree(rp)
gpair=gtree.query(pts,predicate='intersects');rpair=rtree.query(pts,predicate='intersects')
owners=[[] for _ in cells];targets=[[] for _ in cells]
for c,g in gpair.T:owners[c].append(int(g))
for c,r in rpair.T:targets[c].append(int(r))
xy=sh.get_coordinates(pts);chosen=np.full(len(cells),-1,dtype=np.int32)
extra=[];cross=[]
for i,rs in enumerate(targets):
    if rs:
        z=planes[rs,:2]@xy[i]+planes[rs,2];chosen[i]=rs[int(np.argmax(z))]
        if len(rs)>1:
            coords=np.array(cells[i].exterior.coords)
            diff=(planes[rs]-planes[chosen[i]])
            zz=coords@diff[:,:2].T+diff[:,2]
            if np.max(zz)>0.01:cross.append(i)
    else:
        chosen[i]=int(rtree.nearest(pts[i]));extra.append(i)
log(f'extrapolated cells {len(extra)} crossing plane cells {len(cross)}')
# Save cells as WKB, ownership and analytic height plane for deterministic mesh assembly.
np.savez_compressed(ROOT/'partition.npz',wkb=sh.to_wkb(cells),owners=np.array(owners,dtype=object),chosen=chosen,planes=planes,relief_ids=ri,extrapolated=np.array(extra),crossing=np.array(cross),grid=GRID)
report={'cells':len(cells),'extrapolated_cells':len(extra),'extrapolated_area':float(sh.area(cells[extra]).sum()),'crossing_plane_cells':cross,'grid_source_world_units':GRID,'source_overlap_policy':'preserve each original ground face and material owner','seconds':time.time()-t0}
(ROOT/'partition_report.json').write_text(json.dumps(report,indent=2))
log('partition saved')

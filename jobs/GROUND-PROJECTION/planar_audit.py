import json, numpy as np, shapely
from pathlib import Path
from shapely import Polygon, union_all
root=Path(__file__).parent/'outputs/v001'
report={}
unions={}
for name in ['Ground','Relef']:
    d=json.loads((root/f'source_{name}.json').read_text())
    v=np.array(d['vertices']); f=np.array(d['faces']); t=v[f]
    polys=np.array([Polygon(p[:,:2]) for p in t])
    a=shapely.area(polys)
    keep=a>1e-5
    u=union_all(polys[keep]); unions[name]=u
    norms=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]); nz=np.abs(norms[:,2])/np.maximum(np.linalg.norm(norms,axis=1),1e-30)
    report[name]={'area_xy':float(a.sum()),'union_area':u.area,'overlap_area':float(a.sum()-u.area),'degenerate_xy':int((~keep).sum()),'slope_normal_z_quantiles':np.quantile(nz,[0,.1,.5,.9,1]).tolist(),'bounds':u.bounds,'geometry_type':u.geom_type}
    np.savez(root/f'{name}_arrays.npz',v=v,f=f,mat=np.array(d['materials']))
missing=unions['Ground'].difference(unions['Relef'])
report['missing']={'area':missing.area,'percent':100*missing.area/unions['Ground'].area,'pieces':len(list(shapely.get_parts(missing))),'bounds':missing.bounds}
(root/'missing.wkt').write_text(missing.wkt)
(root/'planar_audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))

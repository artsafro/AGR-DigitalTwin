import numpy as np,json
from pathlib import Path
r=Path(__file__).parent/'outputs/v002';d=np.load(r/'quad_mesh.npz');v=d['vertices'];f=d['faces']
rows=[]
for origin in [[2300,3800,0],[7944,4800,0],[7944,6000,0],[7944,4000,0],[7944,0,0],[0,0,0]]:
    vv=(v-origin).astype(np.float32).astype(np.float64)+origin;p=vv[f]
    a=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);b=np.cross(p[:,2]-p[:,0],p[:,3]-p[:,0]);fold=np.flatnonzero(a[:,2]*b[:,2]<-1e-8)
    rows.append({'origin':origin,'folds':len(fold),'examples':fold[:10].tolist(),'max_xyz_delta':float(np.linalg.norm(vv-v,axis=1).max())})
print(json.dumps(rows,indent=2))
(r/'precision.json').write_text(json.dumps(rows,indent=2))

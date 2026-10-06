import numpy as np,json,collections,hashlib
from pathlib import Path
R=Path(__file__).parent/'outputs/v008';d=np.load(R/'readback_QUADS.npz');v=d['vertices'];f=d['faces'];m=d['materials'];edges=collections.defaultdict(list)
for i,face in enumerate(f):
 for a,b in zip(face,np.roll(face,-1)):edges[tuple(sorted((a,b)))].append(i)
non=[ids for ids in edges.values() if len(ids)>2]
same=[ids for ids in non if len(set(m[ids]))==1]
source=Path('C:/Users/artsafro/Downloads/Telegram Desktop/GROUND.fbx')
r={'nonmanifold_edges':len(non),'nonmanifold_single_material_edges':len(same),'nonmanifold_multiple_material_edges':len(non)-len(same),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
(R/'additional_qa.json').write_text(json.dumps(r,indent=2));print(r)

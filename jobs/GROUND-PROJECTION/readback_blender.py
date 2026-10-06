import bpy,json,hashlib,collections,sys
from pathlib import Path
import numpy as np
from io_scene_fbx import parse_fbx
VERSION=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'v001'
ROOT=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION/outputs')/VERSION
expected=np.load(ROOT/'blend_geometry.npz');mapping=json.loads((ROOT/'material_ids.json').read_text(encoding='utf-8'))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(ROOT/f'GROUND_projected_{VERSION}.fbx'),use_image_search=False)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(objs)==1
obj=objs[0];mesh=obj.data
local=np.empty(len(mesh.vertices)*3,dtype=np.float64);mesh.vertices.foreach_get('co',local)
matrix=np.array(obj.matrix_world,dtype=np.float64)
v=local.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3];f=np.array([list(p.vertices) for p in mesh.polygons]);m=np.array([p.material_index for p in mesh.polygons])
names=[s.name for s in mesh.materials]
np.savez_compressed(ROOT/'fbx_geometry.npz',vertices=v,faces=f,materials=m)
raw,version=parse_fbx.parse(str(ROOT/f'GROUND_projected_{VERSION}.fbx'))
geom=next(e for e in next(e for e in raw.elems if e.id==b'Objects').elems if e.id==b'Geometry')
layer=next(e for e in geom.elems if e.id==b'LayerElementMaterial')
raw_ids=next(e.props[0] for e in layer.elems if e.id==b'Materials')
vdelta=float(np.max(np.linalg.norm(v-expected['vertices'],axis=1))) if v.shape==expected['vertices'].shape else None
out={'mesh_objects':len(objs),'vertices':len(v),'faces':len(f),'polygon_sizes':dict(collections.Counter(len(p.vertices) for p in mesh.polygons)),'fbx_version':version,'material_slots':len(names),'material_names_equal':names==[x['name'] for x in mapping],'face_material_ids_equal':bool(np.array_equal(m,expected['materials'])),'raw_fbx_material_ids_equal':bool(np.array_equal(raw_ids,m)),'face_indices_equal':bool(np.array_equal(f,expected['faces'])),'vertex_world_max_delta':vdelta,'fbx_sha256':hashlib.sha256((ROOT/f'GROUND_projected_{VERSION}.fbx').read_bytes()).hexdigest(),'max_application_readback':'not_run','visual_acceptance':'pending'}
(ROOT/'readback.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2),flush=True)

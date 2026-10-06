import bpy,json,hashlib
from pathlib import Path
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'GLB_K1_assembled_v021.blend'))
ob=bpy.data.objects['K1_TYPICAL_NPM']
def signature():return hashlib.sha256(json.dumps(([list(v.co) for v in ob.data.vertices],[list(p.vertices) for p in ob.data.polygons])).encode()).hexdigest()
before=signature()
with bpy.data.libraries.load(str(out.parent/'clearance-ab-v007/GLB_AB_clearance_v007.blend'),link=False) as (available,dest):dest.objects=['A_<auto>26','B_<auto>26']
templates={o.name[0]:o for o in dest.objects};trees={k:BVHTree.FromPolygons([v.co for v in o.data.vertices],[list(p.vertices) for p in o.data.polygons]) for k,o in templates.items()}
floors=[]
for row in json.loads((out/'floor-instances.json').read_text()):
 label='A' if row['definition_id']==170455 else 'B';offset=0 if label=='A' else 3.3
 m=Matrix(row['matrix_inches']);m.translation*=.0254;m=m@Matrix.Translation((0,0,.02-offset))
 floors.append((row['z_translation_m']+.02,label,m.inverted(),offset))
layer=ob.data.uv_layers['Atlas_UV'];attr=ob.data.attributes['npm_part_id'];count=0
for p in ob.data.polygons:
 if attr.data[p.index].value!=3:continue
 z=sum(ob.data.vertices[i].co.z for i in p.vertices)/len(p.vertices)
 level,label,inv,offset=min(floors,key=lambda row:min(abs(z-row[0]),abs(z-row[0]-1)))
 source=templates[label];me=source.data;tree=trees[label]
 for vid,li in zip(p.vertices,p.loop_indices):
  point=inv@ob.data.vertices[vid].co;point.z=offset
  loc,n,idx,dist=tree.find_nearest(point);tri=me.polygons[idx];v=[me.vertices[i].co for i in tri.vertices]
  uv=[Vector((*me.uv_layers.active.data[i].uv,0)) for i in tri.loop_indices]
  co=barycentric_transform(point,*v,*uv);layer.data[li].uv=(co.x,co.y)
 count+=1
for o in templates.values():bpy.data.objects.remove(o,do_unlink=True)
assert signature()==before
target=out/'GLB_K1_assembled_v022.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target));ob=bpy.data.objects['K1_TYPICAL_NPM'];assert signature()==before
(out/'v022-uv-readback.json').write_text(json.dumps({'exterior_ledge_faces_source_uv_restored':count,'geometry_hash_unchanged_from_v021':before,'clearance_and_interior_reports':'v021 geometry unchanged'},indent=2),encoding='utf-8')
scene=bpy.context.scene;scene.render.filepath=str(out/'GLB_K1_assembled_v022.png');bpy.ops.render.render(write_still=True)
print('Restored source UV to',count,'ledge faces')

import bpy,bmesh,json
from pathlib import Path
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'K1_exterior_top_draft_v013.blend'))
rows=json.loads((out/'sills-exterior-polygons.json').read_text());ob=bpy.data.objects['K1_SIMPLE_SILLS'];old=ob.data
vs=[];fs=[]
for row in rows:
 start=len(vs);vs.extend(row['points']);fs.append(list(range(start,len(vs))))
me=bpy.data.meshes.new('K1_ExteriorSills');me.from_pydata(vs,[],fs);me.update();me.materials.append(old.materials[0]);uv=me.uv_layers.new(name='Source_UV')
for p,row in zip(me.polygons,rows):
 for i,co in zip(p.loop_indices,row['uv']):uv.data[i].uv=co
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000005)
bmesh.ops.join_triangles(bm,faces=[f for f in bm.faces if len(f.verts)==3],angle_face_threshold=.0001,angle_shape_threshold=.8,cmp_uvs=True,cmp_materials=True)
bm.to_mesh(me);bm.free();me.update();ob.data=me
scene=bpy.context.scene;scene['status']='K1_EXTERIOR_ASSEMBLED_TOP_DRAFT_QA_PENDING';scene['delivery']=False
bpy.ops.wm.save_as_mainfile(filepath=str(out/'K1_exterior_top_draft_v014.blend'))
print('EXTERIOR SILLS',len(me.polygons))

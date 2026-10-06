import bpy,bmesh,json
from pathlib import Path
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'K1_exterior_top_draft_v014.blend'))
with bpy.data.libraries.load(str(out.parent/'clearance-ab-v007/GLB_AB_clearance_v007.blend'),link=False) as (available,target):
 target.materials=['<auto>26']
rows=json.loads((out/'exterior-ledge-faces.json').read_text());vs=[];fs=[]
for r in rows:
 start=len(vs);vs.extend(r['points']);fs.append(list(range(start,len(vs))))
me=bpy.data.meshes.new('ExteriorBeltLedges');me.from_pydata(vs,[],fs);me.materials.append(bpy.data.materials['<auto>26']);me.update();uv=me.uv_layers.new(name='Exterior_Ledge_UV')
for p,r in zip(me.polygons,rows):
 for i,co in zip(p.loop_indices,r['uv']):uv.data[i].uv=co
ob=bpy.data.objects.new('K1_EXTERIOR_LEDGES',me);bpy.data.collections['K1_TYPICAL_EXTERIOR'].objects.link(ob)
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000005)
bmesh.ops.join_triangles(bm,faces=list(bm.faces),angle_face_threshold=.0001,angle_shape_threshold=.8,cmp_uvs=True,cmp_materials=True)
bm.to_mesh(me);bm.free();me.update()
# Remove only redundant coplanar cuts from the clipped, single-color sills.
sills=bpy.data.objects['K1_SIMPLE_SILLS'];bm=bmesh.new();bm.from_mesh(sills.data)
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00005)
bmesh.ops.dissolve_degenerate(bm,dist=.00001,edges=list(bm.edges))
bmesh.ops.dissolve_limit(bm,angle_limit=.00005,verts=list(bm.verts),edges=list(bm.edges),delimit={'NORMAL','MATERIAL'})
ngons=[f for f in bm.faces if len(f.verts)>4]
if ngons:bmesh.ops.triangulate(bm,faces=ngons)
bmesh.ops.join_triangles(bm,faces=[f for f in bm.faces if len(f.verts)==3],angle_face_threshold=.0001,angle_shape_threshold=.8,cmp_uvs=False,cmp_materials=True)
bm.to_mesh(sills.data);bm.free();sills.data.update()
bpy.context.scene['status']='K1_EXTERIOR_ASSEMBLY_TOP_DRAFT';bpy.context.scene['delivery']=False
bpy.ops.wm.save_as_mainfile(filepath=str(out/'K1_exterior_top_draft_v015.blend'))
print('LEDGES',len(me.polygons),'SILLS',len(sills.data.polygons))

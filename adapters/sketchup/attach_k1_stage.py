import bpy,bmesh,json
from pathlib import Path
from mathutils.kdtree import KDTree
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'K1_exterior_top_draft_v016.blend'))
group=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('K1_')]
roles={name:i+1 for i,name in enumerate(sorted(o.name for o in group))}
for o in group:
 o.data.uv_layers.active.name='Atlas_UV'
 attr=o.data.attributes.new(name='npm_part_id',type='INT',domain='FACE');attr.data.foreach_set('value',[roles[o.name]]*len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
for o in group:o.select_set(True)
bpy.context.view_layer.objects.active=bpy.data.objects['K1_BODY'];bpy.ops.object.join();ob=bpy.context.object;ob.name='K1_TYPICAL_NPM';ob['role']='typical_assembled'
bm=bmesh.new();bm.from_mesh(ob.data);before=len(bm.verts)
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000005)
splits=0
# Preserve intentional separate shells instead of making multi-face junctions.
uv=bm.loops.layers.uv.active;part=bm.faces.layers.int.get('npm_part_id');detach=set()
for e in bm.edges:
 if len(e.link_faces)>2:
  ff=list(e.link_faces);score,i,j=max((ff[i].normal.dot(ff[j].normal),i,j) for i in range(len(ff)) for j in range(i));detach.update(f for k,f in enumerate(ff) if k not in [i,j])
for f in detach:
 nf=bm.faces.new([bm.verts.new(v.co) for v in f.verts]);nf.material_index=f.material_index
 if part:nf[part]=f[part]
 for a,b in zip(nf.loops,f.loops):a[uv].uv=b[uv].uv
 bmesh.ops.delete(bm,geom=[f],context='FACES_ONLY')
loose=[v for v in bm.verts if not v.link_faces];bmesh.ops.delete(bm,geom=loose,context='VERTS')
report={'part_ids':roles,'vertex_count_before_weld':before,'vertex_count_after':len(bm.verts),'conforming_edge_splits':splits,
 'separate_penetrating_faces':len(detach),'edges_more_than_two_faces':sum(len(e.link_faces)>2 for e in bm.edges),
 'degenerate_faces':sum(f.calc_area()<1e-9 for f in bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),
 'weld_tolerance_m':.000005,'top_draft_excluded':True}
bm.to_mesh(ob.data);bm.free();ob.data.update();ob['status']='EXTERIOR_TYPICAL_ASSEMBLED_VISUAL_ACCEPTANCE_PENDING'
scene=bpy.context.scene;scene['status']='K1_TYPICAL_ATTACHED_TOP_DRAFT';scene['delivery']=False
target=out/'GLB_K1_assembled_v019.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target))
ob=bpy.data.objects['K1_TYPICAL_NPM'];faces=[{'object':ob.name,'index':p.index,'points':[list(ob.data.vertices[i].co) for i in p.vertices]} for p in ob.data.polygons]
(out/'final-typical-faces.json').write_text(json.dumps(faces),encoding='utf-8');(out/'final-attach-readback.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
scene=bpy.context.scene;scene.cycles.samples=32;scene.render.filepath=str(out/'GLB_K1_assembled_v019.png');bpy.ops.render.render(write_still=True)
print('FINAL ATTACH',len(faces),'faces',json.dumps(report))

import bpy,bmesh,json
from pathlib import Path
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'GLB_K1_assembled_v020.blend'))
ob=bpy.data.objects['K1_TYPICAL_NPM'];bm=bmesh.new();bm.from_mesh(ob.data);bm.faces.ensure_lookup_table();original=list(bm.faces)
uv=bm.loops.layers.uv.get('Atlas_UV');part=bm.faces.layers.int.get('npm_part_id')
for group in json.loads((out/'reveal-seam-unions.json').read_text()):
 old=[original[i] for i in group['old_indices']];mat=old[0].material_index;pid=old[0][part]
 for r in group['replacement']:
  f=bm.faces.new([bm.verts.new(p) for p in r['points']]);f.material_index=mat;f[part]=pid
  for loop,co in zip(f.loops,r['uv']):loop[uv].uv=co
 bmesh.ops.delete(bm,geom=old,context='FACES_ONLY')
loose=[v for v in bm.verts if not v.link_faces];bmesh.ops.delete(bm,geom=loose,context='VERTS');bm.to_mesh(ob.data);bm.free();ob.data.update()
for node in bpy.data.materials['M_AC_d_o'].node_tree.nodes:
 if node.type=='UVMAP' and node.uv_map=='OpacityUV':node.uv_map='Atlas_UV'
for o in bpy.data.objects:
 if o.type=='MESH' and o.name.startswith('TOP_AC_'):o.data.uv_layers.active.name='Atlas_UV'
target=out/'GLB_K1_assembled_v021.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target))
o=bpy.data.objects['K1_TYPICAL_NPM'];bm=bmesh.new();bm.from_mesh(o.data)
report={'faces':len(bm.faces),'vertices':len(bm.verts),'degenerate_faces':sum(f.calc_area()<1e-9 for f in bm.faces),
 'edges_more_than_two_faces':sum(len(e.link_faces)>2 for e in bm.edges),'reveals_rejoined':33,
 'ac_opacity_uv':'Atlas_UV','ac_finish_uv':'FinishUV','full_quad_retopology_pending':True,'top_draft':True,'delivery_passed':False}
bm.free();faces=[{'object':o.name,'index':p.index,'points':[list(o.data.vertices[i].co) for i in p.vertices]} for p in o.data.polygons]
(out/'v021-faces.json').write_text(json.dumps(faces),encoding='utf-8');(out/'v021-readback.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
scene=bpy.context.scene;scene.render.filepath=str(out/'GLB_K1_assembled_v021.png');bpy.ops.render.render(write_still=True)
print('V021',json.dumps(report))

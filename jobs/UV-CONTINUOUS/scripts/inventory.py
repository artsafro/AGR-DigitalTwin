import bpy, json
from pathlib import Path
root=Path('C:/Users/artsafro/.AGR_Project/jobs/UV-CONTINUOUS/outputs')
o=bpy.context.active_object
m=o.data
if not (root/'source_v001.blend').exists():bpy.ops.wm.save_as_mainfile(filepath=str(root/'source_v001.blend'),copy=True)
m.calc_loop_triangles()
r={'name':o.name,'matrix':[list(x) for x in o.matrix_world],'vertices':[list(o.matrix_world@v.co) for v in m.vertices], 'faces':[list(p.vertices) for p in m.polygons], 'normals':[list(p.normal) for p in m.polygons], 'materials':[p.material_index for p in m.polygons], 'slots':[x.name if x else None for x in m.materials], 'uv':[[list(m.uv_layers.active.data[i].uv) for i in p.loop_indices] for p in m.polygons], 'images':[{'name':i.name,'path':i.filepath,'size':list(i.size)} for i in bpy.data.images], 'nodes':{mat.name:[{'type':n.type,'image':n.image.name if n.type=='TEX_IMAGE' and n.image else None} for n in mat.node_tree.nodes] for mat in m.materials if mat and mat.use_nodes}}
r['triangles']=[{'face':t.polygon_index,'vertices':list(t.vertices)} for t in m.loop_triangles]
(root/'source.json').write_text(json.dumps(r),encoding='utf-8')
print(json.dumps({'slots':r['slots'],'images':r['images'],'nodes':r['nodes']}))

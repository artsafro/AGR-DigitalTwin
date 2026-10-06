"""Export v005 to FBX with approved atlas UV as map channel 1; source stays untouched."""
import bpy,json,sys,shutil
from pathlib import Path
from collections import Counter
out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=False)
src=Path(bpy.data.filepath).parent
manifest=json.loads((src/'manifest.json').read_text(encoding='utf-8'));reference={}
bpy.ops.object.select_all(action='DESELECT')
for name,meta in manifest['objects'].items():
    o=bpy.data.objects[name];m=o.data;keep=meta['new_uv_layer']
    for layer in list(m.uv_layers):
        if layer.name!=keep:m.uv_layers.remove(layer)
    m.uv_layers.active_index=0;m.uv_layers[0].active_render=True
    o.name=f'FACADES_v005_C{meta["corpus"]}_{name}'
    uv=m.uv_layers[0]
    reference[o.name]={'faces':len(m.polygons),'vertices':len(m.vertices),'degrees':dict(Counter(len(p.vertices) for p in m.polygons)),
        'ids':dict(Counter(p.material_index+1 for p in m.polygons)),
        'corners':[[*(o.matrix_world@m.vertices[m.loops[i].vertex_index].co),*uv.data[i].uv] for p in m.polygons for i in p.loop_indices]}
    o.select_set(True)
for cid in ('01','02','03'):shutil.copyfile(src/f'T_Facades_{cid}_Atlas_d.png',out/f'T_Facades_{cid}_Atlas_d.png')
for img in bpy.data.images:
    if img.name.startswith('T_Facades_'):img.filepath_raw=str(out/(img.name+'.png'))
(out/'blender-reference.json').write_text(json.dumps(reference),encoding='utf-8')
bpy.ops.export_scene.fbx(filepath=str(out/'facades_v005.fbx'),use_selection=True,object_types={'MESH'},use_mesh_modifiers=False,
    add_leaf_bones=False,bake_anim=False,path_mode='COPY',embed_textures=False,axis_forward='-Y',axis_up='Z',use_triangles=False)
print('EXPORTED',len(reference),'meshes',sum(v['faces'] for v in reference.values()),'faces')

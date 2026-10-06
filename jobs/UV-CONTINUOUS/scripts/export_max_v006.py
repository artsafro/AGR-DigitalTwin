"""Export the saved wall version in an isolated Blender process and reimport."""
import bpy,json,hashlib,shutil
import numpy as np
from pathlib import Path
from collections import Counter
root=Path('C:/Users/artsafro/.AGR_Project/jobs/UV-CONTINUOUS/outputs')
out=root/'FBX_For_Max_v006';out.mkdir(exist_ok=True)
source=root/'walls_UV550-1500_FlipH_v006.blend'
png=out/'Walls_FlipH_v006_Diffuse.png'
shutil.copy2(root/'T_Template_Address_001_Diffuse_FlipH_v005.1001.png',png)
bpy.ops.wm.open_mainfile(filepath=str(source))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
assert len(objects)==1
obj=objects[0];obj.name='Walls_FlipH_v006'
mat=bpy.data.materials.new('Walls_FlipH_v006_Diffuse');mat.use_nodes=True
bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.85
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(png),check_existing=False)
tex.extension='REPEAT';mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
obj.data.materials.clear();obj.data.materials.append(mat)
obj.data.uv_layers.active_index=0;obj.data.uv_layers[0].active_render=True
def capture(o):
    m=o.data
    return {'vertices':np.array([o.matrix_world@v.co for v in m.vertices]),
            'faces':[list(p.vertices) for p in m.polygons],
            'uv':np.array([x.uv[:] for x in m.uv_layers.active.data]),
            'material_ids':[p.material_index for p in m.polygons]}
before=capture(obj)
for o in bpy.context.scene.objects:o.select_set(False)
obj.select_set(True);bpy.context.view_layer.objects.active=obj
fbx=out/'Walls_FlipH_v006.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},
    global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
    axis_forward='-Y',axis_up='Z',use_mesh_modifiers=False,use_triangles=False,
    mesh_smooth_type='FACE',bake_anim=False,add_leaf_bones=False,
    path_mode='COPY',embed_textures=True,bake_space_transform=False)
# Read the embedded bytes from the actual FBX, rather than infer embedding from options.
from io_scene_fbx import parse_fbx as parse
tree,version=parse.parse(str(fbx))
embedded=[]
def walk(e):
    if e.id==b'Content':
        for value in e.props:
            if isinstance(value,bytes) and value:embedded.append(value)
    for child in e.elems:walk(child)
walk(tree)
image_hash=hashlib.sha256(png.read_bytes()).hexdigest()
assert any(hashlib.sha256(x).hexdigest()==image_hash for x in embedded),'Diffuse not embedded'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(fbx),use_image_search=True)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(objects)==1
imported=objects[0];after=capture(imported)
assert before['faces']==after['faces'],'Topology changed in FBX roundtrip'
assert before['material_ids']==after['material_ids']
uv_error=float(abs(before['uv']-after['uv']).max())
world_error=float(abs(before['vertices']-after['vertices']).max())
assert uv_error<1e-6 and world_error<1e-4
bound=after['vertices'].max(0)-after['vertices'].min(0)
assert len(imported.data.uv_layers)==1
imported_images=[n.image for m in imported.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
assert imported_images,'FBX material did not retain the diffuse'
assert any(hashlib.sha256(Path(bpy.path.abspath(i.filepath)).read_bytes()).hexdigest()==image_hash for i in imported_images if Path(bpy.path.abspath(i.filepath)).exists())
report={'source':str(source),'fbx':str(fbx),'fbx_version':version,'objects':1,'vertices':len(imported.data.vertices),
    'polygon_sizes':dict(Counter(len(p.vertices) for p in imported.data.polygons)),
    'uv_channels':len(imported.data.uv_layers),'uv_max_error':uv_error,'world_max_error_m':world_error,
    'dimensions_m':bound.tolist(),'material_slots':len(imported.data.materials),
    'embedded_diffuse_sha256':image_hash,'embedded_diffuse_verified':True,
    'diffuse_material_binding_verified':True,'mesh_validate_repairs':imported.data.validate(verbose=False),
    'blender_fbx_roundtrip_passed':True,'native_max_import_verified':False}
(out/'FBX_READBACK.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
assert not report['mesh_validate_repairs']
print(json.dumps(report))

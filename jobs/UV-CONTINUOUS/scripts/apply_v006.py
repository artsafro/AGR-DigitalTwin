import bpy,json,shutil
from pathlib import Path
from mathutils import Vector
root=Path('C:/Users/artsafro/.AGR_Project/jobs/UV-CONTINUOUS/outputs')
b=json.loads((root/'build.json').read_text())
o=bpy.context.active_object
assert o.name==b['source']
original=next(m for m in bpy.data.meshes if len(m.polygons)==8755)
mesh=bpy.data.meshes.new(original.name+'_UV1500_v002')
inv=o.matrix_world.inverted()
mesh.from_pydata([inv@Vector(v) for v in b['vertices']],[],b['faces']);mesh.update()
uv=mesh.uv_layers.new(name='UV_1001_Range550_1500')
for poly,coords in zip(mesh.polygons,b['uv']):
    for li,xy in zip(poly.loop_indices,coords):uv.data[li].uv=tuple(max(0,min(1,c)) for c in xy)
attr=mesh.attributes.new('source_face','INT','FACE')
for a,i in zip(attr.data,b['parents']):a.value=i
mat=original.materials[0].copy();mat.name='UDIM_1001_Continuous_FlipH_v005'
src=root/'T_Template_Address_001_Diffuse_FlipH_v005.1001.png'
dest=root/src.name
if not dest.exists():shutil.copy2(src,dest)
im=bpy.data.images.load(str(dest),check_existing=False);im.pack()
for node in mat.node_tree.nodes:
    if node.type=='TEX_IMAGE' and node.image and 'Diffuse' in node.image.name:node.image=im
mesh.materials.append(mat)
o.data=mesh;o['UV_status']='Vertical wall phase aligned; visual acceptance pending';o['density_range_px_m']=[550,1500]
rep={'mesh_validate_repairs':mesh.validate(verbose=False),'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'packed_diffuse':bool(im.packed_file),'image_size':list(im.size)}
for a in bpy.context.screen.areas:
    if a.type=='VIEW_3D':
        a.spaces.active.shading.type='MATERIAL';a.spaces.active.overlay.show_overlays=False
bpy.context.scene.render.resolution_x=1600;bpy.context.scene.render.resolution_y=900;bpy.context.scene.render.resolution_percentage=100
bpy.context.scene.render.filepath=str(root/'trial_view_v002.png')
bpy.context.scene.render.image_settings.file_format='PNG'
bpy.ops.wm.save_as_mainfile(filepath=str(root/'walls_UV550-1500_FlipH_v006.blend'))
(root/'apply.json').write_text(json.dumps(rep,indent=2))
print(json.dumps(rep))

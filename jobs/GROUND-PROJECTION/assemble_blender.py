import bpy,json,collections,hashlib,sys
import numpy as np
from pathlib import Path
from mathutils import Vector
VERSION=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'v001'
ROOT=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION/outputs')/VERSION
bpy.ops.wm.open_mainfile(filepath=str(ROOT.parent/'v001/source_import.blend'))
s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
d=np.load(ROOT/'quad_mesh.npz');v=d['vertices'];f=d['faces'];m=d['materials']
origin=np.array([7944.,0.,0.]) if VERSION!='v001' else np.array([2300.,3800.,0.])
mesh=bpy.data.meshes.new('Ground_projected_quads')
mesh.from_pydata((v-origin).tolist(),[],f.tolist());mesh.update()
obj=bpy.data.objects.new('GROUND_PROJECTED',mesh);s.collection.objects.link(obj);obj.location=origin
for mat in bpy.data.objects['Ground'].data.materials:mesh.materials.append(mat)
mesh.polygons.foreach_set('material_index',m.astype(np.int32));mesh.polygons.foreach_set('use_smooth',np.zeros(len(f),dtype=bool))
for name,values in [('source_ground_face',d['source_faces']),('extrapolated',d['extrapolated'].astype(np.int32))]:
    attr=mesh.attributes.new(name,'INT','FACE');attr.data.foreach_set('value',values)
obj['source_file']='GROUND.fbx';obj['projection']='Vertical Z; XY contours preserved within documented numeric tolerance'
obj['source_overlap_policy']='Original coverage overlaps retained by user request'
obj['outside_relief']='Nearest terrain triangle plane extension authorized by user'
obj['material_ids']='Original source slots retained; Max ID = Blender material_index + 1'
for o in s.objects:
    if o!=obj:o.hide_set(True);o.hide_render=True;o.select_set(False)
obj.select_set(True);bpy.context.view_layer.objects.active=obj
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active;sp.clip_end=100000;sp.shading.type='SOLID';sp.shading.color_type='MATERIAL'
            sp.region_3d.view_location=Vector((2300,3800,250));sp.region_3d.view_distance=20000
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f'GROUND_projected_{VERSION}.blend'))
bpy.ops.export_scene.fbx(filepath=str(ROOT/f'GROUND_projected_{VERSION}.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',use_mesh_modifiers=False,use_triangles=False,mesh_smooth_type='FACE',bake_anim=False,add_leaf_bones=False,path_mode='STRIP',use_custom_props=True)
mapping=[{'max_material_id':i+1,'blender_slot':i,'name':mat.name,'faces':int(np.sum(m==i))} for i,mat in enumerate(mesh.materials)]
(ROOT/'material_ids.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')
local=np.empty(len(mesh.vertices)*3,dtype=np.float64);mesh.vertices.foreach_get('co',local)
matrix=np.array(obj.matrix_world,dtype=np.float64)
np.savez_compressed(ROOT/'blend_geometry.npz',vertices=local.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3],faces=f,materials=m)
print('ASSEMBLY',len(v),len(f),len(mapping),flush=True)

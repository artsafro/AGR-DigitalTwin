import bpy
path=r'C:\Users\artsafro\.AGR_Project\jobs\FACADE-SIGNS\outputs\v001\facade_signs_v001.blend'
previous=bpy.context.scene.name
with bpy.data.libraries.load(path,link=False) as (src,dst):
    dst.scenes=src.scenes
scene=dst.scenes[0]
scene.name='FACADE_SIGNS_v001'
if bpy.context.window:
    bpy.context.window.scene=scene
    for area in bpy.context.window.screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.shading.color_type='MATERIAL'
print({'shown_scene':scene.name,'previous_scene_preserved':previous,'source_blend':path,'existing_file_not_overwritten':True})

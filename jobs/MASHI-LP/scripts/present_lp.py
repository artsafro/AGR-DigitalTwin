import bpy
from mathutils import Vector
for name in ['LP','Revit','LP_old']:
    for o in bpy.data.collections[name].objects:
        o.hide_set(name!='LP')
        o.hide_render=name!='LP'
        o.select_set(False)
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        sp=area.spaces.active
        sp.region_3d.view_perspective='ORTHO'
        sp.region_3d.view_location=Vector((22,-43,16))
        sp.region_3d.view_distance=85
        sp.region_3d.view_rotation=Vector((100,-100,-70)).to_track_quat('-Z','Y')
        sp.shading.type='SOLID'
bpy.ops.wm.save_as_mainfile(filepath='C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/audit-v001/organized-v001.blend')
print('LP isolated; Revit and LP_old preserved and hidden; saved')

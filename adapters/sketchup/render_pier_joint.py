import bpy
from pathlib import Path
from mathutils import Vector
out=Path('jobs/GLB-NPM/outputs/clearance-ab-v010').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'GLB_AB_clearance_v010.blend'))
win=next(o for o in bpy.data.objects if o.get('role')=='windows' and o.name.startswith('A_'))
scene=bpy.context.scene;cam=scene.camera;scene.cycles.samples=24
# View upward at the actual A/B joint; no clipping/hiding the receiving belt.
aim=win.matrix_world@Vector((.9,.5,1.14))
direction=win.matrix_world.to_3x3()@Vector((-1,1,-.55)).normalized()
cam.location=aim+direction*7
cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.ortho_scale=2.3;scene.render.resolution_x=1400;scene.render.resolution_y=1100
scene.render.filepath=str(out/'pier_upper_joint.png');bpy.ops.render.render(write_still=True)

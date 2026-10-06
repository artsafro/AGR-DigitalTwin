import bpy,json
from pathlib import Path
from mathutils import Matrix,Vector
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'GLB_K1_assembled_v022.blend'))
row=next(r for r in json.loads((out/'floor-instances.json').read_text()) if r['definition_id']==170455)
m=Matrix(row['matrix_inches']);m.translation*=.0254
m=m@Matrix.Translation((0,0,.02))@Matrix(json.loads((out/'closeup-window-frame.json').read_text()))
aim=m@Vector((.9,.5,1.14));direction=m.to_3x3()@Vector((-1,1,-.55)).normalized()
scene=bpy.context.scene;cam=scene.camera;cam.location=aim+direction*7
cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=2.3
scene.render.resolution_x=1400;scene.render.resolution_y=1100;scene.cycles.samples=32
scene.render.filepath=str(out/'straight_pier_joint_v022.png');bpy.ops.render.render(write_still=True)

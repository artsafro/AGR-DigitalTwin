"""Isolated native renders of editable snapshot and actual reimport, same cameras."""
from pathlib import Path
import json
import sys
import math
import bpy
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_snapshot_common import render_scope, orthographic_fit

if not bpy.app.background:
    raise RuntimeError('Background-only comparison')
cfg=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
out=Path(cfg['output_dir']);out.mkdir(parents=True,exist_ok=True)
if (out/'render-evidence.json').exists():
    raise FileExistsError(out/'render-evidence.json')
camera_parameters=None
view_scales={}
evidence={'scope':'Native source/reimport renders, no visual approval implied',
          'mesh_names':cfg['mesh_names'],'renders':[]}
for label in ('source','reimport'):
    if label=='source':
        bpy.ops.wm.open_mainfile(filepath=cfg['blend'],load_ui=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=cfg['fbx'],use_image_search=False)
    scene=bpy.context.scene
    meshes=render_scope(scene.objects, cfg['mesh_names'])
    # Keep parent/constraint/modifier dependencies; only their render visibility
    # is suppressed. Removing reference objects can alter the selected geometry.
    for obj in list(scene.objects):
        obj.hide_render = obj not in meshes
    points=[o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
    minimum=Vector([min(p[i] for p in points) for i in range(3)])
    maximum=Vector([max(p[i] for p in points) for i in range(3)])
    if camera_parameters is None:
        center=(minimum+maximum)/2
        extent=max(maximum-minimum)
        camera_parameters=(center,extent)
    center,extent=camera_parameters
    for obj in meshes:
        obj.hide_render=False
    world=bpy.data.worlds.new('DT_CompareWorld');scene.world=world;world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(0.65,0.65,0.65,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=0.6
    light_data=bpy.data.lights.new('DT_CompareSun','SUN');light_data.energy=2.0
    sun=bpy.data.objects.new('DT_CompareSun',light_data);scene.collection.objects.link(sun)
    sun.rotation_euler=(math.radians(25),math.radians(-25),math.radians(-25))
    cam_data=bpy.data.cameras.new('DT_CompareCamera');cam_data.type='ORTHO'
    cam=bpy.data.objects.new('DT_CompareCamera',cam_data);scene.collection.objects.link(cam);scene.camera=cam
    scene.render.engine='BLENDER_EEVEE_NEXT'
    scene.render.resolution_x=1400;scene.render.resolution_y=600;scene.render.resolution_percentage=100
    scene.render.pixel_aspect_x=1;scene.render.pixel_aspect_y=1
    scene.render.image_settings.file_format='PNG'
    for view,offset in [('front',(0,-1,0.07)),('oblique',(0.65,-1,0.35))]:
        target=out/f'{label}-{view}.png'
        if target.exists():
            raise FileExistsError(target)
        cam.location=center+Vector(offset)*extent*2
        cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
        if label == 'source':
            rotation=cam.rotation_euler.to_matrix()
            right,up=rotation@Vector((1,0,0)),rotation@Vector((0,1,0))
            x=[(p-center).dot(right) for p in points]
            y=[(p-center).dot(up) for p in points]
            aspect=scene.render.resolution_x/scene.render.resolution_y
            view_scales[view]=orthographic_fit(x,y,aspect)
        cam_data.ortho_scale=view_scales[view]
        scene.render.filepath=str(target)
        bpy.ops.render.render(write_still=True)
        evidence['renders'].append({'label':label,'view':view,'path':str(target),
                                    'mesh_names':[obj.name for obj in meshes],
                                    'ortho_scale':cam_data.ortho_scale,
                                    'camera_world':[list(r) for r in cam.matrix_world]})
(out/'render-evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print('PROFILE_COMPARISON_RENDERED',len(evidence['renders']))

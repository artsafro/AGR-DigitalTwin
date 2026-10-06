import bpy,sys
from pathlib import Path
from mathutils import Vector
ver=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'v002'
ROOT=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION/outputs')/ver
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(ROOT/f'GROUND_projected_{ver}.fbx'),use_image_search=False)
s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH';s.render.resolution_x=1400;s.render.resolution_y=1200;s.render.resolution_percentage=100
s.display.shading.light='STUDIO';s.display.shading.color_type='MATERIAL';s.display.shading.show_shadows=True;s.display.shading.show_cavity=True
s.display.shading.cavity_type='BOTH';s.display.shading.curvature_ridge_factor=1.4;s.display.shading.curvature_valley_factor=1.2
s.display.shading.background_type='VIEWPORT';s.display.shading.background_color=(.08,.08,.08)
cam=bpy.data.objects.new('QA Camera',bpy.data.cameras.new('QA Camera'));s.collection.objects.link(cam);s.camera=cam;cam.data.type='ORTHO';cam.data.clip_end=100000
views=[('overview',(12500,-13500,16500),(2300,3800,200),21000),('top',(2300,3800,30000),(2300,3800,0),19000),('detail',(-5500,500,3200),(-2100,4500,180),6000)]
for name,eye,target,size in views:
    cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=size
    s.render.filepath=str(ROOT/f'{name}.png');bpy.ops.render.render(write_still=True)

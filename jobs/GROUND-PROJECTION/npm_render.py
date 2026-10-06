import bpy,sys
from pathlib import Path
from mathutils import Vector
R=Path(r'C:/Users/artsafro/.AGR_Project/jobs/GROUND-PROJECTION/outputs/v008')
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.system='METRIC'
bpy.ops.import_scene.fbx(filepath=str(R/'GROUND_NPM_QUADS_v008.fbx'),use_image_search=False)
s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH';s.render.resolution_x=1500;s.render.resolution_y=1300;s.render.resolution_percentage=100
s.display.shading.light='STUDIO';s.display.shading.color_type='MATERIAL';s.display.shading.show_shadows=True;s.display.shading.show_cavity=False;s.display.shading.background_type='VIEWPORT';s.display.shading.background_color=(.12,.12,.12)
cam=bpy.data.objects.new('QA_CAMERA',bpy.data.cameras.new('QA_CAMERA'));s.collection.objects.link(cam);s.camera=cam;cam.data.type='ORTHO';cam.data.clip_end=10000
def render(name,eye,target,size):
 cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=size;s.render.filepath=str(R/f'{name}.png');bpy.ops.render.render(write_still=True)
render('overview',(125,-135,165),(23,38,2),210)
render('detail',(-55,5,32),(-21,45,1.8),60)
render('top',(23,38,300),(23,38,0),190)
o=next(o for o in s.objects if o.type=='MESH');mat=bpy.data.materials.new('QA_WIRE');mat.diffuse_color=(.025,.025,.025,1);o.data.materials.append(mat)
curve=bpy.data.curves.new('QA_EDGE_LINES','CURVE');curve.dimensions='3D';curve.bevel_depth=.006;curve.bevel_resolution=0;curve.resolution_u=1
for edge in o.data.edges:
 spl=curve.splines.new('POLY');spl.points.add(1)
 for point,idx in zip(spl.points,edge.vertices):
  v=o.matrix_world@o.data.vertices[idx].co;point.co=(*v,1)
wire=bpy.data.objects.new('QA_EDGES',curve);s.collection.objects.link(wire);curve.materials.append(mat)
render('wire_overview',(125,-135,165),(23,38,2),210)
render('wire_detail',(-55,5,32),(-21,45,1.8),60)





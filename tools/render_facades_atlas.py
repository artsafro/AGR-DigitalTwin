"""Render packed atlas readback; never save visualization changes to the model."""
import bpy, sys, json, math
from pathlib import Path
from mathutils import Vector

out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
meta=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
scene=bpy.context.scene
scene.render.engine='BLENDER_EEVEE_NEXT'
scene.render.resolution_x=1400
scene.render.resolution_y=1000
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.world.color=(.18,.18,.18)
scene.view_settings.view_transform='Standard'
scene.view_settings.look='None'
scene.view_settings.exposure=0
scene.view_settings.gamma=1
for mat in bpy.data.materials:
 if not mat.use_nodes: continue
 nodes=mat.node_tree.nodes
 textures=[n for n in nodes if n.type=='TEX_IMAGE' and n.image]
 if not textures: continue
 output=next((n for n in nodes if n.type=='OUTPUT_MATERIAL'),None)
 if not output: continue
 emission=nodes.new('ShaderNodeEmission')
 mat.node_tree.links.new(textures[0].outputs['Color'],emission.inputs['Color'])
 mat.node_tree.links.new(emission.outputs[0],output.inputs['Surface'])
camdata=bpy.data.cameras.new('Atlas_QA_camera')
camera=bpy.data.objects.new('Atlas_QA_camera',camdata)
scene.collection.objects.link(camera);scene.camera=camera
camdata.type='ORTHO';camdata.clip_end=10000
objects=[bpy.data.objects[n] for n in meta['objects']]
for o in scene.objects:
 if o.type=='MESH':o.hide_render=True
for obj in objects:
 obj.hide_render=False
 points=[obj.matrix_world@Vector(p) for p in obj.bound_box]
 center=sum(points,Vector())/8
 angle=math.radians(meta['objects'][obj.name]['principal_tangent_angle_deg'])
 tangent=Vector((math.cos(angle),math.sin(angle),0))
 normal=Vector((-tangent.y,tangent.x,0))
 direction=(normal*.95+tangent*.45+Vector((0,0,.4))).normalized()
 camera.location=center+direction*300
 camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
 bpy.context.view_layer.update()
 inv=camera.matrix_world.inverted()
 cp=[inv@p for p in points]
 camdata.ortho_scale=max((max(p.y for p in cp)-min(p.y for p in cp))*1.4,max(p.x for p in cp)-min(p.x for p in cp))*1.15
 scene.render.filepath=str(out/(obj.name+'_overview.png'))
 bpy.ops.render.render(write_still=True)
 # A real facade polygon close-up, oriented from its outward normal.
 candidates=[p for p in obj.data.polygons if p.material_index==100 and abs(p.normal.z)<.1]
 p=max(candidates,key=lambda p:p.area)
 target=obj.matrix_world@p.center
 normal=(obj.matrix_world.to_3x3()@p.normal).normalized()
 camera.location=target+normal*30
 camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
 camdata.ortho_scale=6
 scene.render.filepath=str(out/(obj.name+'_brick_detail.png'))
 bpy.ops.render.render(write_still=True)
 obj.hide_render=True

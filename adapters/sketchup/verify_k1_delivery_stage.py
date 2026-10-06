import bpy,bmesh,json,sys
from pathlib import Path
from mathutils import Matrix,Vector
out=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'GLB_K1_assembled_v019.blend'))
o=bpy.data.objects['K1_TYPICAL_NPM'];bm=bmesh.new();bm.from_mesh(o.data)
kill=[f for f in bm.faces if f.calc_area()<1e-9];removed=len(kill);bmesh.ops.delete(bm,geom=kill,context='FACES')
loose=[v for v in bm.verts if not v.link_faces];bmesh.ops.delete(bm,geom=loose,context='VERTS');bm.to_mesh(o.data);bm.free();o.data.update()
scene=bpy.context.scene;scene['status']='TYPICAL_ATTACHED_INTERIOR_CLEAN_TOP_DRAFT';scene['delivery']=False
target=out/'GLB_K1_assembled_v020.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target))
o=bpy.data.objects['K1_TYPICAL_NPM'];bm=bmesh.new();bm.from_mesh(o.data)
report={'saved_file':str(target),'removed_faces_below_1e_9_m2':removed,'faces':len(bm.faces),'vertices':len(bm.verts),
 'degenerate_faces':sum(f.calc_area()<1e-9 for f in bm.faces),'edges_more_than_two_faces':sum(len(e.link_faces)>2 for e in bm.edges),
 'face_sizes':{str(n):sum(len(f.verts)==n for f in bm.faces) for n in sorted(set(len(f.verts) for f in bm.faces))},
 'top_status':'DRAFT: unique upper block has not passed cleanup/UV/clearance review','delivery_passed':False}
bm.free()
faces=[{'object':o.name,'index':p.index,'points':[list(o.data.vertices[i].co) for i in p.vertices]} for p in o.data.polygons]
(out/'final-v020-faces.json').write_text(json.dumps(faces),encoding='utf-8');(out/'final-v020-readback.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
scene=bpy.context.scene;scene.cycles.samples=32;scene.render.filepath=str(out/'GLB_K1_assembled_v020.png');bpy.ops.render.render(write_still=True)
# Reuse source window frame solely to place the diagnostic camera.
with bpy.data.libraries.load(str(out.parent/'clearance-ab-v007/GLB_AB_clearance_v007.blend'),link=False) as (source,dest):
 dest.objects=[next(n for n in source.objects if n.startswith('A_windows_'))]
template=dest.objects[0];row=next(r for r in json.loads((out/'floor-instances.json').read_text()) if r['definition_id']==170455)
m=Matrix(row['matrix_inches']);m.translation*=.0254;m=m@Matrix.Translation((0,0,.02))@template.matrix_world
aim=m@Vector((.9,.5,1.14));direction=m.to_3x3()@Vector((-1,1,-.55)).normalized();cam=scene.camera
cam.location=aim+direction*7;cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=2.3
scene.render.resolution_x=1400;scene.render.resolution_y=1100;scene.render.filepath=str(out/'straight_pier_joint_v020.png');bpy.ops.render.render(write_still=True)
bpy.data.objects.remove(template,do_unlink=True)
print('V020',json.dumps(report))

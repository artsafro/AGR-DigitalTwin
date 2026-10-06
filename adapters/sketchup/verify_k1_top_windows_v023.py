"""Saved-file checks and a fixed-camera window/reveal comparison."""
import bpy, json, hashlib
from pathlib import Path
from mathutils import Vector

root=Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
reports={}
for version in (22,23):
 bpy.ops.wm.open_mainfile(filepath=str(root/f'GLB_K1_assembled_v{version:03d}.blend'))
 body=bpy.data.objects['K1_TYPICAL_NPM'].data
 payload=bytearray()
 for v in body.vertices:payload.extend(f'{v.co.x:.7f},{v.co.y:.7f},{v.co.z:.7f};'.encode())
 for p in body.polygons:payload.extend((','.join(map(str,p.vertices))+';').encode())
 wins=[o for o in bpy.data.objects if o.name.startswith('TOP_Window')]
 mesh=bpy.data.objects.get('K1_TOP_REVEALS_10MM')
 rows=[]
 for o in wins:
  zz=[(o.matrix_world@v.co).z for v in o.data.vertices]
  center=o.matrix_world@o.data.polygons[0].center
  normal=o.matrix_world.to_3x3()@o.data.polygons[0].normal
  radial=Vector((center.x-14.25,center.y-6.0,0))
  rows.append({'name':o.name,'definition':o.get('source_definition'),'z':[min(zz),max(zz)],
               'faces':len(o.data.polygons),'normal_outward':normal.dot(radial)>0})
 reports[str(version)]={'typical_sha256':hashlib.sha256(payload).hexdigest(),
                        'window_count':len(wins),'windows':rows,
                        'reveal_faces':len(mesh.data.polygons) if mesh else 0,
                        'reveal_degenerate':sum(p.area<1e-7 for p in mesh.data.polygons) if mesh else 0}
 scene=bpy.context.scene
 scene.render.engine='BLENDER_WORKBENCH'
 scene.display.shading.light='STUDIO'
 scene.display.shading.color_type='MATERIAL'
 scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
 cam=scene.camera
 target=Vector((4.908,-3.902,69.25))
 outward=Vector((-.0976,-.9952,0))
 cam.location=target+outward*7+Vector((0,0,1.2))
 cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
 cam.data.type='ORTHO';cam.data.ortho_scale=7.8
 scene.render.filepath=str(root/f'top-windows-v{version:03d}-closeup.png')
 bpy.ops.render.render(write_still=True)
assert reports['22']['typical_sha256']==reports['23']['typical_sha256']
assert reports['23']['window_count']==44 and reports['23']['reveal_faces']==154
assert reports['23']['reveal_degenerate']==0
assert all(r['z'][1]<68.93 for r in reports['23']['windows'] if r['definition']!=14155)
assert all(r['z'][0]>70.0 for r in reports['23']['windows'] if r['definition']==14155)
assert all(r['normal_outward'] for r in reports['23']['windows'])
(root/'top-windows-v023-readback.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
scope=[o for o in bpy.data.objects if o.name.startswith('TOP_Window')]
scope += [bpy.data.objects[n] for n in ('K1_TOP_REVEALS_10MM','TOP_[Black Lines 1]','TOP_Материал8')]
faces=[]
for o in scope:
 for p in o.data.polygons:
  faces.append({'object':o.name,'index':p.index,
                'points':[list(o.matrix_world@o.data.vertices[i].co) for i in p.vertices]})
(root/'top-windows-v023-faces.json').write_text(json.dumps(faces),encoding='utf-8')
print('TOP_WINDOW_READBACK='+json.dumps({k:{'typical_sha256':v['typical_sha256'],'window_count':v['window_count'],'reveal_faces':v['reveal_faces'],'reveal_degenerate':v['reveal_degenerate']} for k,v in reports.items()}))

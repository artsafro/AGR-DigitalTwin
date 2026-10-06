import bpy, bmesh, json
from pathlib import Path
from mathutils import Vector
import os
ROOT=Path(os.environ['AGR_BOX_LIGHT_OUTPUT']).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
assert not (ROOT/'frames_box_lights_v002.blend').exists(), 'Refusing to overwrite result'
assert bpy.data.objects.get('BoxLights_AllFrames_v001') is None, 'Use original source scene'
source=json.loads((ROOT/'box_light_source_audit.json').read_text())
candidates=json.loads((ROOT/'box_light_candidates.json').read_text())
frame=bpy.data.objects['frames']; sample=bpy.data.objects['box_light']
assert len(frame.data.vertices)==3118 and len(frame.data.polygons)==2352
inset=.1146; drop=.0211029052734375; height=.09459304809570312
vertices=[]; faces=[]; mapping=[]; skipped=[]; planar_corrections=[]
for f in candidates['selected']:
    if f['id']==1081:
        skipped.append({'face':1081,'reason':'existing sample retained'}); continue
    pts=[frame.matrix_world @ frame.data.vertices[i].co for i in f['v']]
    assert len(pts)==4
    # Native inset preserves the original slightly warped corner geometry.
    local=bmesh.new(); vv=[local.verts.new(p) for p in pts]; ff=local.faces.new(vv)
    local.normal_update()
    bmesh.ops.inset_region(local,faces=[ff],thickness=inset,depth=0,use_even_offset=True,use_boundary=True)
    inner=[v.co.copy()-Vector((0,0,drop)) for v in ff.verts]
    local.normal_update(); normal=ff.normal.copy()
    center=sum(inner,Vector())/4
    z_adjust=[-(p-center).dot(normal)/normal.z for p in inner]
    local_height=height
    if max(abs(z) for z in z_adjust)>1e-5:
        down=max(z_adjust)
        local_height=max(height,drop+max(z_adjust)-min(z_adjust)+.0101)
        for p,dz in zip(inner,z_adjust):p.z+=dz-down
        planar_corrections.append({'source_face':f['id'],'maximum_extra_drop_m':max(z_adjust)-min(z_adjust),'height_m':local_height})
    local.free()
    assert len(inner)==4
    base=len(vertices); vertices.extend(inner); vertices.extend(p+Vector((0,0,local_height)) for p in inner)
    faces.append(tuple(base+i for i in range(4)))
    for i in range(4):
        j=(i+1)%4; faces.append((base+j,base+i,base+i+4,base+j+4))
    ci=next(c['component'] for c in candidates['components'] if f['id'] in c['faces'])
    mapping.append({'frame_component':ci,'source_face':f['id'],'vertex_start':base,'face_start':len(faces)-5})
mesh=bpy.data.meshes.new('BoxLights_AllFrames_v001'); mesh.from_pydata(vertices,[],faces); mesh.update()
obj=bpy.data.objects.new('BoxLights_AllFrames_v001',mesh); bpy.context.scene.collection.objects.link(obj)
obj.color=(1,.7,.2,1)
obj['inset_m']=inset; obj['drop_m']=drop; obj['height_m']=height
obj['open_top_intentional']=True; obj['source_object']='frames'
for mat in sample.data.materials: mesh.materials.append(mat)
attr=mesh.attributes.new('source_frame_face','INT','FACE')
for item in mapping:
    for j in range(5):attr.data[item['face_start']+j].value=item['source_face']
bm=bmesh.new(); bm.from_mesh(mesh)
qa={'new_lights':len(mapping),'total_lights_including_sample':len(mapping)+1,'frame_components_served':len({m['frame_component'] for m in mapping})+1,'quads':len(faces),'non_quads':sum(len(f.verts)!=4 for f in bm.faces),'zero_area':sum(f.calc_area()<1e-10 for f in bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),'edges_more_than_two_faces':sum(len(e.link_faces)>2 for e in bm.edges),'duplicate_faces':len(faces)-len({tuple(sorted(tuple(round(x,6) for x in vertices[i]) for i in f)) for f in faces}),'inset_m':inset,'height_m':height,'drop_m':drop,'skipped':skipped,'mapping':mapping,'delivery_passed':False,'pending':['visual acceptance','AGR Checker and export outside this modeling stage']}
bm.free()
assert qa['non_quads']==qa['zero_area']==qa['edges_more_than_two_faces']==qa['duplicate_faces']==0
assert qa['boundary_edges']==4*len(mapping)
qa['planar_corrections']=planar_corrections
(ROOT/'box_lights_v002_qa.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'frames_box_lights_v002.blend'))
print(json.dumps({k:v for k,v in qa.items() if k not in ('mapping','pending','planar_corrections')}))

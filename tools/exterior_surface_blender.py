"""Build or independently read back an exterior-only pre-Shell Blender surface."""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

p=Path(sys.argv[sys.argv.index('--')+1]).resolve()
source=np.load(p/'exterior-surface.npz')
report=json.loads((p/'exterior-surface.json').read_text(encoding='utf-8'))
blend=p/'OBR22_K02_typical_floor_v006_EXTERIOR.blend'

if '--check' in sys.argv:
    digest=hashlib.sha256(blend.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    assert len(meshes)==1
    obj=meshes[0];mesh=obj.data
    v=np.empty(len(mesh.vertices)*3);mesh.vertices.foreach_get('co',v);v=v.reshape(-1,3)
    degree=np.empty(len(mesh.polygons),dtype=np.int32);mesh.polygons.foreach_get('loop_total',degree)
    assert (degree==4).all()
    f=np.empty(len(mesh.loops),dtype=np.int32);mesh.loops.foreach_get('vertex_index',f);f=f.reshape(-1,4)
    labels=np.empty(len(f),dtype=np.int32);mesh.attributes['facade_run_index'].data.foreach_get('value',labels)
    assert np.array_equal(f,source['faces']) and np.array_equal(labels,source['facade_indices'])
    assert json.loads(bpy.data.texts['EXTERIOR_source_profiles.json'].as_string())==report
    edges=np.sort(np.stack([f,np.roll(f,-1,axis=1)],axis=2).reshape(-1,2),axis=1)
    unique,counts=np.unique(edges,axis=0,return_counts=True)
    boundary=unique[counts==1]
    boundary_degree=defaultdict(int)
    for edge in boundary:
        for i in edge:boundary_degree[int(i)]+=1
    q=v[f];lengths=np.linalg.norm(np.roll(q,-1,axis=1)-q,axis=2)
    shell=obj.modifiers.get('SHELL_0.4m_AFTER_SURFACE_REVIEW')
    result={'blend':str(blend),'sha256':digest,'scope':'exterior surface only, before Shell',
            'vertices':len(v),'quads':len(f),'exact_duplicate_vertices':len(v)-len(np.unique(v,axis=0)),
            'exact_duplicate_faces':len(f)-len(np.unique(np.sort(f,axis=1),axis=0)),
            'edges_with_more_than_two_faces':int((counts>2).sum()),
            'intentional_boundary_edges':len(boundary),'boundary_junction_vertices':sum(n!=2 for n in boundary_degree.values()),
            'minimum_edge_m':float(lengths.min()),'faces_with_edge_below_10mm':int((lengths.min(axis=1)<.01).sum()),
            'readback_max_error_m':float(np.linalg.norm(v-source['vertices'],axis=1).max()),
            'source_mapping_readback':True,'shell_thickness_m':shell.thickness,
            'shell_enabled':shell.show_viewport or shell.show_render,
            'geometry_checks_passed':False,'passed':False,
            'remaining':['Independent exterior/profile/overlap verification','Surface review before enabling and validating Shell']}
    assert not result['shell_enabled']
    np.savez_compressed(p/'exterior-readback.npz',vertices=v,faces=f,facade_indices=labels)
    (p/'exterior-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result))
    raise SystemExit(0)

bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.length_unit='METERS'
collection=bpy.data.collections.new('01_BODY_EXTERIOR_ONLY');s.collection.children.link(collection)
mesh=bpy.data.meshes.new('Exterior_faces_openings_only')
mesh.from_pydata(source['vertices'].tolist(),[],source['faces'].tolist());mesh.update()
obj=bpy.data.objects.new('BODY_Наружные_фейсы_без_интерьера',mesh);collection.objects.link(obj)
obj.color=(.75,.77,.79,1)
mesh.attributes.new('facade_run_index','INT','FACE').data.foreach_set('value',source['facade_indices'])
obj['stage']='Exterior surface with removed opening faces. Interior not modelled.'
obj['mapping']='facade_run_index -> EXTERIOR_source_profiles.json -> original wall source indices'
shell=obj.modifiers.new('SHELL_0.4m_AFTER_SURFACE_REVIEW','SOLIDIFY')
shell.thickness=.4;shell.offset=-1;shell.use_even_offset=True;shell.use_quality_normals=True
shell.show_viewport=False;shell.show_render=False
build=json.loads((p/'body-build.json').read_text(encoding='utf-8'))
s['local_to_revit_internal_m']=build['local_to_revit_internal_m']
s['status']='Exterior-only pre-Shell surface. Shell 0.4m inward is configured but disabled and unvalidated.'
bpy.data.texts.new('EXTERIOR_source_profiles.json').write(json.dumps(report,ensure_ascii=False,indent=2))
bpy.data.texts.new('EXTERIOR_source_walls.json').write(json.dumps(build['wall_records'],ensure_ascii=False,indent=2))
bpy.data.texts.new('READ_ME.txt').write('Только наружные фейсы по периметру. Интерьера нет.\n'
    'Открытые границы сверху/снизу и проёмов намеренны: это этап до Shell.\n'
    'Shell внутрь 0.4м настроен, но ВЫКЛЮЧЕН. После проверки наружной сетки включить и отдельно проверить толщину/стыки.\n'
    'Происхождение размеров и нормализация субмиллиметрового шума записаны в EXTERIOR_source_profiles.json.\n')
cams=bpy.data.collections.new('00_Камеры');s.collection.children.link(cams)
def camera(name,target,direction,scale):
    data=bpy.data.cameras.new(name);data.type='ORTHO';data.ortho_scale=scale;data.clip_end=1000
    cam=bpy.data.objects.new(name,data);cams.objects.link(cam)
    target=Vector(target);cam.location=target+Vector(direction).normalized()*150
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();return cam
v=source['vertices'];center=(v.min(axis=0)+v.max(axis=0))/2
overview=camera('Наружная_оболочка',center,(.1,-1.2,1),94)
detail=camera('Сетка_наружного_проёма',(-20.14,8.45,1.5),(.8,14,4),5.2)
s.render.engine='BLENDER_WORKBENCH';s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG'
sh=s.display.shading;sh.light='FLAT';sh.color_type='OBJECT';sh.show_shadows=True;sh.show_cavity=True;sh.cavity_type='BOTH'
sh.show_object_outline=True;sh.show_backface_culling=False;sh.background_type='VIEWPORT';sh.background_color=(.025,.04,.065)
s.world=bpy.data.worlds.new('Studio');s.world.color=(.015,.025,.045);s.camera=overview
bpy.context.view_layer.objects.active=obj;obj.select_set(True)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=65
            area.spaces.active.region_3d.view_location=Vector(center)
            area.spaces.active.region_3d.view_rotation=overview.rotation_euler.to_quaternion()
            area.spaces.active.shading.color_type='OBJECT';area.spaces.active.overlay.show_extras=False
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
# Wire is a render-only inspection object, never saved into the master file.
wire=obj.copy();wire.data=obj.data.copy();collection.objects.link(wire);wire.color=(.015,.018,.022,1)
mod=wire.modifiers.new('PREVIEW_WIRE_ONLY','WIREFRAME');mod.thickness=.004;mod.use_replace=True
for cam,name,w,h in [(overview,'exterior-overview-wire.png',2000,900),(detail,'exterior-opening-wire.png',1400,1000)]:
    s.camera=cam;s.render.resolution_x=w;s.render.resolution_y=h;s.render.filepath=str(p/name)
    bpy.ops.render.render(write_still=True)
print('SAVED',str(blend),len(mesh.polygons),'quads')

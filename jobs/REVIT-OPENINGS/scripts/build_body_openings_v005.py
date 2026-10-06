"""Replace marked body planes with outward-facing simple frames in a scene copy."""
import json
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/body-v005'
mapping=json.loads((OUT/'body-opening-map.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=mapping['source_autosave'])
scene=bpy.context.scene
body=bpy.data.objects[mapping['body_object']]
original_faces=len(body.data.polygons)

# The imported FBX remains in this copy for provenance, but the new body is the active target.
body_collection=bpy.data.collections.new('SOSH1150_BODY_WITH_OPENINGS_v005')
scene.collection.children.link(body_collection)
body_collection.objects.link(body)
for old_collection in list(body.users_collection):
    if old_collection!=body_collection:
        old_collection.objects.unlink(body)
        old_collection.hide_viewport=True
        old_collection.hide_render=True

confirmed=bpy.data.collections.new('FRAMES_BODY_FBX_MATCH_OR_CLOSE_SIZE')
review=bpy.data.collections.new('FRAMES_SCALED_REVIEW_REQUIRED')
scene.collection.children.link(confirmed)
scene.collection.children.link(review)

type_ids={r['type_id'] for r in mapping['records']}
library=str(ROOT/'outputs/openings-v003/SOSH1150_Openings_v003.blend')
def get_id(name):
    return next((id for id in sorted(type_ids,key=len,reverse=True) if name.startswith(id+'_')),None)
with bpy.data.libraries.load(library,link=False) as (source,target):
    target.objects=[name for name in source.objects if get_id(name) and not name.endswith('_LABEL')]
assets={get_id(obj.name):obj for obj in target.objects if obj and obj.type=='MESH'}
assert set(assets)==type_ids

placed=[]
for row in mapping['records']:
    obj=assets[row['type_id']].copy()
    obj.name=row['id']+'_'+row['type_id']
    (review if 'review required' in row['confidence'] else confirmed).objects.link(obj)
    right=Vector(row['right']);normal=Vector(row['normal_out'])
    columns=(right*(row['width_m']/row['source_type_width_m']),
             -normal,Vector((0,0,row['height_m']/row['source_type_height_m'])))
    matrix=Matrix.Identity(4)
    for j,col in enumerate(columns):
        for i in range(3):matrix[i][j]=col[i]
    matrix.translation=Vector(row['origin'])
    obj.matrix_world=matrix
    obj['type_id']=row['type_id']
    obj['body_group_index']=row['body_group_index']
    obj['body_face_indices_json']=json.dumps(row['body_face_indices'])
    obj['source_material']='2 окна / ID 2'
    obj['assignment_basis']=row['assignment_basis']
    obj['confidence']=row['confidence']
    obj['frame_faces_outward']=True
    obj['source_plane_size_m']=f"{row['width_m']}x{row['height_m']}"
    obj.color=(.19,.72,.88,1) if obj.users_collection[0]==confirmed else (.98,.61,.22,1)
    placed.append(obj)

# Remove only the planes marked with the window ID; the extrusion/returns stay.
bm=bmesh.new();bm.from_mesh(body.data);bm.faces.ensure_lookup_table()
target_indices={i for row in mapping['records'] for i in row['body_face_indices']}
assert len(target_indices)==mapping['replaced_body_faces']==3203
assert all(bm.faces[i].material_index==1 for i in target_indices)
bmesh.ops.delete(bm,geom=[bm.faces[i] for i in target_indices],context='FACES')
bm.to_mesh(body.data);bm.free();body.data.update()
assert len(body.data.polygons)==original_faces-3203

scene['body_opening_replacement_version']='v005'
scene['body_opening_count']=len(placed)
scene['body_plane_faces_removed']=3203
scene['orientation_rule']='local -Y (frame) outward; local +Y (glass) inward'
scene['status']='ALL_ID2_PLANES_REPLACED; 89 SCALED MATCHES NEED VISUAL REVIEW'
body['plane_replacement']='ID 2 window planes removed and replaced with separate two-ID meshes'
note=bpy.data.texts.new('BODY_OPENINGS_README_RU')
note.write('На копии autosave заменены все 285 плоскостей материала «2 окна».\n')
note.write('Плоскости удалены из body; экструзия проёмов и другие ID сохранены.\n')
note.write('Рама локально в y=0, стекло утоплено на 30 мм по +Y; локальная -Y совпадает с наружной нормалью плейна.\n')
note.write('169 типов подтверждены также соседним размещением FBX, 27 близки по размеру, 89 масштабированы и требуют визуальной сверки.\n')
note.write('Исходный FBX скрыт как справочный; исходный autosave скопирован отдельно и не менялся.\n')

for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.shading.color_type='MATERIAL'
            space.region_3d.view_location=Vector((0,0,10))
            space.region_3d.view_distance=115
            space.region_3d.view_rotation=Vector((.7,-.8,.5)).to_track_quat('Z','Y')
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active=body
body.select_set(True)
path=OUT/'SOSH1150_Body_Openings_Replaced_v005.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
print(json.dumps({'blend':str(path),'body_faces_before':original_faces,
    'body_faces_after':len(body.data.polygons),'frames':len(placed),
    'review_frames':len(review.objects)},ensure_ascii=False))

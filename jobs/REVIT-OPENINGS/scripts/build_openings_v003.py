"""Build editable all-quad facade skins from the measured v003 type map."""
import bpy
import json
import math
from pathlib import Path

from mathutils import Vector

OUT = Path('C:/Users/artsafro/.AGR_Project/jobs/REVIT-OPENINGS/outputs/openings-v003')
type_map = json.loads((OUT/'type-map.json').read_text(encoding='utf-8'))
primary_specs = type_map['types']
specs = primary_specs + type_map['size_variants']


def skin(s):
    w, h = s['width_m'], s['height_m']
    boxes = s['panes_m']
    xs = sorted(set([0, w] + [q[k] for q in boxes for k in (0, 2)]))
    zs = sorted(set([0, h] + [q[k] for q in boxes for k in (1, 3)]))
    vertices, faces, ids, lookup, levels = [], [], [], {}, {}

    def vertex(x, y, z):
        key = tuple(round(float(v), 6) for v in (x, y, z))
        if key not in lookup:
            lookup[key] = len(vertices)
            vertices.append(key)
        return lookup[key]

    for i in range(len(xs)-1):
        for j in range(len(zs)-1):
            cx, cz = (xs[i]+xs[i+1])/2, (zs[j]+zs[j+1])/2
            recessed = any(a < cx < c and b < cz < d for a,b,c,d in boxes)
            y = .03 if recessed else 0
            levels[i,j] = y
            faces.append([vertex(xs[i],y,zs[j]),vertex(xs[i+1],y,zs[j]),
                          vertex(xs[i+1],y,zs[j+1]),vertex(xs[i],y,zs[j+1])])
            ids.append(1 if recessed else 0)
    for (i,j),y in levels.items():
        if y:
            continue
        edges = [((i,j-1), ((xs[i],zs[j]),(xs[i+1],zs[j]))),
                 ((i+1,j), ((xs[i+1],zs[j]),(xs[i+1],zs[j+1]))),
                 ((i,j+1), ((xs[i+1],zs[j+1]),(xs[i],zs[j+1]))),
                 ((i-1,j), ((xs[i],zs[j+1]),(xs[i],zs[j])))]
        for neighbor,(a,b) in edges:
            yy = levels.get(neighbor, 0)
            if yy:
                faces.append([vertex(b[0],0,b[1]),vertex(a[0],0,a[1]),
                              vertex(a[0],yy,a[1]),vertex(b[0],yy,b[1])])
                ids.append(0)
    return vertices,faces,ids


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = 'SOSH1150_OPENINGS_v003'
scene.unit_settings.system = 'METRIC'
models = bpy.data.collections.new('OPENING_TYPES')
scene.collection.children.link(models)
labels = bpy.data.collections.new('LABELS_FOR_PREVIEW')
scene.collection.children.link(labels)
frame = bpy.data.materials.new('ID01_FRAME_F11_RAL7016')
frame.diffuse_color = (.065,.080,.092,1)
glass = bpy.data.materials.new('ID02_GLASS_PENDING')
glass.diffuse_color = (.66,.78,.83,1)
opaque = bpy.data.materials.new('ID02_OPAQUE_LEAF_PENDING')
opaque.diffuse_color = (.42,.46,.49,1)
for mat in (frame,glass,opaque):
    mat['preview_only'] = True
    mat['source_register'] = 'SOSH1150_Material_Register_v001.docx'

for index,s in enumerate(specs):
    if index < len(primary_specs):
        row_x = (index % 3) * 6.5
        row_z = -(index // 3) * 5.0
    else:
        row_x = 30 + (index-len(primary_specs))*6.5
        row_z = 0
    verts,faces,ids = skin(s)
    mesh = bpy.data.meshes.new(s['id'])
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    mesh.materials.append(frame)
    mesh.materials.append(opaque if s['infill']=='opaque_leaf' else glass)
    attr = mesh.attributes.new('Material_ID','INT','FACE')
    for polygon,mi,datum in zip(mesh.polygons,ids,attr.data):
        polygon.material_index = mi
        datum.value = mi+1
    uv=mesh.uv_layers.new(name='Physical_UV_m')
    for polygon in mesh.polygons:
        axis=max(range(3),key=lambda a:abs(polygon.normal[a]))
        plane=[a for a in range(3) if a!=axis]
        for loop_index in polygon.loop_indices:
            co=mesh.vertices[mesh.loops[loop_index].vertex_index].co
            uv.data[loop_index].uv=(co[plane[0]],co[plane[1]])
    ob=bpy.data.objects.new(s['id']+'_'+s['role'].upper(),mesh)
    models.objects.link(ob)
    ob.location=(row_x,0,row_z)
    ob['FBX_type']=s['source']
    ob['FBX_merged_types']=','.join(s['merged_sources'])
    ob['FBX_represented_occurrences']=s['represented_occurrences']
    ob['PDF_pages']=','.join(map(str,s['pdf_pages']))
    ob['matching_evidence']=s['match']
    ob['facade_finish']=s['frame_finish']
    ob['topology']='single quad front skin; open exterior perimeter intentional'
    ob['materials']='two local IDs: 1 frame, 2 infill'
    ob['hardware']='omitted'
    ob.asset_mark()
    ob.asset_data.description='Simplified school facade opening. Measured FBX source and PDF comparison in type-map.json.'
    if index < len(primary_specs):
        font=bpy.data.curves.new(s['id']+'_LABEL','FONT')
        font.body=f"{s['id']}   {s['width_m']:.2f} x {s['height_m']:.2f} m   {s['source']}"
        font.size=.13
        font.materials.append(frame)
        label=bpy.data.objects.new(s['id']+'_LABEL',font)
        labels.objects.link(label)
        label.rotation_euler=(math.pi/2,0,0)
        label.location=(row_x,-.01,row_z-.28)

scene['source']='FBX Revit live scene snapshot; PDF 18-21; visualizations'
scene['type_map']=str(OUT/'type-map.json')
scene['status']='ELEVEN_VISUAL_FAMILIES_17_SIZE_MODELS; VISUAL_ACCEPTANCE_PENDING'
readme=bpy.data.texts.new('README_RU')
readme.write('СОШ1150: 11 визуальных семейств и 6 отдельных размерных версий, всего 17 моделей.\n')
readme.write('В каждом объекте 2 локальных ID: рама и заполнение.\n')
readme.write('Все поверхности — квады, заполнения утоплены на 30 мм; внешний контур намеренно открыт.\n')
readme.write('Без ручек, доводчиков, диагональных обозначений открывания и наружных цветных кассет.\n')
readme.write('Заглубление 30 мм — упрощение формы, не проектная глубина посадки в стену.\n')
readme.write('W01 проверен по пикселям PDF18 и габаритам FBX; остальные сопоставлены визуально.\n')
readme.write('W01_H/W02_H/W03_H выше на 300 мм; W01_N/W04_N/D03_W имеют другие ширины.\n')
readme.write('D04: глухое полотно по FBX, находится вне подтверждённой фасадной типологии PDF.\n')
readme.write('Рама F11/RAL7016 для остеклённых типов; прозрачное стекло отдельный материал пока без F-ID.\n')
readme.write('Файл исходного Revit не изменён.\n')

scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=2400
scene.render.resolution_y=1450
scene.render.resolution_percentage=100
scene.display.shading.light='STUDIO'
scene.display.shading.color_type='MATERIAL'
scene.display.shading.show_shadows=False
scene.display.shading.show_cavity=True
scene.display.shading.cavity_type='BOTH'
world=bpy.data.worlds.new('PreviewWorld')
scene.world=world
scene.display.shading.background_type='WORLD'
world.color=(.78,.79,.8)
camera_data=bpy.data.cameras.new('GalleryCamera')
camera=bpy.data.objects.new('GalleryCamera',camera_data)
scene.collection.objects.link(camera)
scene.camera=camera
camera_data.type='ORTHO'
camera_data.ortho_scale=31
center=Vector((9.25,0,-6.0))
camera.location=center+Vector((0,-20,0))
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.shading.color_type='MATERIAL'
            space.region_3d.view_rotation=camera.rotation_euler.to_quaternion()
            space.region_3d.view_location=center
            space.region_3d.view_distance=17
            space.region_3d.view_perspective='ORTHO'
for ob in models.objects:
    ob.select_set(True)
bpy.context.view_layer.objects.active=models.objects[0]
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'SOSH1150_Openings_v003.blend'))
scene.render.filepath=str(OUT/'blender-gallery.png')
bpy.ops.render.render(write_still=True)
print(json.dumps({'objects':len(specs),'quads':sum(len(skin(s)[1]) for s in specs)}))

import bpy, bmesh, math, json
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/v001'
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'MILLIMETERS'
signs = bpy.data.collections.new('Facade signs | 30 mm')
scene.collection.children.link(signs)

def material(name, color):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = .6
    p.inputs['Specular IOR Level'].default_value = .1
    return m

white = material('White sign', (.88,.88,.88))
black = material('Black numerals', (.009,.011,.014))

def quad_fill(poly):
    points, faces, lookup = [], [], {}
    def idx(p):
        key = tuple(round(float(c),9) for c in p)
        if key not in lookup:
            lookup[key] = len(points)
            points.append(key)
        return lookup[key]
    for tri in tessellate_polygon([[Vector((x,z,0)) for x,z in poly]]):
        a,b,c = [Vector(poly[p]) if isinstance(p,int) else Vector((p.x,p.y)) for p in tri]
        center = (a+b+c)/3
        for v,n,p in [(a,b,c),(b,c,a),(c,a,b)]:
            faces.append([idx(q) for q in (v,(v+n)/2,center,(p+v)/2)])
    return points,faces

def solid(name, points, faces, mat, offset=0):
    count = len(points)
    verts = [(x+offset,y,z) for y in (0,-.03) for x,z in points]
    all_faces = [tuple(reversed(f)) for f in faces] + [tuple(i+count for i in f) for f in faces]
    edges = {}
    for f in faces:
        for a,b in zip(f, f[1:]+f[:1]):
            key = tuple(sorted((a,b)))
            edges.setdefault(key,[]).append((a,b))
    for occurrences in edges.values():
        if len(occurrences)==1:
            a,b = occurrences[0]
            all_faces.append((a,b,b+count,a+count))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],all_faces)
    mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    ob = bpy.data.objects.new(name,mesh); signs.objects.link(ob)
    mesh.materials.append(mat)
    ob['thickness_mm'] = 30
    ob['source'] = 'inputs/reference.png; silhouette traced from raster'
    return ob

# The supplied white silhouette: straight 400 mm stem and a 300 mm semicircle.
poly = [(0,0),(.4,0),(.4,.34)]
poly += [(.4+.3*math.cos(-math.pi/2+i*math.pi/40), .64+.3*math.sin(-math.pi/2+i*math.pi/40)) for i in range(1,41)]
poly += [(0,.94)]
solid('Sign_white_700x940',*quad_fill(poly),white)

# Right sign uses separate horizontal/vertical drawing scales, anchored to 600x1000 mm.
def drawing_point(x,y):
    return ((x-1198)/46*.6,(316-y)/82)
one = [drawing_point(x,y) for x,y in [(1198,242),(1203,234),(1218,234),(1218,316),(1210,316),(1210,242)]]
solid('Number_1',*quad_fill(one),black,1.3)
for row, cy in enumerate((244,262)):
    for col,cx in enumerate((1226.5,1234,1241.5)):
        pts=[]
        for rx,ry in ((2.5,5),(1.15,3.5)):
            for i in range(32):
                t=i*2*math.pi/32
                pts.append(drawing_point(cx+rx*math.cos(t),cy+ry*math.sin(t)))
        faces=[(i,(i+1)%32,(i+1)%32+32,i+32) for i in range(32)]
        solid('Zero_%d_%d'%(row+1,col+1),pts,faces,black,1.3)

im = bpy.data.images.load(str(ROOT/'inputs/reference.png')); im.pack(); im.use_fake_user=True
notes = bpy.data.texts.new('README_RU')
notes.write('Фасадные знаки по единственному растровому референсу. Белый: 700×940 мм. Правая композиция: 600×1000 мм. Толщина обоих 30 мм подтверждена пользователем. Мелкие нули и радиус обведены/аппроксимированы по пикселям, не являются подтверждённым шрифтом или заводским чертежом. Расстояние между знаками демонстрационное. Монтажные высоты не восстановлены. Исходник упакован в blend. Визуальная приёмка открыта.')

def aim(ob,target):
    ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(.95,-5,.5))
camera=bpy.context.object; camera.name='Front'; aim(camera,(.95,0,.5))
camera.data.type='ORTHO'; camera.data.ortho_scale=2.45; scene.camera=camera
for loc,power,size in [((-.7,-3,3),700,4),((3,-2,1),350,3)]:
    bpy.ops.object.light_add(type='AREA',location=loc)
    ob=bpy.context.object; ob.data.energy=power; ob.data.shape='DISK'; ob.data.size=size; aim(ob,(.95,0,.5))
scene.world=bpy.data.worlds.new('Preview world')
scene.world.color=(.18,.18,.18)
scene.render.engine='CYCLES'; scene.cycles.samples=32
scene.render.resolution_x=1400; scene.render.resolution_y=850; scene.render.resolution_percentage=100
scene.view_settings.view_transform='Standard'
scene.render.image_settings.file_format='PNG'
scene.render.film_transparent=False
for ob in bpy.context.selected_objects: ob.select_set(False)
for ob in signs.objects: ob.select_set(True)
bpy.context.view_layer.objects.active=signs.objects[0]
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.shading.color_type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'facade_signs_v001.blend'))
scene.render.filepath=str(OUT/'preview.png')
bpy.ops.render.render(write_still=True)
print('SIGNS_BUILD_OK')

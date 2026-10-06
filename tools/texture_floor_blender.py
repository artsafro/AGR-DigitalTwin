"""Apply baked diffuse maps, preserve geometry/UV/instances, reopen and verify."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


root = Path(sys.argv[sys.argv.index('--')+1]).resolve()
out = root/'textured_v010'
recipe = json.loads((out/'texture-recipe.json').read_text(encoding='utf-8'))


def snapshot():
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    result = {}
    for obj in objects:
        mesh = obj.data
        result[obj.name] = {
            'mesh': mesh.name, 'matrix': [list(r) for r in obj.matrix_world],
            'vertices': [list(v.co) for v in mesh.vertices],
            'faces': [list(f.vertices) for f in mesh.polygons],
            'finish_ids': [v.value for v in mesh.attributes['finish_id'].data],
            'uv': {l.name: [list(v.uv) for v in l.data] for l in mesh.uv_layers},
            'slots': [p.material_index for p in mesh.polygons],
        }
    return result


def render(scene, camera, name, width=1600, height=1100):
    scene.camera = camera
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(out/name)
    bpy.ops.render.render(write_still=True)


reports = {}
for variant in ('NPM_ATLAS', 'VPM_UDIM'):
    source = root/'uv_trial'/f'OBR22_K02_v009_{variant}.blend'
    bpy.ops.wm.open_mainfile(filepath=str(source))
    original = snapshot()
    mat = bpy.data.meshes['BODY'].materials[0]
    tex = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
    im = bpy.data.images.load(str(out/f'{variant}_Diffuse.1001.png'), check_existing=False)
    tiles = recipe['variants'][variant]['tiles']
    if variant == 'VPM_UDIM':
        im.source = 'TILED'
        im.filepath = str(out/f'{variant}_Diffuse.<UDIM>.png')
        for tile in tiles[1:]:
            im.tiles.new(tile)
        im.reload()
    im.colorspace_settings.name = 'sRGB'
    tex.image = im
    mat.name = variant+'_PROCEDURAL_DIFFUSE_v010'
    mat.node_tree.nodes.active = tex
    mat['status'] = 'Procedural finish preview; no measured PBR maps'
    scene = bpy.context.scene
    scene['status'] = recipe['recipe']['limits']
    scene['texture_recipe'] = json.dumps(recipe['recipe'], ensure_ascii=False)
    bpy.data.texts.new('TEXTURE_RECIPE.json').write(json.dumps(recipe, ensure_ascii=False, indent=2))
    scene.display.shading.color_type = 'TEXTURE'
    scene.display.shading.light = 'FLAT'
    scene.camera = bpy.data.objects['Наружная_оболочка']
    im.filepath = '//'+Path(im.filepath).name
    target = out/f'OBR22_K02_v010_{variant}.blend'
    # Set the new base path before resolving relative texture names.
    bpy.ops.wm.save_as_mainfile(filepath=str(target), relative_remap=False)
    bpy.ops.wm.open_mainfile(filepath=str(target))
    assert snapshot() == original, 'Geometry, UV, IDs, instances or slots changed'
    mat = bpy.data.meshes['BODY'].materials[0]
    node = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
    assert Path(bpy.path.abspath(node.image.filepath)).parent == out
    assert [t.number for t in node.image.tiles] == tiles
    assert any(l.from_node == node and l.to_socket.name == 'Base Color' for l in mat.node_tree.links)
    node.image.reload()
    scene = bpy.context.scene
    reports[variant] = {
        'reopened_geometry_uv_ids_instances_unchanged': True,
        'mesh_objects': len(original), 'unique_meshes': len({r['mesh'] for r in original.values()}),
        'image_tiles': tiles, 'image_path': node.image.filepath,
        'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    render(scene, bpy.data.objects['Наружная_оболочка'], variant+'_overview.png', 2000, 1100)
    render(scene, bpy.data.objects['Сетка_наружного_проёма'], variant+'_brick.png')
    # Place an inspection camera against a large facade quad of each tile finish.
    body = next(o for o in scene.objects if o.type == 'MESH' and o.data.name == 'BODY')
    for ident, label in ((2, 'light_tile'), (4, 'gray_tile')):
        candidates = [p for p in body.data.polygons if body.data.attributes['finish_id'].data[p.index].value == ident and abs(p.normal.z) < .1]
        face = max(candidates, key=lambda p: p.area)
        center = body.matrix_world @ face.center
        normal = (body.matrix_world.to_3x3() @ face.normal).normalized()
        data = bpy.data.cameras.new('Inspect_'+label)
        cam = bpy.data.objects.new('Inspect_'+label, data)
        scene.collection.objects.link(cam)
        cam.location = center + normal*7 + Vector((0, 0, .5))
        cam.rotation_euler = (center-cam.location).to_track_quat('-Z', 'Y').to_euler()
        data.type = 'ORTHO'
        data.ortho_scale = 4.5
        render(scene, cam, variant+'_'+label+'.png')
    print('TEXTURE_READBACK_OK', variant, flush=True)

(out/'texture-blender-qa.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')

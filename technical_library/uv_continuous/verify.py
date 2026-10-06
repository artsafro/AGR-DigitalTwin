
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import arguments, require_stage, mark_stage, run_dcc
"""Scoped SOSH1150 v006 stage; see README and replay evidence."""

def readback_v006(root):
    import bpy, json, hashlib, math
    from pathlib import Path
    from collections import Counter
    from mathutils import Vector
    from mathutils.geometry import closest_point_on_tri
    bpy.ops.wm.open_mainfile(filepath=str(root / 'walls_UV550-1500_FlipH_v006.blend'))
    o = next((o for o in bpy.context.scene.objects if o.type == 'MESH'))
    m = o.data
    m.calc_loop_triangles()
    layer = m.uv_layers.active.data
    td = []
    bounds = []
    area = 0
    pa = [0.0] * len(m.polygons)
    pu = [0.0] * len(m.polygons)
    for tri in m.loop_triangles:
        q = [o.matrix_world @ m.vertices[i].co for i in tri.vertices]
        a = (q[1] - q[0]).cross(q[2] - q[0]).length / 2
        u = [layer[i].uv for i in tri.loops]
        b = abs((u[1] - u[0]).cross(u[2] - u[0])) / 2
        if a > 1e-14:
            td.append(4096 * math.sqrt(b / a))
        pa[tri.polygon_index] += a
        pu[tri.polygon_index] += b
        area += a
    for x in layer:
        bounds.extend(x.uv)
    edges = Counter((tuple(sorted((a, b))) for p in m.polygons for a, b in zip(p.vertices, list(p.vertices[1:]) + [p.vertices[0]])))
    img = next((n.image for n in m.materials[0].node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and ('Diffuse' in n.image.name)))
    expected = hashlib.sha256((root / 'T_Template_Address_001_Diffuse_FlipH_v005.1001.png').read_bytes()).hexdigest()
    source = json.loads((root / 'source.json').read_text())
    points = [o.matrix_world @ v.co for v in m.vertices]
    maxerr = 0
    source_tris = {}
    for tri in source['triangles']:
        source_tris.setdefault(tri['face'], []).append([Vector(source['vertices'][i]) for i in tri['vertices']])
    for p in m.polygons:
        sf = source['faces'][m.attributes['source_face'].data[p.index].value]
        q = [Vector(source['vertices'][i]) for i in sf]
        triangles = source_tris[m.attributes['source_face'].data[p.index].value]
        maxerr = max(maxerr, max((min(((points[i] - closest_point_on_tri(points[i], *tri)).length for tri in triangles)) for i in p.vertices)))
    rep = {'file': bpy.data.filepath, 'faces': len(m.polygons), 'polygon_sizes': dict(Counter((len(p.vertices) for p in m.polygons))), 'density_min_max': [min(td), max(td)], 'td_outside_550_1500': sum((x < 550 or x > 1500 for x in td)), 'uv_bounds': [min(bounds), max(bounds)], 'outside_1001': sum((x < 0 or x > 1 for x in bounds)), 'surface_area_m2': area, 'edge_counts': dict(Counter(edges.values())), 'nonmanifold_gt2': sum((x > 2 for x in edges.values())), 'mesh_validate_repairs': m.validate(verbose=False), 'packed_diffuse_matches': hashlib.sha256(img.packed_file.data).hexdigest() == expected, 'source_plane_error_m': maxerr, 'delivery_passed': False}
    polytd = [4096 * math.sqrt(u / a) for u, a in zip(pu, pa) if a > 1e-14]
    rep.pop('source_plane_error_m')
    rep['source_surface_distance_m'] = maxerr
    rep['face_density_min_max'] = [min(polytd), max(polytd)]
    rep['loose_vertices'] = len(m.vertices) - len({i for p in m.polygons for i in p.vertices})
    phase_edges = {}
    phase_residual = []
    phase_failures = []
    for p in m.polygons:
        parent = m.attributes['source_face'].data[p.index].value
        if abs(source['normals'][parent][2]) > 0.001:
            continue
        loops = list(p.loop_indices)
        for la, lb in zip(loops, loops[1:] + loops[:1]):
            va, vb = (m.loops[la].vertex_index, m.loops[lb].vertex_index)
            key = tuple(sorted((va, vb)))
            vals = {va: layer[la].uv.copy(), vb: layer[lb].uv.copy()}
            if key in phase_edges:
                prev, prevparent = phase_edges[key]
                for vi in key:
                    diff = (vals[vi] - prev[vi]) * (4096 / 4056)
                    phase_residual.append(max((abs(x - round(x)) for x in diff)) * 4056)
                    if phase_residual[-1] > 0.1:
                        phase_failures.append({'parents': [prevparent, parent], 'edge': key, 'point': list(points[vi]), 'residual_px': phase_residual[-1]})
            else:
                phase_edges[key] = (vals, parent)
    rep['vertical_shared_edge_sample_max_phase_px'] = max(phase_residual)
    rep['vertical_shared_edge_samples'] = len(phase_residual)
    rep['vertical_phase_samples_over_0_1px'] = sum((x > 0.1 for x in phase_residual))
    (root / 'phase-failures-v006.json').write_text(json.dumps(phase_failures, indent=2))
    (root / 'readback_v006.json').write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep))

def export_max_v006(root):
    """Export the saved wall version in an isolated Blender process and reimport."""
    import bpy, json, hashlib, shutil
    import numpy as np
    from pathlib import Path
    from collections import Counter
    out = root / 'FBX_For_Max_v006'
    out.mkdir(exist_ok=True)
    source = root / 'walls_UV550-1500_FlipH_v006.blend'
    png = out / 'Walls_FlipH_v006_Diffuse.png'
    shutil.copy2(root / 'T_Template_Address_001_Diffuse_FlipH_v005.1001.png', png)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    assert len(objects) == 1
    obj = objects[0]
    obj.name = 'Walls_FlipH_v006'
    mat = bpy.data.materials.new('Walls_FlipH_v006_Diffuse')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value = 0.85
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(png), check_existing=False)
    tex.extension = 'REPEAT'
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    obj.data.uv_layers.active_index = 0
    obj.data.uv_layers[0].active_render = True

    def capture(o):
        m = o.data
        return {'vertices': np.array([o.matrix_world @ v.co for v in m.vertices]), 'faces': [list(p.vertices) for p in m.polygons], 'uv': np.array([x.uv[:] for x in m.uv_layers.active.data]), 'material_ids': [p.material_index for p in m.polygons]}
    before = capture(obj)
    for o in bpy.context.scene.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    fbx = out / 'Walls_FlipH_v006.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'MESH'}, global_scale=1, apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z', use_mesh_modifiers=False, use_triangles=False, mesh_smooth_type='FACE', bake_anim=False, add_leaf_bones=False, path_mode='COPY', embed_textures=True, bake_space_transform=False)
    from io_scene_fbx import parse_fbx as parse
    tree, version = parse.parse(str(fbx))
    embedded = []

    def walk(e):
        if e.id == b'Content':
            for value in e.props:
                if isinstance(value, bytes) and value:
                    embedded.append(value)
        for child in e.elems:
            walk(child)
    walk(tree)
    image_hash = hashlib.sha256(png.read_bytes()).hexdigest()
    assert any((hashlib.sha256(x).hexdigest() == image_hash for x in embedded)), 'Diffuse not embedded'
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), use_image_search=True)
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    assert len(objects) == 1
    imported = objects[0]
    after = capture(imported)
    assert before['faces'] == after['faces'], 'Topology changed in FBX roundtrip'
    assert before['material_ids'] == after['material_ids']
    uv_error = float(abs(before['uv'] - after['uv']).max())
    world_error = float(abs(before['vertices'] - after['vertices']).max())
    assert uv_error < 1e-06 and world_error < 0.0001
    bound = after['vertices'].max(0) - after['vertices'].min(0)
    assert len(imported.data.uv_layers) == 1
    imported_images = [n.image for m in imported.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
    assert imported_images, 'FBX material did not retain the diffuse'
    assert any((hashlib.sha256(Path(bpy.path.abspath(i.filepath)).read_bytes()).hexdigest() == image_hash for i in imported_images if Path(bpy.path.abspath(i.filepath)).exists()))
    report = {'source': str(source), 'fbx': str(fbx), 'fbx_version': version, 'objects': 1, 'vertices': len(imported.data.vertices), 'polygon_sizes': dict(Counter((len(p.vertices) for p in imported.data.polygons))), 'uv_channels': len(imported.data.uv_layers), 'uv_max_error': uv_error, 'world_max_error_m': world_error, 'dimensions_m': bound.tolist(), 'material_slots': len(imported.data.materials), 'embedded_diffuse_sha256': image_hash, 'embedded_diffuse_verified': True, 'diffuse_material_binding_verified': True, 'mesh_validate_repairs': imported.data.validate(verbose=False), 'blender_fbx_roundtrip_passed': True, 'native_max_import_verified': False}
    (out / 'FBX_READBACK.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    assert not report['mesh_validate_repairs']
    print(json.dumps(report))

def package_max_v006(root):
    import hashlib, json, zipfile
    from pathlib import Path
    folder = root / 'FBX_For_Max_v006'
    target = root / 'Walls_FlipH_v006_FBX_For_Max.zip'
    names = ['Walls_FlipH_v006.fbx', 'Walls_FlipH_v006_Diffuse.png', 'README.txt', 'FBX_READBACK.json']
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.write(folder / name, arcname=name)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert sorted(archive.namelist()) == sorted(names)
        for name in names:
            assert archive.read(name) == (folder / name).read_bytes()
    rep = {'zip': str(target), 'archive_readback_verified': True, 'files': {n: {'bytes': (folder / n).stat().st_size, 'sha256': hashlib.sha256((folder / n).read_bytes()).hexdigest()} for n in names}}
    (folder / 'PACKAGE_QA.json').write_text(json.dumps(rep, indent=2))
    print(json.dumps({'zip': str(target), 'bytes': target.stat().st_size, 'files': names, 'readback': True}))


def main():
    import json
    args = arguments()
    root = require_stage(args.output, 'build')
    if args.phase == 'dcc':
        readback_v006(root)
        export_max_v006(root)
        return
    run_dcc(Path(__file__), root, args.blender)
    report = json.loads((root / 'readback_v006.json').read_text())
    assert report['polygon_sizes'] == {'4': 42686}
    assert report['outside_1001'] == 0
    assert report['td_outside_550_1500'] == 0
    assert report['vertical_phase_samples_over_0_1px'] == 0
    assert not report['mesh_validate_repairs']
    assert report['packed_diffuse_matches']
    assert report['source_surface_distance_m'] < 0.0002
    (root / 'FBX_For_Max_v006/README.txt').write_text(
        'Blender FBX roundtrip verified; native Max and full AGR remain unverified. Units: metres.\n')
    package_max_v006(root)
    mark_stage(root, 'verify')
    print('Stage 4/4: scoped checks passed; native Max/full AGR unverified')


if __name__ == '__main__':
    main()

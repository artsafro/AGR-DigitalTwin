"""Blender --background --factory-startup --disable-autoexec --python this.py -- ABS_CONFIG.json.

Config: operation=inspect|export, source_blend, output_dir, atlas, optional mesh_names.
Existing outputs are refused. Save editable copy before export-only triangulation.
"""
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from profile_snapshot_common import absolute, digest, image_facts, request, snapshot, used_images, write


def main(config):
    source = absolute(config['source_blend'])
    output = absolute(config['output_dir'])
    atlas = absolute(config['atlas'])
    operation = config.get('operation', 'inspect')
    if operation not in ('inspect', 'export'):
        raise ValueError('operation must be inspect or export')
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / ('source-snapshot.json' if operation == 'inspect' else 'export-manifest.json')
    if result_path.exists():
        raise FileExistsError(result_path)
    before = {'source': digest(source), 'atlas': digest(atlas)}
    result = {'operation': operation, 'source_blend': str(source), 'source_sha256': before['source'],
              'atlas': str(atlas), 'atlas_sha256': before['atlas'], 'delivery_passed': False,
              'failures': [], 'limitations': ['Full AGR Checker, overlap intersections, Max transfer and visual acceptance are separate gates',
                                              'FBX does not carry generic polygon finish_id; material surface semantics are compared']}
    try:
        bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False)
        meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
        names = config.get('mesh_names')
        if names is not None:
            if not names or len(names) != len(set(names)):
                raise ValueError('mesh_names must be a nonempty unique list')
            by_name = {obj.name: obj for obj in meshes}
            objects = [by_name[name] for name in names]
        else:
            objects = sorted(meshes, key=lambda obj: obj.name)
        if not objects:
            raise ValueError('No selected source meshes')
        result['selection_basis'] = 'explicit mesh_names' if names is not None else 'all source scene MESH objects; preflight inventory requires review'
        result['selected_mesh_names'] = [obj.name for obj in objects]
        result['excluded_objects'] = [{'name': obj.name, 'type': obj.type, 'reason': 'outside selected mesh scope'} for obj in bpy.context.scene.objects if obj not in objects]
        result['native_source'] = snapshot(objects)
        maps = result['native_source']['images']
        if any(not (im['external_sha256'] or im['packed_sha256']) for im in maps):
            raise ValueError('Selected materials contain unavailable image dependencies')
        if not any(before['atlas'] in (im['external_sha256'], im['packed_sha256']) for im in maps):
            raise ValueError('Configured atlas is absent from selected source materials')
        if operation == 'export':
            blend = output / 'working-copy.blend'
            fbx = output / 'technical.fbx'
            atlas_copy = output / atlas.name
            if any(path.exists() for path in (blend, fbx, atlas_copy)):
                raise FileExistsError('Refusing existing export artifacts')
            # Preserve exact image bytes. Only the isolated editable copy gets new image paths.
            shutil.copyfile(atlas, atlas_copy)
            for image in used_images(objects):
                facts = image_facts([image])[0]
                if before['atlas'] in (facts['external_sha256'], facts['packed_sha256']):
                    image.filepath = str(atlas_copy)
            bpy.ops.wm.save_as_mainfile(filepath=str(blend), relative_remap=False)
            depsgraph = bpy.context.evaluated_depsgraph_get()
            export_objects = []
            # The saved editable copy retains source quads, modifiers and instances.
            # Detach evaluated meshes and use calc_loop_triangles explicitly to freeze diagonals.
            for obj in objects:
                evaluated = obj.evaluated_get(depsgraph)
                mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
                mesh.calc_loop_triangles()
                tri_mesh = bpy.data.meshes.new(obj.data.name + '_EXPORT_TRI')
                tri_mesh.from_pydata([v.co[:] for v in mesh.vertices], [], [tri.vertices[:] for tri in mesh.loop_triangles])
                for material in mesh.materials:
                    tri_mesh.materials.append(material)
                for layer in mesh.uv_layers:
                    dest = tri_mesh.uv_layers.new(name=layer.name)
                    for polygon, tri in zip(tri_mesh.polygons, mesh.loop_triangles):
                        for new_loop, old_loop in zip(polygon.loop_indices, tri.loops):
                            dest.data[new_loop].uv = layer.data[old_loop].uv
                    dest.active_render = layer.active_render
                if mesh.uv_layers.active:
                    tri_mesh.uv_layers.active_index = mesh.uv_layers.active_index
                for polygon, tri in zip(tri_mesh.polygons, mesh.loop_triangles):
                    polygon.material_index = mesh.polygons[tri.polygon_index].material_index
                obj.data = tri_mesh
                obj.modifiers.clear()
                export_objects.append(obj)
            bpy.ops.object.select_all(action='DESELECT')
            for obj in export_objects:
                obj.hide_set(False)
                obj.hide_viewport = False
                obj.select_set(True)
            bpy.context.view_layer.objects.active = export_objects[0]
            result['export_reference'] = snapshot(export_objects)
            options = dict(use_selection=True, object_types={'MESH'}, axis_forward='-Y', axis_up='Z',
                           apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', bake_anim=False,
                           use_mesh_modifiers=False, path_mode='COPY', embed_textures=True,
                           add_leaf_bones=False, use_triangles=True)
            bpy.ops.export_scene.fbx(filepath=str(fbx), **options)
            result['export_options'] = {key: sorted(value) if isinstance(value, set) else value for key, value in options.items()}
            result['artifacts'] = {path.name: {'sha256': digest(path), 'bytes': path.stat().st_size} for path in (blend, fbx, atlas_copy)}
    except Exception as exc:
        result['failures'].append(type(exc).__name__ + ': ' + str(exc))
    result['source_unchanged'] = digest(source) == before['source'] and digest(atlas) == before['atlas']
    if not result['source_unchanged']:
        result['failures'].append('Approved source/atlas hash changed')
    result['operation_passed'] = not result['failures']
    write(result_path, result)
    print('SNAPSHOT', operation, 'OK' if result['operation_passed'] else 'FAILED', str(result_path), flush=True)
    if result['failures']:
        raise RuntimeError('; '.join(result['failures']))


if __name__ == '__main__':
    main(request())

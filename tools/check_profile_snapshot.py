"""Actual FBX import: config contains absolute fbx, reference (export JSON), result paths.

Embedding is independently checked by importing an FBX-only temporary directory.
The requested extracted/package FBX is then imported for actual readback evidence.
"""
from pathlib import Path
import shutil
import struct
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
import json
from profile_snapshot_common import (BUDGET_BASIS, NUMERICAL_BUDGET, absolute,
                                     compare_triangles, digest, request, snapshot, write)


def import_snapshot(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.ops.import_scene.fbx(filepath=str(path), use_image_search=False)
    return snapshot(sorted((obj for obj in bpy.context.scene.objects if obj.type == 'MESH'), key=lambda obj: obj.name))


def main(config):
    fbx = absolute(config['fbx'])
    reference_path = absolute(config['reference'])
    output = absolute(config['result'])
    if output.exists():
        raise FileExistsError(output)
    reference = json.loads(reference_path.read_text(encoding='utf-8'))
    report = {'operation': 'actual_fbx_readback', 'fbx': str(fbx), 'fbx_sha256': digest(fbx),
              'reference': str(reference_path), 'reference_sha256': digest(reference_path),
              'numerical_budget': NUMERICAL_BUDGET, 'numerical_budget_basis': BUDGET_BASIS,
              'delivery_passed': False, 'failures': [], 'checks': {},
              'limitations': reference.get('limitations', []) + [
                  'FBX UnitScaleFactor metadata is unverified; import harness uses METRIC scale 1 and world-coordinate comparison checks physical output scale']}
    def check(name, condition):
        report['checks'][name] = bool(condition)
        if not condition:
            report['failures'].append(name)
    try:
        check('export_reference_passed', reference.get('operation_passed') is True)
        check('fbx_hash_matches_export', report['fbx_sha256'] == reference['artifacts']['technical.fbx']['sha256'])
        with fbx.open('rb') as stream:
            header = stream.read(27)
        check('binary_fbx_7400', header[:23] == b'Kaydara FBX Binary  \x00\x1a\x00' and len(header) == 27 and struct.unpack('<I', header[23:])[0] == 7400)
        # No PNG accompanies this FBX: retrieved atlas bytes prove embedding.
        with tempfile.TemporaryDirectory(prefix='dt-embedded-only-') as tmp:
            isolated = Path(tmp) / 'technical.fbx'
            shutil.copyfile(fbx, isolated)
            embedded = import_snapshot(isolated)
            report['embedded_only_images'] = embedded['images']
            check('embedded_atlas_sha_matches', any(
                reference['atlas_sha256'] == im['packed_sha256'] or
                (reference['atlas_sha256'] == im['external_sha256'] and Path(im['path']).resolve().is_relative_to(Path(tmp).resolve()))
                for im in embedded['images']))
        actual = import_snapshot(fbx)
        report['actual_native_readback'] = actual
        expected = reference['export_reference']
        by_name = {obj['name']: obj for obj in actual['objects']}
        check('mesh_names_equal', set(by_name) == {obj['name'] for obj in expected['objects']})
        report['objects'] = {}
        for source in expected['objects']:
            target = by_name.get(source['name'])
            if target is None:
                continue
            name = source['name']
            comparison = compare_triangles(source['triangles'], target['triangles'])
            report['objects'][name] = comparison
            check(name + ':surface_uv_material_winding', comparison['passed'])
            check(name + ':all_triangles', set(target['polygon_sizes']) == {'3'})
            check(name + ':uv_channel_count', source['uv_channels'] == target['uv_channels'])
            check(name + ':ordered_material_slots', source['materials'] == target['materials'])
            check(name + ':no_new_exact_degenerate', target['exact_degenerate_triangles'] <= source['exact_degenerate_triangles'])
            check(name + ':no_new_exact_duplicate', target['exact_duplicate_surface_triangles'] <= source['exact_duplicate_surface_triangles'])
        check('import_harness_metric_settings', actual['unit_system'] == 'METRIC' and actual['unit_scale'] == 1.0)
        atlas = fbx.parent / Path(reference['atlas']).name
        check('external_atlas_sha_matches', atlas.is_file() and digest(atlas) == reference['atlas_sha256'])
        check('source_still_unchanged', digest(reference['source_blend']) == reference['source_sha256'] and digest(reference['atlas']) == reference['atlas_sha256'])
    except Exception as exc:
        report['failures'].append(type(exc).__name__ + ': ' + str(exc))
    report['transfer_technical_checks_passed'] = not report['failures']
    write(output, report)
    print('SNAPSHOT_READBACK', 'OK' if report['transfer_technical_checks_passed'] else 'FAILED', str(output), flush=True)
    if report['failures']:
        raise RuntimeError('; '.join(report['failures']))


if __name__ == '__main__':
    main(request())

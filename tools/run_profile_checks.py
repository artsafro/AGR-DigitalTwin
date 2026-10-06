"""Review a completed OBR22 snapshot pilot in isolated processes and fresh outputs.

No existing pilot evidence, approved input or interactive DCC scene is changed.
AGR diagnostics and visual renders do not constitute delivery or user acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from dt_ai.core.run_record import RunRecord, atomic_json, file_evidence
from dt_ai.publish.bundle import read_bundle


REVERSE_CHECK = '''from pathlib import Path
import json, sys
sys.path.insert(0, {tools!r})
import bpy
from profile_snapshot_common import snapshot, compare_triangles, write, NUMERICAL_BUDGET, BUDGET_BASIS
c=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
r=json.loads(Path(c['reference']).read_text())
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.scene.unit_settings.scale_length=1.0
bpy.ops.import_scene.fbx(filepath=c['fbx'],use_image_search=False)
a=snapshot(sorted([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:o.name))
e=r['export_reference']
comparison=compare_triangles([t for o in e['objects'] for t in o['triangles']], [t for o in a['objects'] for t in o['triangles']])
same_names=set(o['name'] for o in e['objects'])==set(o['name'] for o in a['objects'])
actual_by_name=dict((o['name'],o) for o in a['objects'])
same_slots=bool(same_names and all(o['materials']==actual_by_name[o['name']]['materials'] for o in e['objects']))
per_object=dict((o['name'],compare_triangles(o['triangles'],actual_by_name[o['name']]['triangles'])) for o in e['objects'] if o['name'] in actual_by_name)
objects_preserved=bool(same_names and all(item['passed'] for item in per_object.values()))
atlas=any(r['atlas_sha256'] in (i['external_sha256'],i['packed_sha256']) for i in a['images'])
result=dict(comparison=comparison, per_object=per_object, mesh_names_equal=same_names, ordered_material_slots_equal=same_slots, atlas_sha_matches=atlas,
            actual_native_readback=a, numerical_budget=NUMERICAL_BUDGET, numerical_budget_basis=BUDGET_BASIS,
            transfer_technical_checks_passed=bool(comparison['passed'] and objects_preserved and same_slots and atlas), delivery_passed=False,
            limitations=['Max custom polygon finish_id/instance reconstruction not certified; compare surface material names and UV',
                         'Texture hash match checks resolved image bytes; reverse FBX embedding is not independently certified',
                         'FBX UnitScaleFactor metadata unverified; physical scale checked through world-coordinate surface comparison'])
write(c['result'],result)
print('MAX_REVERSE_BLENDER_CHECK',result['transfer_technical_checks_passed'])
if not result['transfer_technical_checks_passed']: raise SystemExit(1)
'''


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True, help='Ready pilot run (latest ledger attempt) or explicit attempt directory')
    parser.add_argument('--blender', type=Path, required=True)
    parser.add_argument('--review-id', required=True, help='Fresh review identifier; existing directory refused')
    parser.add_argument('--agr-addon', type=Path)
    parser.add_argument('--max-batch', type=Path)
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args()
    run = args.run.resolve()
    if (run / 'export/export-manifest.json').is_file():
        attempt = run
    else:
        ledger = load(run / 'run.json')
        if not ledger.get('attempts'):
            raise ValueError('Pilot ledger has no completed attempt')
        attempt = Path(ledger['attempts'][-1]['directory']).resolve()
        if not attempt.is_relative_to(run):
            raise ValueError('Pilot attempt points outside its run')
    reference = attempt / 'export/export-manifest.json'
    fbx = attempt / 'actual-zip-files/technical.fbx'
    blend = attempt / 'export/working-copy.blend'
    archive = attempt / 'technical-transfer.zip'
    pilot_ledger_path=attempt.parent/'run.json'
    pilot_ledger=load(pilot_ledger_path)
    completed=next((item for item in pilot_ledger['attempts'] if Path(item['directory']).resolve()==attempt),None)
    if completed is None:
        raise ValueError('Attempt is not bound to pilot ledger')
    for name in ('inspect','export','editable_readback','readback'):
        facts=completed['stages'].get(name,{})
        if facts.get('status')!='verified':
            raise ValueError('Pilot stage not verified: '+name)
        for item in facts['outputs'].values():
            path=Path(item['path']).resolve()
            if not path.is_relative_to(attempt) or sha(path)!=item['sha256'] or path.stat().st_size!=item['bytes']:
                raise ValueError('Changed pilot stage output: '+str(path))
    export_facts = load(reference)
    if export_facts.get('operation_passed') is not True or sha(fbx) != export_facts['artifacts']['technical.fbx']['sha256']:
        raise ValueError('Pilot FBX is missing, changed, or has no successful export evidence')
    if sha(blend)!=export_facts['artifacts']['working-copy.blend']['sha256']:
        raise ValueError('Editable blend differs from verified export')
    package_path=attempt/'package-readback.json'
    package_facts=load(package_path)
    if sha(archive)!=package_facts['sha256']:
        raise ValueError('Archive differs from pilot package readback')
    members=read_bundle(archive)
    expected_members={'technical.fbx',Path(export_facts['atlas']).name}
    if set(members)!=expected_members or set(members)!=set(package_facts['members']):
        raise ValueError('Archive members differ from pilot')
    extracted={}
    for name,data in members.items():
        path=attempt/'actual-zip-files'/name
        if path.read_bytes()!=data or hashlib.sha256(data).hexdigest()!=export_facts['artifacts'][name]['sha256']:
            raise ValueError('Extracted member differs from verified archive: '+name)
        extracted['extracted:'+name]=path
    approved_path = ROOT / 'jobs/OBR22-K02/APPROVED_VERSIONS.json'
    source_root = approved_path.parent / 'outputs'
    approved = load(approved_path)
    sources = {}
    for entry in approved['files']:
        path = (approved_path.parent / entry['path']).resolve()
        if not path.is_relative_to(source_root.resolve()) or sha(path) != entry['sha256']:
            raise ValueError('Approved input absent/changed/outside outputs: ' + str(path))
        sources[entry['path']] = path
    for name in ('npm_v012/shared-uv-manifest.json', 'uv_trial/uv-manifest.json'):
        sources[name] = source_root / name
    inputs = {'reference': reference, 'fbx': fbx, 'blend': blend, 'zip': archive,
              'pilot_ledger':pilot_ledger_path,'package_readback':package_path,**extracted,
              'approved_manifest': approved_path, 'runner': Path(__file__).resolve(),
              **{'approved:' + key: value for key, value in sources.items()}}
    scripts = ['render_profile_comparison.py', 'check_npm_vpm_scale.py', 'profile_snapshot_common.py']
    if args.agr_addon:
        scripts.append('check_profile_agr.py')
        inputs.update({'addon:' + str(path.relative_to(args.agr_addon)): path for path in args.agr_addon.rglob('*.py')})
    if args.max_batch:
        scripts.append('max_profile_roundtrip.py')
    inputs.update({'script:' + name: ROOT / 'tools' / name for name in scripts})
    inputs['blender_executable'] = args.blender.resolve()
    if args.max_batch:
        inputs['max_executable'] = args.max_batch.resolve()
    baseline = file_evidence(inputs)
    # RunRecord validates the identifier before any review directory is created.
    from dt_ai.core.run_record import _name
    review = attempt / 'reviews' / _name(args.review_id)
    review.mkdir(parents=True, exist_ok=False)
    render = review / 'renders'
    scale = review / 'scale-snapshot'
    agr = review / 'agr-native'
    max_dir = review / 'max-batch'
    for path in (render, scale, agr, max_dir):
        path.mkdir()
    configs = {}
    def config(name, value):
        target = review / (name + '-config.json')
        atomic_json(target, value)
        configs[name] = target
        inputs['config:' + name] = target
        return target
    render_mesh_names = export_facts['selected_mesh_names']
    config('renders', {'blend': str(blend), 'fbx': str(fbx), 'output_dir': str(render),
                       'mesh_names': render_mesh_names})
    for path in sources.values():
        target = scale / path.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        if sha(target) != baseline[next(key for key, value in inputs.items() if value == path)]['sha256']:
            raise ValueError('Copied scale source changed: ' + str(path))
        inputs['scale_copy:' + str(path.relative_to(source_root))] = target
    if args.agr_addon:
        config('agr', {'addon_path': str(args.agr_addon.resolve()), 'fbx': str(fbx), 'zip_path': str(archive),
                       'output_dir': str(agr), 'result': str(agr / 'agr-diagnostic.json')})
    if args.max_batch:
        config('max', {'fbx': str(fbx), 'output_dir': str(max_dir)})
        reverse_script = review / 'reverse-check.py'
        reverse_script.write_text(REVERSE_CHECK.format(tools=str(ROOT / 'tools')), encoding='utf-8')
        inputs['reverse_checker'] = reverse_script
        config('reverse', {'fbx': str(max_dir / 'max-roundtrip.fbx'), 'reference': str(reference),
                           'result': str(max_dir / 'blender-reverse-readback.json')})
    record = RunRecord.create(review, 'ledger', inputs,
                              {'scope': 'OBR22 approved component transfer checks', 'timeout': args.timeout,
                               'delivery_passed': False, 'interactive_scene_mutations': False})
    report = {'scope': 'OBR22 snapshot component review', 'review': str(review), 'delivery_passed': False,
              'pilot_accepted': False, 'findings': [], 'stages': {}}
    def blender(script, cfg):
        return [str(args.blender.resolve()), '--background', '--factory-startup', '--disable-autoexec',
                '--python-exit-code', '1', '--python', str(script), '--', str(cfg)]
    def stage(name, argv, outputs, directory, predicate):
        try:
            result = record.run_stage(name, argv, outputs, cwd=ROOT, timeout=args.timeout, resources=[directory])
            report['stages'][name] = {'status': result['status'], 'stdout': result['stdout'], 'stderr': result['stderr']}
            if result['status'] not in ('produced', 'verified'):
                raise RuntimeError('Stage process did not produce evidence; see saved logs')
            evidence = load(next(iter(outputs.values())))
            accepted = predicate(evidence)
            if accepted:
                record.verify_stage(name, lambda paths: predicate(load(next(iter(paths.values())))),
                                    expected_signature=result['signature'])
            report['findings'].append({'id': name, 'status': 'pass' if accepted else 'fail', 'evidence': str(next(iter(outputs.values())))})
            return accepted
        except Exception as exc:
            report['findings'].append({'id': name, 'status': 'fail', 'reason': type(exc).__name__ + ': ' + str(exc)})
            return False
    stage('renders', blender(ROOT / 'tools/render_profile_comparison.py', configs['renders']),
          {'evidence': render / 'render-evidence.json', **{label: render / (label + '.png') for label in ('source-front', 'source-oblique', 'reimport-front', 'reimport-oblique')}},
          render, lambda value: len(value.get('renders', [])) == 4
          and value.get('mesh_names') == render_mesh_names
          and all(item.get('mesh_names') == render_mesh_names for item in value['renders']))
    stage('scale', blender(ROOT / 'tools/check_npm_vpm_scale.py', scale),
          {'evidence': scale / 'npm_v012/npm-vpm-scale-qa.json'}, scale,
          lambda value: value.get('compared_faces', 0) > 0 and value.get('approved_vpm_and_four_maps_unchanged') is True)
    if args.agr_addon:
        stage('agr_diagnostic', blender(ROOT / 'tools/check_profile_agr.py', configs['agr']),
              {'evidence': agr / 'agr-diagnostic.json'}, agr,
              lambda value: value.get('execution') == 'completed' and value.get('input_fbx_unchanged') is True
              and bool(value.get('checks')) and value.get('native_internal_errors', 0) == 0)
        if (agr / 'agr-diagnostic.json').is_file():
            native = load(agr / 'agr-diagnostic.json')
            report['agr_native_status_counts'] = native.get('check_status_counts', {})
            report['findings'].extend({'id': 'agr:' + str(index), 'status': item.get('status', 'pending'), 'native': item}
                                      for index, item in enumerate(native.get('checks', [])))
    else:
        report['findings'].append({'id': 'agr_diagnostic', 'status': 'pending', 'reason': '--agr-addon not provided'})
    if args.max_batch:
        max_ok = stage('max_import_export', [str(args.max_batch.resolve()), str(ROOT / 'tools/max_profile_roundtrip.py'),
                       '-mxsString', 'config:' + configs['max'].as_posix(), '-dm', 'off', '-log', str(max_dir / 'system.log'), '-listenerlog', str(max_dir / 'listener.log')],
                       {'evidence': max_dir / 'max-native.json', 'fbx': max_dir / 'max-roundtrip.fbx'}, max_dir,
                       lambda value: value.get('operation_completed') is True)
        if max_ok:
            stage('max_reverse_readback', blender(reverse_script, configs['reverse']),
                  {'evidence': max_dir / 'blender-reverse-readback.json'}, max_dir,
                  lambda value: value.get('transfer_technical_checks_passed') is True)
        else:
            report['findings'].append({'id': 'max_reverse_readback', 'status': 'pending', 'reason': 'Max import/export failed'})
    else:
        report['findings'].append({'id': 'max_roundtrip', 'status': 'pending', 'reason': '--max-batch not provided'})
    protected = {key: value for key, value in inputs.items() if key in baseline}
    unchanged = file_evidence(protected) == baseline
    report['findings'].extend([{'id': 'protected_inputs', 'status': 'pass' if unchanged else 'fail'},
                               {'id': 'visual_acceptance', 'status': 'pending', 'reason': 'Four renders require explicit user acceptance'},
                               {'id': 'full_delivery', 'status': 'pending', 'reason': 'Component diagnostics do not satisfy full OKS delivery gates'}])
    atomic_json(review / 'review-report.json', report)
    print(json.dumps({'review': str(review), 'report': str(review / 'review-report.json'), 'delivery_passed': False,
                      'failed': sum(item['status'] == 'fail' for item in report['findings'])}, ensure_ascii=False))
    if any(item['status'] == 'fail' for item in report['findings']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

"""Local file-based pilot; deterministic DCC stages, hash-bound restart, no agent API.

Run from project root. Open interactive DCC scenes are never accessed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from dt_ai.core.run_record import RunRecord, atomic_json, file_evidence, EvidenceMismatch
from dt_ai.publish.bundle import package, read_bundle
from dt_ai.core.adapter_report import AdapterReport, Check


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(blender, script, config):
    return [str(blender), '--background', '--factory-startup', '--disable-autoexec',
            '--python-exit-code', '1', '--python', str(ROOT/'tools'/script), '--', str(config)]


def execute(run, name, argv, outputs, directory, verifier):
    record = run.run_stage(name, argv, outputs, cwd=ROOT, timeout=180, resources=[directory])
    if record['status'] not in {'produced', 'verified'}:
        raise RuntimeError(f"{name}: {record['status']}; see {record['stderr']}")
    return run.verify_stage(name, verifier, expected_signature=record['signature'])


def run(args):
    spec_path=args.spec.resolve()
    spec=load(spec_path)
    if not spec.get('execution_authorized'):
        raise ValueError('Pilot spec requires explicit execution authorization')
    if spec['profile'] != 'NPM' or spec['synthetic']:
        raise ValueError('This runner supports the real NPM component-transfer pilot only')
    approved_path=ROOT/spec['approved_manifest']
    approved=load(approved_path)
    inputs={'spec':spec_path,'approved':approved_path}
    for item in approved['files']:
        p=ROOT/'jobs/OBR22-K02'/item['path']
        if sha(p)!=item['sha256']:
            raise EvidenceMismatch(f'Approved source hash mismatch: {p}')
        inputs[item['path']]=p
    for p in (ROOT/'standards').glob('*.yaml'):
        inputs[p.name]=p
    scripts=['run_profile_pilot.py','export_profile_snapshot.py','check_profile_snapshot.py','profile_snapshot_common.py']
    context={'scope':spec['scope'],'profile':'NPM','code_sha256':{p:sha(ROOT/'tools'/p) for p in scripts},
             'run_record_sha256':sha(ROOT/'src/dt_ai/core/run_record.py'),
             'blender_path':str(args.blender.resolve()),'blender_exe_sha256':sha(args.blender),
             'blender_version':subprocess.check_output([str(args.blender),'--version'],text=True,encoding='utf-8').splitlines()[0]}
    record=RunRecord.open(args.resume.resolve(),inputs,context) if args.resume else RunRecord.create(
        ROOT/'jobs/ORCH-OBR22-NPM/runs',args.run_id,inputs,context)
    ledger=record.read()
    attempt=record.new_attempt() if args.new_attempt or not ledger['attempts'] else Path(ledger['attempts'][-1]['directory'])
    source_dir=attempt/'source'
    source_dir.mkdir(exist_ok=True)
    scene=next(ROOT/s['path'] for s in spec['sources'] if s['role']=='npm_scene_read_only')
    atlas=next(ROOT/s['path'] for s in spec['sources'] if s['role']=='npm_atlas_read_only')
    for original in (scene,atlas):
        copy=source_dir/original.name
        if copy.exists():
            if sha(copy)!=sha(original):
                raise EvidenceMismatch(f'Source copy changed: {copy}')
        else:
            shutil.copyfile(original,copy)
    atomic_json(attempt/'input-manifest.json',{'inputs':file_evidence(inputs),'context':context,
                                             'source_copy':file_evidence({'scene':source_dir/scene.name,'atlas':source_dir/atlas.name})})
    preflight=attempt/'preflight'
    inspect_config=attempt/'inspect-config.json'
    cfg={'operation':'inspect','source_blend':str(source_dir/scene.name),'atlas':str(source_dir/atlas.name),
         'output_dir':str(preflight)}
    if spec.get('mesh_names'):
        cfg['mesh_names']=spec['mesh_names']
    atomic_json(inspect_config,cfg)
    execute(record,'inspect',command(args.blender,'export_profile_snapshot.py',inspect_config),
            {'snapshot':preflight/'source-snapshot.json'},preflight,
            lambda paths:load(paths['snapshot'])['operation_passed'] is True)
    source_snapshot=load(preflight/'source-snapshot.json')
    if args.stop_after=='inspect':
        print(json.dumps({'run':str(record.directory),'stage':'inspect_verified','meshes':source_snapshot['selected_mesh_names']},ensure_ascii=False))
        return
    export=attempt/'export'
    export_config=attempt/'export-config.json'
    atomic_json(export_config,{**cfg,'operation':'export','mesh_names':source_snapshot['selected_mesh_names'],'output_dir':str(export)})
    execute(record,'export',command(args.blender,'export_profile_snapshot.py',export_config),
            {'manifest':export/'export-manifest.json','fbx':export/'technical.fbx',
             'blend':export/'working-copy.blend','atlas':export/atlas.name},export,
            lambda paths:load(paths['manifest'])['operation_passed'] is True)
    reopened=attempt/'editable-readback'
    reopen_config=attempt/'editable-readback-config.json'
    atomic_json(reopen_config,{**cfg,'source_blend':str(export/'working-copy.blend'),
                              'atlas':str(export/atlas.name),'output_dir':str(reopened),
                              'mesh_names':source_snapshot['selected_mesh_names']})
    def editable_matches(paths):
        actual=load(paths['snapshot'])
        return actual['operation_passed'] is True and actual['native_source']['objects']==source_snapshot['native_source']['objects']
    execute(record,'editable_readback',command(args.blender,'export_profile_snapshot.py',reopen_config),
            {'snapshot':reopened/'source-snapshot.json'},reopened,editable_matches)
    assets={name:(export/name).read_bytes() for name in ['technical.fbx',atlas.name]}
    transfer=attempt/'technical-transfer.zip'
    if transfer.exists():
        if read_bundle(transfer)!=assets:
            raise EvidenceMismatch('Existing technical ZIP differs from export')
    else:
        package(assets,transfer)
    actual=read_bundle(transfer)
    if actual!=assets:
        raise EvidenceMismatch('ZIP actual member bytes mismatch')
    extracted=attempt/'actual-zip-files'
    extracted.mkdir(exist_ok=True)
    for name,data in actual.items():
        target=extracted/name
        if target.exists() and target.read_bytes()!=data:
            raise EvidenceMismatch(f'Extracted file changed: {target}')
        if not target.exists():
            target.write_bytes(data)
    atomic_json(attempt/'package-readback.json',{'archive':str(transfer),'sha256':sha(transfer),
                  'members':file_evidence({n:extracted/n for n in actual}),'member_bytes_equal':True,'delivery_passed':False})
    result=attempt/'actual-file-readback.json'
    check_config=attempt/'readback-config.json'
    atomic_json(check_config,{'fbx':str(extracted/'technical.fbx'),'reference':str(export/'export-manifest.json'),'result':str(result)})
    execute(record,'readback',command(args.blender,'check_profile_snapshot.py',check_config),
            {'readback':result},attempt/'readback-owned',
            lambda paths:load(paths['readback'])['transfer_technical_checks_passed'] is True)
    preserved=all(sha(ROOT/'jobs/OBR22-K02'/item['path'])==item['sha256'] for item in approved['files'])
    report=AdapterReport(operation='npm-component-transfer',tool_version='snapshot-pilot-1',scope=spec['scope'],
        execution='completed',input_manifest=str(attempt/'input-manifest.json'),output_manifest=str(export/'export-manifest.json'),
        checks=(Check(id='native_export',status='pass',evidence=str(export/'export-manifest.json')),
                Check(id='editable_saved_readback',status='pass',evidence=str(reopened/'source-snapshot.json')),
                Check(id='actual_zip_readback',status='pass',evidence=str(attempt/'package-readback.json')),
                Check(id='actual_fbx_import',status='pass',evidence=str(result)),
                Check(id='approved_preserved',status='pass' if preserved else 'fail',evidence=str(approved_path)),
                Check(id='max_roundtrip',status='not_run',evidence='Separate isolated Max batch stage'),
                Check(id='agr_checker',status='not_run',evidence='Separate native checker diagnostic stage')),
        pending_decisions=('User visual acceptance of the new transfer result',),
        limitations=('Component pilot; full OKS/Ground/placement/naming not certified',
                     'Original unresolved finish_id0 retained','Generic polygon finish_id is native provenance; FBX material semantics checked separately'))
    atomic_json(attempt/'report.json',report.model_dump(mode='json'))
    print(json.dumps({'run':str(record.directory),'archive':str(transfer),'transfer_file_checks':True,
                     'approved_preserved':preserved,'delivery_passed':False,'summary':report.summary()},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec',type=Path,default=ROOT/'jobs/ORCH-OBR22-NPM/pilot-spec.json')
    p.add_argument('--blender',type=Path,required=True)
    p.add_argument('--run-id',default='pilot-20261001-001')
    p.add_argument('--resume',type=Path)
    p.add_argument('--new-attempt',action='store_true',help='Retain failed outputs and create fresh attempt directories')
    p.add_argument('--stop-after',choices=['inspect','readback'],default='readback')
    run(p.parse_args())

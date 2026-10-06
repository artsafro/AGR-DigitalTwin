"""Run the reviewed exterior-surface -> shell prototype in a fresh output directory."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from dt_ai.geometry.shell import shell_body
from dt_ai.core.adapter_report import AdapterReport, Check
from dt_ai.core.io import read_json, write_json
from check_shell_windows import audit


def run(config_path, output):
    config = read_json(config_path.read_bytes())
    for key in ('surface_review_ref', 'thickness_decision_ref'):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f'Missing manual decision: {key}')
    if config['units'] != 'm':
        raise ValueError('Explicit metre inputs required')
    source = (config_path.parent / config['surface_npz']).resolve()
    profiles_path = (config_path.parent / config['profiles_json']).resolve()
    profiles_doc = read_json(profiles_path.read_bytes())
    profiles = profiles_doc['profiles']
    with np.load(source, allow_pickle=False) as data:
        v, f, labels = data['vertices'].copy(), data['faces'].copy(), data['facade_indices'].copy()
    if len(labels) != len(f) or not np.issubdtype(labels.dtype, np.integer) or (labels < 1).any() or (labels > len(profiles)).any():
        raise ValueError('Invalid facade provenance labels')
    angle = float(config['angle_rad'])
    if not np.isfinite(angle):
        raise ValueError('Invalid local rotation')
    if 'angle_rad' not in profiles_doc or not np.isclose(
            angle, float(profiles_doc['angle_rad']), atol=1e-12, rtol=0):
        raise ValueError('Config angle_rad does not match the reviewed exterior report')
    R = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    v[:, :2] = v[:, :2] @ R
    result = shell_body(v, f, [profiles[i-1]['outward']+[0.] for i in labels],
                        units=config['units'], thickness_m=config['thickness_m'],
                        tolerance_m=config['tolerance_m'], name=config['body_name'],
                        source_refs=[f'{profiles_path}#profiles/{i-1}' for i in labels])
    coords = np.array(result['mesh']['vertices'])
    coords[:, :2] = coords[:, :2] @ R.T
    result['mesh']['vertices'] = coords.tolist()
    scene = {'angle': angle, 'windows': [], 'meshes': [result['mesh']]}
    # Audit in memory before saving; a failed audit is still written as evidence.
    qa = audit(scene)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'body-shell.json', {**scene, 'face_sources': result['face_sources'],
                                        'thickness_m': result['thickness_m'], 'inner_faces': False})
    write_json(output/'qa.json', qa)
    inputs = {'config': config, 'sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in (config_path, source, profiles_path)},
              'implementation_sha256': hashlib.sha256((Path(__file__).resolve().parents[1]/'src/dt_ai/geometry/shell.py').read_bytes()).hexdigest()}
    write_json(output/'inputs.json', inputs)
    saved = read_json((output/'body-shell.json').read_bytes())
    readback = saved['meshes'] == scene['meshes'] and saved['face_sources'] == result['face_sources']
    report = AdapterReport(operation='exterior-body-shell', tool_version='prototype-1',
        scope='Reviewed exterior surface and rims only; no windows/interior/material inference',
        execution='completed', input_manifest=str(output/'inputs.json'), output_manifest=str(output/'body-shell.json'),
        checks=(Check(id='geometry', status='pass' if qa['geometry_checks_passed'] else 'fail', evidence=str(output/'qa.json')),
                Check(id='json_readback', status='pass' if readback else 'fail', evidence=str(output/'body-shell.json')),
                Check(id='dcc_readback', status='not_run', evidence='Run body_shell_blender.py separately')),
        pending_decisions=('Visual review of this new output',),
        limitations=('Orthogonal vertical facades only', 'Existing measured exterior required', 'Second project untested'))
    write_json(output/'report.json', report.model_dump(mode='json'))
    print(json.dumps({**report.summary(), 'full_report': str(output/'report.json')}))
    return qa['geometry_checks_passed'] and readback


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    sys.exit(0 if run(args.config.resolve(), args.output.resolve()) else 1)

"""Audit the actual Blender readback and update operation evidence, not approval."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from dt_ai.core.io import read_json, write_json
from dt_ai.core.adapter_report import AdapterReport, Check
from check_shell_windows import audit


def check(p):
    before = read_json((p/'body-shell.json').read_bytes())
    actual = read_json((p/'blender-readback.json').read_bytes())
    qa = audit(actual)
    b, a = before['meshes'][0], actual['meshes'][0]
    exact_faces = b['faces'] == a['faces']
    materials_match = b['materials'] == a['materials']
    name_match = b['name'] == a['name']
    error = float(np.max(np.abs(np.array(b['vertices'])-np.array(a['vertices']))))
    sources_match = before['face_sources'] == actual['face_sources']
    passed = bool(qa['geometry_checks_passed'] and exact_faces and materials_match and
                  name_match and error < 5e-6 and sources_match)
    write_json(p/'readback-qa.json', {**qa, 'faces_preserved': exact_faces,
                                   'coordinate_error_m': error, 'sources_preserved': sources_match,
                                   'materials_preserved': materials_match, 'name_preserved': name_match})
    report = AdapterReport.model_validate(read_json((p/'report.json').read_bytes()))
    data = report.model_dump(mode='json')
    data['checks'] = [c for c in data['checks'] if c['id'] != 'dcc_readback'] + [
        Check(id='dcc_readback', status='pass' if passed else 'fail', evidence=str(p/'readback-qa.json')).model_dump()]
    report = AdapterReport.model_validate(data)
    write_json(p/'report.json', report.model_dump(mode='json'))
    print(json.dumps(report.summary()))
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    sys.exit(0 if check(parser.parse_args().output.resolve()) else 1)

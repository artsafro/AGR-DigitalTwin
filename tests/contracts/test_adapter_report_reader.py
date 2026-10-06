import json
from pathlib import Path
import subprocess
import sys

import pytest

from dt_ai.core.adapter_report import AdapterReport


READER = Path(__file__).resolve().parents[2] / 'tools/adapter_report.py'


def run_reader(path):
    return subprocess.run([sys.executable, str(READER), str(path)],
                          capture_output=True, text=True)


def test_reader_valid_failed_operation_is_not_format_error(tmp_path):
    report = AdapterReport(operation='fixture', tool_version='test', scope='synthetic',
                           execution='failed', input_manifest='fixture.json')
    path = tmp_path / 'report.json'
    path.write_text(report.model_dump_json(), encoding='utf-8')
    result = run_reader(path)
    assert result.returncode == 0
    assert result.stderr == ''
    summary = json.loads(result.stdout)
    assert summary['execution'] == 'failed'
    assert not summary['required_checks_passed']
    assert not summary['delivery_passed']
    assert Path(summary['full_report']) == path.resolve()


def test_reader_contract_errors_do_not_dump_payload(tmp_path):
    payload = {f'private-payload-{i}': 'x' * 1000 for i in range(100)}
    path = tmp_path / 'invalid.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    result = run_reader(path)
    assert result.returncode == 1
    assert result.stdout == ''
    assert json.loads(result.stderr) == {'error': 'invalid_report', 'errors_total': 105}
    assert 'private-payload' not in result.stderr
    assert len(result.stderr) < 150


@pytest.mark.parametrize('content', [None, '{', '{"x":1,"x":2}', '{"x":NaN}'])
def test_reader_io_and_json_errors_are_compact(tmp_path, content):
    path = tmp_path / 'bad.json'
    if content is not None:
        path.write_text(content, encoding='utf-8')
    result = run_reader(path)
    assert result.returncode == 1
    assert result.stdout == ''
    assert json.loads(result.stderr) == {'error': 'unreadable_or_invalid_json'}

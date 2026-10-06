import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    'uv_stage_common', Path(__file__).parents[2] / 'technical_library/uv_continuous/common.py')
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


def test_does_not_accept_existing_unowned_outputs(tmp_path):
    (tmp_path / 'approved.blend').write_bytes(b'preserve')
    with pytest.raises(FileNotFoundError):
        common.require_stage(tmp_path, 'inspect')
    assert (tmp_path / 'approved.blend').read_bytes() == b'preserve'


@pytest.mark.parametrize('pipeline,stage', [('foreign', 'inspect'), (common.PIPELINE, 'solve')])
def test_rejects_foreign_workspace_or_repeated_solver(tmp_path, pipeline, stage):
    (tmp_path / 'PIPELINE.json').write_text(json.dumps({'pipeline': pipeline, 'stage': stage}))
    with pytest.raises(ValueError, match='Expected isolated pipeline stage'):
        common.require_stage(tmp_path, 'inspect')


def test_stage_transition_retains_input_hashes(tmp_path):
    state = {'pipeline': common.PIPELINE, 'stage': 'inspect', 'input_sha256': {'source': 'proof'}}
    (tmp_path / 'PIPELINE.json').write_text(json.dumps(state))
    assert common.require_stage(tmp_path, 'inspect') == tmp_path
    common.mark_stage(tmp_path, 'solve')
    result = json.loads((tmp_path / 'PIPELINE.json').read_text())
    assert result['stage'] == 'solve'
    assert result['input_sha256'] == state['input_sha256']

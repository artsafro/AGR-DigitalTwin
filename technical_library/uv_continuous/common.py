"""Shared workspace and process handling for the four scoped UV stages."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

PIPELINE = 'sosh1150-uv-v006'


def arguments(scene=False):
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    if scene:
        parser.add_argument('--source-blend', type=Path, required=True)
        parser.add_argument('--diffuse', type=Path, required=True)
    else:
        parser.add_argument('--blender', type=Path)
        parser.add_argument('--phase', choices=['local', 'dcc'], default='local')
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return parser.parse_args(args)


def require_stage(root, expected):
    root = Path(root).resolve()
    state = json.loads((root / 'PIPELINE.json').read_text())
    if state.get('pipeline') != PIPELINE or state.get('stage') != expected:
        raise ValueError('Expected isolated pipeline stage: ' + expected)
    return root


def mark_stage(root, stage):
    path = root / 'PIPELINE.json'
    state = json.loads(path.read_text())
    state['stage'] = stage
    path.write_text(json.dumps(state, indent=2), encoding='utf-8')


def run_dcc(script, root, blender):
    if blender is None or not blender.is_file():
        raise ValueError('Supply an existing --blender executable')
    command = [str(blender.resolve()), '--background', '--factory-startup',
               '--disable-autoexec', '--python-exit-code', '1', '--python', str(script.resolve()), '--',
               '--output', str(root), '--phase', 'dcc']
    with (root / (script.stem + '-blender.log')).open('w', encoding='utf-8') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)

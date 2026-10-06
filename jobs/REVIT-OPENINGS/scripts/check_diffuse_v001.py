"""Read back every generated diffuse PNG and verify the repeat boundaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

root = Path(__file__).resolve().parents[1] / 'outputs/diffuse-v001'
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
entries = manifest['materials']
assert len(entries) == 15
assert manifest['aliases'] == {'F13': 'F1', 'F14': 'F11'}
assert sum(e['resolution'] == [4096, 4096] for e in entries) == 3
assert sum(e['resolution'] == [256, 256] for e in entries) == 12
assert {e['id'] for e in entries if e['resolution'][0] == 4096} == {'F1', 'F9', 'F9.1'}

for entry in [*entries, manifest['F10_alternate']]:
    path = root / entry['file']
    assert path.is_file(), path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], path
    with Image.open(path) as img:
        img.load()
        assert img.mode == 'RGB', path
        assert img.size == tuple(entry.get('resolution', [256, 256])), path
        pixels = np.asarray(img)
        if img.width == 256:
            assert np.all(pixels == pixels[0, 0]), path
        else:
            assert not np.all(pixels == pixels[0, 0]), path
            # The repeat boundary lies at the centre of a uniform grout line.
            assert np.array_equal(pixels[0], pixels[-1]), path
            assert np.array_equal(pixels[:, 0], pixels[:, -1]), path
            assert np.max(np.abs(pixels[0, 0].astype(int) - pixels[100, 100].astype(int))) >= 15
            assert np.max(np.abs(pixels[1024, 100].astype(int) - pixels[1000, 100].astype(int))) >= 10

assert len(list((root / 'maps').glob('*.png'))) == 16
print(json.dumps({'passed': True, 'primary_maps': 15, 'alternate_maps': 1,
                  'repeat_edges_checked': 3, 'hashes_checked': 16}, ensure_ascii=False))

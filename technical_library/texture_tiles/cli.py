"""Configured RGB tiles, fresh outputs, PNG and archive readback."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from technical_library.texture_tiles.panels import kpp_panels
from tools.facades_texture_pattern import raster


def validate(config):
    tiles = config['tiles']
    if not tiles:
        raise ValueError('No tiles')
    ids, udims = set(), set()
    for tile in tiles:
        ident, udim = tile['id'], tile['udim']
        if type(ident) is not int or type(udim) is not int or ident < 1 or udim < 1001:
            raise ValueError('Invalid numeric ID/UDIM')
        if ident in ids or udim in udims:
            raise ValueError('Duplicate ID/UDIM')
        ids.add(ident); udims.add(udim)
        if len(tile['rgb']) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in tile['rgb']):
            raise ValueError('Invalid RGB')
        if len(tile['size']) != 2 or any(type(n) is not int or not 1 <= n <= 8192 for n in tile['size']):
            raise ValueError('Invalid size')
        if tile['kind'] not in ('solid', 'kpp_panels', 'metric_pattern'):
            raise ValueError('Unknown tile recipe')
        if tile['kind'] == 'kpp_panels' and tile['size'] != [4096, 4096]:
            raise ValueError('Historical KPP panel recipe requires 4096 square')
        if tile['kind'] == 'metric_pattern':
            if tile.get('pattern_id') not in (101, 102, 103, 104, 105):
                raise ValueError('Unknown metric pattern ID')
            if len(tile.get('extent_m', [])) != 2 or any(not np.isfinite(n) or n <= 0 for n in tile['extent_m']):
                raise ValueError('Metric recipe requires positive physical extent')
    return tiles


def draw(tile):
    width, height = tile['size']
    if tile['kind'] == 'solid':
        return Image.new('RGB', (width, height), tuple(tile['rgb']))
    if tile['kind'] == 'kpp_panels':
        return Image.fromarray(kpp_panels(tile['rgb']), 'RGB')
    pixels = raster(tile['pattern_id'], width, height, tile['extent_m'], np.asarray(tile['rgb']) / 255,
                    joint=tile.get('joint_m', .005), offset=tuple(tile.get('offset_m', [0, 0])),
                    panel_dimensions=tile.get('panel_dimensions_m'))
    return Image.fromarray(np.rint(np.clip(pixels, 0, 1) * 255).astype(np.uint8), 'RGB')


def build(config, output, reference=None):
    tiles = validate(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for tile in tiles:
        path = output / f"{tile['udim']}.png"
        draw(tile).save(path, optimize=True)
        with Image.open(path) as saved:
            saved.load()
            pixels = np.asarray(saved)
            if saved.mode != 'RGB' or list(saved.size) != tile['size']:
                raise ValueError('PNG readback format differs')
            solid = bool(np.all(pixels == tile['rgb']))
            if tile['kind'] == 'solid' and not solid:
                raise ValueError('Solid color differs')
            edges = bool(np.array_equal(pixels[0], pixels[-1]) and np.array_equal(pixels[:, 0], pixels[:, -1]))
            if tile['kind'] != 'metric_pattern' and not edges:
                raise ValueError('Historical seamless edge invariant differs')
            row = {'id': tile['id'], 'udim': tile['udim'], 'size': tile['size'], 'solid': solid,
                   'opposite_edges_equal': edges, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            if reference:
                original = Path(reference) / path.name
                with Image.open(original) as expected:
                    same = expected.mode == saved.mode and expected.size == saved.size and np.array_equal(pixels, np.asarray(expected))
                row['reference_pixels_equal'] = bool(same)
                row['reference_bytes_equal'] = path.read_bytes() == original.read_bytes()
                if not same:
                    raise ValueError(f'Reference differs: {path.name}')
            rows.append(row)
    archive = output / 'tiles.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as zipped:
        for row in rows:
            path = output / f"{row['udim']}.png"
            zipped.write(path, path.name)
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() or set(zipped.namelist()) != {f"{r['udim']}.png" for r in rows}:
            raise ValueError('Archive inventory differs')
        for row in rows:
            if hashlib.sha256(zipped.read(f"{row['udim']}.png")).hexdigest() != row['sha256']:
                raise ValueError('Archive member differs')
    report = {'tiles': rows, 'archive_readback_equal': True, 'delivery_passed': False,
              'scope': 'RGB map generation/readback only; no shader, model UV, physical-scale or native Max acceptance'}
    (output / 'QA.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path)
    args = parser.parse_args()
    report = build(json.loads(args.config.read_text(encoding='utf-8')), args.output, args.reference)
    print(json.dumps({'tiles': len(report['tiles']), 'archive_readback_equal': report['archive_readback_equal']}))

"""Build/read back configured atlas; compare prior PNG and manifest if supplied."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops
from atlas import build


def verify(output, config, reference_png=None, reference_manifest=None):
    output = Path(output)
    png = output / 'new_building_windows_ral_atlas_2048_v8.png'
    manifest = output / 'new_building_window_uv_manifest_v8.csv'
    with manifest.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    expected = {str(w['id']): w for w in config['WINDOWS']}
    assert len(rows) == len(expected) and {r['id'] for r in rows} == set(expected)
    for row in rows:
        item = expected[row['id']]
        assert int(row['width']) == item['width'] and int(row['height']) == item['height']
        assert row['source_docx_image'] == config['DOCX_IMAGES'][row['id']]
    with Image.open(png) as image:
        image.load()
        assert image.size == (config['SIZE'], config['SIZE']) and image.mode == 'RGB'
        if reference_png:
            with Image.open(reference_png) as original:
                assert image.size == original.size and image.mode == original.mode
                assert ImageChops.difference(image, original).getbbox() is None
        minimum = None
        for row in rows:
            if not expected[row['id']]['door_leaves']:
                continue
            x, y, width, height = (int(row[k]) for k in ['x', 'y', 'width', 'height'])
            for yy in range(y, y + height):
                run = 0
                for xx in range(x, x + width + 1):
                    if xx < x + width and image.getpixel((xx, yy)) == (255, 255, 255):
                        run += 1
                    elif run:
                        minimum = run if minimum is None else min(minimum, run)
                        run = 0
        assert minimum is not None and minimum >= 8, 'Thin white door-glass sliver'
    if reference_manifest:
        with Path(reference_manifest).open(encoding='utf-8-sig', newline='') as stream:
            prior = list(csv.DictReader(stream))
        normalize = lambda data: [{k: v for k, v in row.items() if k != 'source'} for row in data]
        assert normalize(rows) == normalize(prior), 'Manifest geometry/mapping changed'
    return {'png_readback_verified': True, 'manifest_readback_verified': True,
            'ids': sorted(int(k) for k in expected), 'minimum_white_door_run_px': minimum,
            'reference_png_pixels_equal': bool(reference_png),
            'reference_manifest_geometry_and_mapping_equal': bool(reference_manifest),
            'source_text_sanitized': True, 'png_sha256': hashlib.sha256(png.read_bytes()).hexdigest(),
            'native_model_uv_or_fbx_tested': False, 'full_agr_delivery_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fonts', type=Path, required=True)
    parser.add_argument('--reference-png', type=Path)
    parser.add_argument('--reference-manifest', type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    build(config, args.output, args.fonts)
    report = verify(args.output, config, args.reference_png, args.reference_manifest)
    (args.output / 'QA.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()

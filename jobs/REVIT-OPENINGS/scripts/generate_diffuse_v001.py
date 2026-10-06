"""Generate reproducible sRGB diffuse maps from the school facade material register."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / 'outputs/material-register-v001'
OUT = ROOT / 'outputs/diffuse-v001'
MAPS = OUT / 'maps'
MAPS.mkdir(parents=True, exist_ok=True)

register = json.loads((REGISTER / 'materials.json').read_text(encoding='utf-8'))
legend = np.asarray(Image.open(REGISTER / 'source/page-18.png').convert('RGB'))

# Coordinates are central, unannotated pixels of the PDF 18 legend swatches.
spots = {
    'F2': (100, 873), 'F3': (100, 925), 'F4': (100, 976),
    'F5': (100, 1025), 'F6': (600, 810), 'F7': (600, 865),
    'F8': (600, 922), 'F9': (600, 973), 'F9.1': (600, 1025),
    'F12': (1040, 923), 'F15': (1510, 810), 'F16': (1510, 865),
}

def swatch_rgb(name: str) -> tuple[int, int, int]:
    x, y = spots[name]
    pixels = legend[y-7:y+7, x-7:x+7].reshape(-1, 3)
    return tuple(int(v) for v in np.median(pixels, axis=0))

colors = {name: swatch_rgb(name) for name in spots}
# The F1 PDF swatch is a light grey hatch, not a faithful NCS reference.
# 0.180144 linear grey is the user's imported body material for the main grey facade.
body_linear_grey = 0.1801443099975586
body_srgb = round(255 * (1.055 * body_linear_grey ** (1 / 2.4) - .055))
colors['F1'] = (body_srgb,) * 3
colors['F11'] = colors['F12']  # RAL 7016 in the album, swatch on F12.
colors['F10'] = colors['F8']  # provisional Y40R; second documented option exported below.

def save_flat(name: str, color: tuple[int, int, int]):
    path = MAPS / f'{name}_Diffuse_256.png'
    Image.new('RGB', (256, 256), color).save(path, optimize=True)
    return path

def raster_periodic(base, joint, *, cell_x, cell_y, line_px, seed,
                    tile_variation, fine_noise, edge_falloff):
    """A physical-size grid with joints centred on all four repeat boundaries."""
    size = 4096
    rng = np.random.default_rng(seed)
    image = np.empty((size, size, 3), dtype=np.uint8)
    x = np.arange(size, dtype=np.float32)[None, :]
    dx = np.minimum(x % cell_x, cell_x - x % cell_x)
    cols = (x.astype(np.int32) // cell_x).astype(np.int16)
    tint = rng.integers(-tile_variation, tile_variation + 1,
                        size=(size // cell_y, size // cell_x), dtype=np.int16)
    base = np.asarray(base, dtype=np.float32)
    joint = np.asarray(joint, dtype=np.float32)
    for top in range(0, size, 128):
        bottom = min(top + 128, size)
        y = np.arange(top, bottom, dtype=np.float32)[:, None]
        dy = np.minimum(y % cell_y, cell_y - y % cell_y)
        rows = (y.astype(np.int32) // cell_y).astype(np.int16)
        # Very low amplitude monocolour variation; no baked shadows or stone veins.
        low_frequency = (np.sin(2*math.pi*x/256) * np.sin(2*math.pi*y/256)) * .75
        noise = rng.normal(0, fine_noise, size=(bottom-top, size)).astype(np.float32)
        value = low_frequency + noise + tint[rows, cols]
        rgb = base[None, None, :] + value[:, :, None]
        distance = np.minimum(dx, dy)
        edge = (distance >= line_px/2) & (distance < line_px/2+edge_falloff)
        rgb = np.where(edge[:, :, None], rgb - 6, rgb)
        seam = distance < line_px/2
        rgb = np.where(seam[:, :, None], joint[None, None, :], rgb)
        image[top:bottom] = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
    return Image.fromarray(image, 'RGB')

entries = []
for material in register['materials']:
    mid = material['id']
    resolution = material['resolution'][0]
    if resolution == 256:
        path = save_flat(mid, colors[mid])
        extent = None
        construction = 'uniform color placeholder'
        params = {}
    elif mid == 'F1':
        path = MAPS / 'F1_Diffuse_4096.png'
        # Four 1200-mm cassettes across, eight 600-mm rows; 5-mm joints.
        raster_periodic(colors[mid], (86, 86, 86), cell_x=1024, cell_y=512,
                        line_px=4, seed=1101, tile_variation=3,
                        fine_noise=.7, edge_falloff=3).save(path, optimize=True)
        extent = [4.8, 4.8]
        construction = 'metal cassettes; periodic joints; neutral albedo'
        params = {'panel_mm': [1200, 600], 'joint_mm_approx': 5}
    else:
        assert mid in {'F9', 'F9.1'}
        path = MAPS / f'{mid}_Diffuse_4096.png'
        grout = (167, 139, 101) if mid == 'F9' else (145, 145, 145)
        raster_periodic(colors[mid], grout, cell_x=1024, cell_y=1024,
                        line_px=5, seed=901 if mid == 'F9' else 902,
                        tile_variation=2, fine_noise=.85,
                        edge_falloff=3).save(path, optimize=True)
        extent = [2.4, 2.4]
        construction = 'monocolour porcelain 600-mm tile grid with joints'
        params = {'tile_mm': [600, 600], 'joint_mm_approx': 3}
    entries.append({'id': mid, 'file': 'maps/' + path.name,
                    'resolution': [resolution, resolution], 'rgb_reference': colors[mid],
                    'reference_hex': '#%02X%02X%02X' % colors[mid],
                    'reference_source': ('body material linear grey + visualization' if mid == 'F1'
                                         else 'PDF 18 legend swatch F12' if mid == 'F11'
                                         else 'PDF 18 legend swatch F8; provisional choice' if mid == 'F10'
                                         else 'PDF 18 legend swatch'),
                    'source_color_code': material['source_color_code'],
                    'construction': construction, 'extent_m': extent, **params,
                    'status': 'PROVISIONAL' if mid in {'F1', 'F10', 'F9', 'F9.1'} else 'SOURCE_SWATCH'})

alternate = save_flat('F10_Y90R_alternate', colors['F6'])
manifest = {
    'project': register['project'], 'version': 'diffuse-v001', 'color_space': 'sRGB',
    'image_type': 'base color / diffuse only; no baked lighting',
    'source_pdf_sha256': register['source_sha256'],
    'aliases': {'F13': 'F1', 'F14': 'F11'},
    'glass': 'transparent glazing has no F diffuse map in the material register',
    'tile_format_note': '600x600 mm is a working choice; PDF legend does not specify installation format',
    'F10_alternate': {'file': 'maps/' + alternate.name,
                      'reference_hex': '#%02X%02X%02X' % colors['F6'],
                      'source_color_code': 'NCS S 1060-Y90R'},
    'materials': entries,
}

for entry in entries:
    path = OUT / entry['file']
    entry['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
manifest['F10_alternate']['sha256'] = hashlib.sha256(alternate.read_bytes()).hexdigest()
(OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

font_path = 'C:/Windows/Fonts/arial.ttf'
font = ImageFont.truetype(font_path, 29)
small = ImageFont.truetype(font_path, 21)
preview = Image.new('RGB', (1900, 1420), '#f2f3f4')
pen = ImageDraw.Draw(preview)
pen.text((38, 23), 'СОШ 1150  |  диффузные карты F1–F16', font=font, fill='#23282c')
pen.text((38, 67), '3 карты 4K с рисунком + 12 однотонных 256px; F13 → F1, F14 → F11',
         font=small, fill='#4d555b')
for index, entry in enumerate(entries):
    col, row = index % 5, index // 5
    left, top = 38 + col*375, 115 + row*420
    pen.rounded_rectangle((left, top, left+350, top+395), radius=12,
                          fill='white', outline='#cbd0d3', width=2)
    with Image.open(OUT / entry['file']) as source:
        tile = source.resize((310, 310), Image.Resampling.LANCZOS)
        preview.paste(tile, (left+20, top+20))
    pen.text((left+20, top+337), f"{entry['id']}   {entry['resolution'][0]}²   {entry['reference_hex']}",
             font=small, fill='#283037')
    pen.text((left+20, top+365), 'предварительно' if entry['status']=='PROVISIONAL' else 'цвет: PDF 18',
             font=small, fill='#677079')
pen.text((38, 1390), 'F10: основной Y40R; дополнительный Y90R в maps/.  Текстуры F9/F9.1 — процедурный моноколор, не скан производителя.',
         font=small, fill='#565e64')
preview.save(OUT / 'contact-sheet.png', optimize=True)
print(json.dumps({'maps': len(entries), 'alternate': alternate.name,
                  'four_k': [e['id'] for e in entries if e['resolution'][0]==4096],
                  'placeholders': sum(e['resolution'][0]==256 for e in entries),
                  'output': str(OUT)}, ensure_ascii=False))

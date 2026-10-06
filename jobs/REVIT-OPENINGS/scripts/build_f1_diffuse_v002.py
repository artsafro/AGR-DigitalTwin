"""Rebuild F1 with three cassette columns and periodic decorative linework."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r'C:\Users\artsafro\Desktop\!3D viz\!Weltbau\5_chertanovo\впм\maps_vpm\F1_Diffuse_4096.png')
OUT = ROOT / 'outputs/diffuse-v002'
OUT.mkdir(parents=True, exist_ok=True)
TARGET = OUT / 'F1_Diffuse_4096_v002.png'

size = 4096
with Image.open(SOURCE) as original:
    assert original.size == (size, size) and original.mode == 'RGB'
    source_color = np.asarray(original)[768:900, 430:560].reshape(-1, 3)
base_rgb = np.median(source_color, axis=0).astype(np.float32)

# 4096 is not divisible by three. These boundaries differ by at most one pixel.
columns = np.rint(np.linspace(0, size, 4)).astype(int)
rows = np.arange(0, size + 1, 512)
rng = np.random.default_rng(1102)
cell_tints = rng.integers(-2, 3, size=(8, 3))
image = np.empty((size, size, 3), dtype=np.uint8)
x = np.arange(size, dtype=np.float32)[None, :]
column_id = np.minimum(np.searchsorted(columns[1:-1], x, side='right'), 2)
column_distance = np.min(np.abs(x[:, :, None] - columns[None, None, :]), axis=2)

# Decorative diagonals remain within a cassette; dark joints mask their ends.
diagonals = {
    0: (0, 2), 1: (1,), 2: (0, 2), 3: (1,),
    4: (0, 2), 5: (1,), 6: (0, 2), 7: (1,),
}
for top in range(0, size, 128):
    bottom = top + 128
    y = np.arange(top, bottom, dtype=np.float32)[:, None]
    row_id = np.minimum((y.astype(int) // 512), 7)
    local_y = y % 512
    noise = rng.normal(0, .48, (128, size)).astype(np.float32)
    low_frequency = .55 * np.sin(2 * np.pi * x / 256) * np.sin(2 * np.pi * y / 256)
    color = base_rgb[None, None, :] + (noise + low_frequency + cell_tints[row_id, column_id])[:, :, None]

    # One soft horizontal white line through the middle of each cassette row.
    horizontal_distance = np.abs(local_y - 256)
    horizontal_alpha = (.58 * np.exp(-.5 * (horizontal_distance / 7.2) ** 2)
                        + .13 * np.exp(-.5 * (horizontal_distance / 18) ** 2))
    color = color * (1 - horizontal_alpha[:, :, None]) + 220 * horizontal_alpha[:, :, None]

    # Faint rising slashes as in the supplied visualization and image edit.
    diagonal_alpha = np.zeros((128, size), dtype=np.float32)
    for row in range(top // 512, (bottom - 1) // 512 + 1):
        row_mask = (row_id == row)
        for col in diagonals[row]:
            left, right = columns[col:col + 2]
            width = right - left
            x_at_y = left + .66 * width - .47 * width * (local_y / 512)
            distance = np.abs(x - x_at_y) / np.sqrt(1 + (.47 * width / 512) ** 2)
            profile = .30 * np.exp(-.5 * (distance / 6.5) ** 2)
            valid = row_mask & (x >= left + 3) & (x < right - 3) & (local_y >= 8) & (local_y <= 504)
            diagonal_alpha = np.maximum(diagonal_alpha, np.where(valid, profile, 0))
    color = color * (1 - diagonal_alpha[:, :, None]) + 218 * diagonal_alpha[:, :, None]

    # The dark joint is centred on the boundary and overrides all light lines.
    row_distance = np.minimum(local_y, 512 - local_y)
    joint = (column_distance < 2.5) | (row_distance < 2.5)
    color = np.where(joint[:, :, None], np.array([85, 85, 85]), color)
    image[top:bottom] = np.clip(np.rint(color), 0, 255).astype(np.uint8)

assert np.array_equal(image[0], image[-1])
assert np.array_equal(image[:, 0], image[:, -1])
Image.fromarray(image, 'RGB').save(TARGET, optimize=True)
with Image.open(TARGET) as check:
    check.load()
    assert check.size == (4096, 4096) and check.mode == 'RGB'
    pixels = np.asarray(check)
    assert np.array_equal(pixels[0], pixels[-1])
    assert np.array_equal(pixels[:, 0], pixels[:, -1])

preview = Image.fromarray(image, 'RGB').resize((1024, 1024), Image.Resampling.LANCZOS)
preview.save(OUT / 'F1_preview_1024.png', optimize=True)
repeated = Image.new('RGB', (2048, 2048))
for px in (0, 1024):
    for py in (0, 1024):
        repeated.paste(preview, (px, py))
repeated.save(OUT / 'F1_repeat_2x2.png', optimize=True)

report = {
    'source': str(SOURCE), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'output': TARGET.name, 'output_sha256': hashlib.sha256(TARGET.read_bytes()).hexdigest(),
    'resolution': [size, size], 'columns': columns.tolist(), 'rows': rows.tolist(),
    'horizontal_lines': 8, 'diagonals': sum(len(v) for v in diagonals.values()),
    'top_bottom_equal': True, 'left_right_equal': True,
    'source_color_median': base_rgb.astype(int).tolist(),
    'method': 'Original F1 grey sampled; image-generation study guided pattern; periodic 4K raster rebuilt for exact tileability',
}
(OUT / 'QA.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))

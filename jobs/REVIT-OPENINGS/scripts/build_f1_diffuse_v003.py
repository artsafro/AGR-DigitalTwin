"""F1: continuous, periodic white stripes over a three-column cassette grid."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r'C:\Users\artsafro\Desktop\!3D viz\!Weltbau\5_chertanovo\впм\maps_vpm\F1_Diffuse_4096.png')
OUT = ROOT / 'outputs/diffuse-v003'
OUT.mkdir(parents=True, exist_ok=True)
TARGET = OUT / 'F1_Diffuse_4096_v003.png'
N = 4096
PERIOD = N - 1  # first and last texels are identical by construction

with Image.open(SOURCE) as original:
    assert original.size == (N, N) and original.mode == 'RGB'
    base = float(np.median(np.asarray(original)[768:900, 430:560]))

image = np.empty((N, N, 3), dtype=np.uint8)
rng = np.random.default_rng(1103)
x = np.arange(N, dtype=np.float32)[None, :]

def cyc_distance(phase):
    return np.abs(phase - np.rint(phase))

for top in range(0, N, 128):
    y = np.arange(top, top + 128, dtype=np.float32)[:, None]
    u = x / PERIOD
    v = y / PERIOD
    panel_x = 3 * u
    panel_y = 8 * v
    tint_index_x = np.minimum((panel_x.astype(int)), 2)
    tint_index_y = np.minimum((panel_y.astype(int)), 7)
    # All low-frequency variation is periodic. The random texture is hidden at
    # the outer cassette joints and cannot create a visible tile-edge mismatch.
    noise = rng.normal(0, .42, (128, N)).astype(np.float32)
    smooth = .55 * np.sin(2 * np.pi * 16 * u) * np.sin(2 * np.pi * 16 * v)
    tint = ((tint_index_x * 3 + tint_index_y * 5) % 5 - 2).astype(np.float32)
    plain = np.broadcast_to(base + noise + smooth + tint, (128, N)).copy()

    grid_x = cyc_distance(panel_x) * (PERIOD / 3)
    grid_y = cyc_distance(panel_y) * (PERIOD / 8)
    grid = (grid_x < 2.5) | (grid_y < 2.5)
    grey = np.where(grid, 85., plain)

    # Eight unbroken horizontal stripes, one through each cassette row.
    h_px = cyc_distance(panel_y - .5) * (PERIOD / 8)
    h_alpha = .68 * np.exp(-.5 * (h_px / 7.5) ** 2)
    h_alpha += .15 * np.exp(-.5 * (h_px / 18) ** 2)

    # Two global diagonals. 2*u+v has an integer phase offset on every outer
    # boundary, so each stroke continues exactly on the adjacent texture tile.
    diagonal_phase = 2 * u + v - .22
    d_px = cyc_distance(diagonal_phase) * (PERIOD / np.sqrt(5))
    d_alpha = .55 * np.exp(-.5 * (d_px / 7) ** 2)
    d_alpha += .06 * np.exp(-.5 * (d_px / 19) ** 2)

    alpha = np.maximum(h_alpha, d_alpha)
    lit = plain * (1 - alpha) + 220. * alpha
    # The solid white strokes cover the dark cassette joints without a gap.
    value = np.where(alpha >= .17, lit, grey * (1 - alpha) + 220. * alpha)
    value = np.clip(np.rint(value), 0, 255).astype(np.uint8)
    image[top:top + 128] = value[:, :, None]

# Exact equality is stronger than merely having a mathematically periodic
# formula: it also eliminates rounding differences at the last raster pixel.
image[-1] = image[0]
image[:, -1] = image[:, 0]
assert np.array_equal(image[0], image[-1])
assert np.array_equal(image[:, 0], image[:, -1])
Image.fromarray(image, 'RGB').save(TARGET, optimize=True)

with Image.open(TARGET) as check:
    check.load()
    assert check.size == (N, N) and check.mode == 'RGB'
    pixels = np.asarray(check)
    assert np.array_equal(pixels[0], pixels[-1])
    assert np.array_equal(pixels[:, 0], pixels[:, -1])
    # White horizontals cross the two interior vertical cassette joints.
    for yy in (256, 768, 1280, 1792, 2304, 2816, 3328, 3840):
        for xx in (1365, 2730):
            assert int(pixels[yy, xx, 0]) > 155

preview = Image.fromarray(image, 'RGB').resize((1024, 1024), Image.Resampling.LANCZOS)
preview.save(OUT / 'F1_preview_1024.png', optimize=True)
repeated = Image.new('RGB', (2048, 2048))
for px in (0, 1024):
    for py in (0, 1024):
        repeated.paste(preview, (px, py))
repeated.save(OUT / 'F1_repeat_2x2.png', optimize=True)

qa = {
    'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'output_sha256': hashlib.sha256(TARGET.read_bytes()).hexdigest(),
    'resolution': [N, N], 'column_count': 3, 'row_count': 8,
    'horizontal_stripes': 8, 'diagonal_stripes': 2,
    'horizontal_joint_crossings': 16, 'opposite_edges_identical': True,
    'source_base_median': base,
    'method': 'Image-generated continuous-line study; exact 4K periodic raster and readback',
}
(OUT / 'QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(qa, ensure_ascii=False))

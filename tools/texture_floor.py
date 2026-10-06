"""Bake approved-size procedural finish previews into existing metric UV layouts.

No geometry edits. Colors remain PDF-preview candidates, not product samples.
"""
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image


RECIPE = {
    'status': 'procedural working textures; dimensions approved in chat, colors are candidates',
    'brick': {'face_m': [.250, .065], 'joint_m': .010, 'bond': 'half running bond'},
    'tile': {'face_m': [.600, 1.200], 'joint_m': .005, 'orientation': 'long side vertical'},
    'finish_ids': {'2': 'light tile', '4': 'gray tile', '5': 'brick'},
    'color_source': 'existing PDF 14-15 palette preview; not calibrated RAL',
    'maps': ['Diffuse'],
    'limits': 'No measured PBR/normal maps. ID0 unresolved faces preserved. Not delivery-ready.',
}


def pattern(s, t, ident):
    """Sample a globally phased pattern in physical meters (face size excludes joint)."""
    brick = ident == 5
    w, h, joint = (.250, .065, .010) if brick else (.600, 1.200, .005)
    pw, ph = w + joint, h + joint
    row = np.floor(t / ph)
    shifted = s + (np.mod(row, 2) * pw / 2 if brick else 0)
    col = np.floor(shifted / pw)
    mortar = (np.mod(shifted, pw) < joint) | (np.mod(t, ph) < joint)
    variation = (np.mod(np.sin(col * 12.9898 + row * 78.233) * 43758.5453, 1) - .5)
    base = np.array({2: [214, 214, 214], 4: [106, 106, 114], 5: [181, 154, 143]}[ident])
    rgb = base + variation[..., None] * (12 if brick else 5)
    seam = np.array([117, 112, 108] if brick else ([158, 158, 158] if ident == 2 else [62, 63, 68]))
    return np.where(mortar[..., None], seam, rgb)


def projection(q):
    axis = int(np.argmin(np.ptp(q, axis=0)))
    axes = [a for a in range(3) if a != axis]
    raw = q[:, axes].copy()
    sign = 1 if np.sum(raw[:, 0]*np.roll(raw[:, 1], -1)-np.roll(raw[:, 0], -1)*raw[:, 1]) >= 0 else -1
    raw[:, 0] *= sign
    return axes, sign, raw.min(0)


def bake(root):
    source = root / 'uv_trial'
    out = root / 'textured_v010'
    out.mkdir(exist_ok=True)
    manifest = json.loads((source / 'uv-manifest.json').read_text(encoding='utf-8'))
    report = {'recipe': RECIPE, 'variants': {}}
    for variant, layout in manifest['layouts'].items():
        size, pad = layout['size'], layout['padding']
        meshes = manifest['vpm_meshes' if variant == 'VPM_UDIM' else 'meshes']
        entries = layout['entries']
        samples = 4 if variant == 'NPM_ATLAS' else 2
        paths = []
        for ti, udim in enumerate(layout['tiles']):
            canvas = np.zeros((size, size, 3), dtype=np.uint8)
            for e in entries:
                if e['tile'] != ti or (variant == 'VPM_UDIM' and e['finish_id'] == 90):
                    continue
                x0, y0 = e['x'] - pad, e['y'] - pad
                x1, y1 = e['x'] + e['width'] + pad, e['y'] + e['height'] + pad
                ident = e['finish_id']
                if ident not in (2, 4, 5):
                    canvas[size-y1:size-y0, x0:x1] = manifest['palette'][str(ident)]
                    continue
                mesh = meshes[e['mesh']]
                q = np.array(mesh['vertices'])[mesh['faces'][e['face']]]
                axes, sign, minimum = projection(q)
                # Project physical coordinates back from the unmodified per-face UV.
                # Shared plane coordinates retain phase across opening and Connect cuts.
                for bottom in range(y0, y1, 96):
                    top = min(bottom + 96, y1)
                    acc = np.zeros((top-bottom, x1-x0, 3), dtype=np.float64)
                    for sy in range(samples):
                        for sx in range(samples):
                            a = (np.arange(x0, x1)[None, :] + (sx+.5)/samples-e['x']) / e['density'] + minimum[0]
                            b = (np.arange(bottom, top)[:, None] + (sy+.5)/samples-e['y']) / e['density'] + minimum[1]
                            a = a * sign
                            acc += pattern(a, b, ident)
                    pixels = np.clip(np.rint(acc / samples**2), 0, 255).astype(np.uint8)
                    canvas[size-top:size-bottom, x0:x1] = pixels[::-1]
            path = out / f'{variant}_Diffuse.{udim}.png'
            Image.fromarray(canvas).save(path)
            with Image.open(path) as image:
                assert image.size == (size, size) and image.mode == 'RGB'
                assert np.array_equal(np.asarray(image), canvas)
            paths.append(path.name)
            print(variant, udim, 'saved/read back', flush=True)
        report['variants'][variant] = {'size': size, 'padding_px': pad, 'tiles': layout['tiles'], 'files': paths, 'samples_per_pixel': samples**2}
    (out/'texture-recipe.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    bake(Path(sys.argv[1]).resolve())

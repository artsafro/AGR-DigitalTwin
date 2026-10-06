"""Check saved texels against physical geometry through an independent UV inverse."""
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from texture_floor import pattern


root = Path(sys.argv[1]).resolve()
out = root/'textured_v010'
manifest = json.loads((root/'uv_trial/uv-manifest.json').read_text(encoding='utf-8'))
readback = json.loads((root/'uv_trial/blender-uv-readback.json').read_text(encoding='utf-8'))
report = {'scope': 'saved PNG texels at face centers; unchanged v009 UV verified separately by Blender', 'variants': {}}
for variant, layout in manifest['layouts'].items():
    meshes = manifest['vpm_meshes' if variant == 'VPM_UDIM' else 'meshes']
    size = layout['size']
    samples = 4 if variant == 'NPM_ATLAS' else 2
    errors = []
    count = 0
    for ti, udim in enumerate(layout['tiles']):
        with Image.open(out/f'{variant}_Diffuse.{udim}.png') as image:
            assert image.size == (size, size) and image.mode == 'RGB'
            pixels = np.asarray(image)
            for entry in layout['entries']:
                if entry['tile'] != ti or (variant == 'VPM_UDIM' and entry['finish_id'] == 90):
                    continue
                mi, fi, ident = entry['mesh'], entry['face'], entry['finish_id']
                mesh = meshes[mi]
                actual = readback[variant]['meshes'][mi]
                offset = sum(len(f) for f in mesh['faces'][:fi])
                uv = np.array(actual['uv_layers'][variant][offset:offset+4])
                uv -= [ti % 10, ti // 10]
                uv *= size
                px, py = np.floor(uv.mean(0)).astype(int)
                if ident in (2, 4, 5):
                    q = np.array(actual['vertices'])[mesh['faces'][fi]]
                    axes = [a for a in range(3) if a != np.argmin(np.ptp(q, axis=0))]
                    transform = np.linalg.lstsq(np.c_[uv, np.ones(4)], q[:,axes], rcond=None)[0]
                    expected = np.zeros(3)
                    for sy in range(samples):
                        for sx in range(samples):
                            s, t = np.array([px+(sx+.5)/samples, py+(sy+.5)/samples, 1]) @ transform
                            expected += pattern(s, t, ident)
                    expected /= samples**2
                else:
                    expected = np.array(manifest['palette'][str(ident)])
                error = float(np.max(abs(pixels[size-1-py, px].astype(float)-expected)))
                errors.append(error)
                count += 1
    report['variants'][variant] = {'checked_face_centers': count, 'max_rgb_error_255': max(errors), 'within_2_levels': max(errors) <= 2}
    assert max(errors) <= 2, (variant, max(errors))
(out/'texture-pixel-qa.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))

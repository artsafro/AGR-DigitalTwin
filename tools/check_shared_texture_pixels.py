"""Validate actual output pixels, saved hashes, untouched source images and atlas labels."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

out=Path(sys.argv[1]).resolve()
d=json.loads((out/'shared-uv-manifest.json').read_text(encoding='utf-8'))
for r in d['source_images']:
    assert hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256']
atlas=np.array(Image.open(out/'NPM_ATLAS_Diffuse.png'))
original=np.array(Image.open(d['source_images'][-1]['path']))
assert atlas.shape==(2048,2048,3)
assert np.array_equal(atlas[1789:],original[1789:]), 'Bottom sample legend or window reference changed'
assert np.all(atlas[1932:1948,1928:1944]==[69,73,78]), 'Frame swatch is not flat RAL7024 preview'
report={'source_images_unchanged':True,'atlas_bottom_reference_unchanged':True,'tiles':[]}
for tile in range(1001,1005):
    path=out/f'VPM_Diffuse.{tile}.png'
    with Image.open(path) as im:
        assert im.size==(4096,4096) and im.mode=='RGB'
        a=np.array(im)
    brick=tile==1004
    pitch=.260 if brick else .605
    joint=.010 if brick else .005
    # Scan the first module midway through a face, measure dark mortar in saved PNG.
    row=4096-1-int(.03*1024)
    scan=a[row,:int(pitch*1024)].mean(1)
    threshold=(float(scan.min())+float(np.median(scan)))/2
    measured=int(np.count_nonzero(scan<threshold))
    assert abs(measured-joint*1024)<=1.1,(tile,measured,joint*1024)
    report['tiles'].append({'tile':tile,'size':[4096,4096],'vertical_joint_width_px':measured,
                            'target_joint_width_px':joint*1024,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(out/'texture-pixel-qa.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PIXEL_READBACK_OK: 4 tiles, original source hashes, atlas bottom, frame swatch, joint widths')

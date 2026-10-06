"""Independent saved-PNG checks of 600/1200 mm spacing and ZIP contents."""
import json,io,zipfile,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
job=Path(__file__).resolve().parents[1]/'jobs/FACADES-ATLAS'
out=job/'outputs/metric-v005'
archive=out/'Facades_3_Atlases_5_Textures_2K_v005.zip'
result={}
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    files=[n for n in z.namelist() if n.endswith('.png')]
    assert len(files)==8 and sum(n.startswith('Atlases/') for n in files)==3
    for name in files:
        data=z.read(name);im=Image.open(io.BytesIO(data));im.load()
        assert im.size==(2048,2048)
        a=np.asarray(im.convert('RGB'))
        if name.startswith('Textures_2K/'):
            assert np.array_equal(a[0],a[-1]) and np.array_equal(a[:,0],a[:,-1])
            brick='ID101_' in name
            sx,sy=(512,256) if brick else (256,512)
            # Sample saved raster away from brick bed joints; both grid directions.
            line_x=a[101,:,:].mean(1);line_y=a[:,101,:].mean(1)
            for line,step in ((line_x,sx),(line_y,sy)):
                for pos in range(step,2048,step):
                    assert line[pos-1:pos+1].mean()<line[pos+8:pos+16].mean()*.7,(name,pos)
        result[name]={'sha256':hashlib.sha256(data).hexdigest(),'size':list(im.size)}
(job/'v005-package-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('ZIP: 3 atlases + 5 maps; 2048px; edges match; 600/1200mm raster spacing verified')

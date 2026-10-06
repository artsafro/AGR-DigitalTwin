"""Package exactly three atlases and five common visualization maps; read back ZIP."""
from pathlib import Path
import json, shutil, zipfile, io, hashlib
import numpy as np
from PIL import Image

root=Path(__file__).resolve().parents[1]
job=root/'jobs/FACADES-ATLAS';out=job/'outputs/metric-v004'
package=out/'Delivery_3_atlases_5_textures';package.mkdir(exist_ok=True)
for sub in ('Atlases','Textures_2K'):(package/sub).mkdir(exist_ok=True)
for f in out.glob('T_Facades_*_Atlas_d.png'):shutil.copyfile(f,package/'Atlases'/f.name)
for mid in range(101,106):
    filename=f'ID{mid}_BaseColor_2K_4800x4800mm.png'
    source=out/'Textures_2K'/filename
    if not source.exists():source=out/'Textures_2K/Corpus_01'/filename
    shutil.copyfile(source,package/'Textures_2K'/filename)
(package/'README.txt').write_text('Состав: 3 атласа корпусов + 5 общих бесшовных текстур 2048x2048.\nAtlases: только для готовых UV модели facades_metric_v004.blend.\nTextures_2K: Base Color/Diffuse, sRGB. Каждая карта покрывает 4800x4800мм.\nВ визуализации включить Repeat и задать UVW 4800x4800мм.\nID101: кирпич250x65мм+шов10мм; горизонтальные панели1600x1200мм.\nID102: светлая; ID103: светло-серая; ID104: тёмно-серая; ID105: тёплая тёмная первого этажа.\nID102-105: вертикальные панели1200x1600мм. Шов панелей5мм внутри номинальных размеров.\nОбщий набор использует оттенки корпуса01. Атласы сохраняют индивидуальные оттенки.\nВ атласе кирпичные стыки визуально усилены до1px (12.5мм), в отдельных картах шов5мм.\nNormal/Roughness/Displacement не входят в набор.\n',encoding='utf-8')
archive=Path(shutil.make_archive(str(out/'Facades_3_Atlases_5_Textures_2K'),'zip',package))
report={'png_count':0,'maps':{},'accepted_tile_bands_unchanged':{},'archive':str(archive)}
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    pngs=[n for n in z.namelist() if n.endswith('.png')]
    assert len(pngs)==8 and sum(n.startswith('Atlases/') for n in pngs)==3
    for name in pngs:
        image=Image.open(io.BytesIO(z.read(name)));image.load()
        assert image.size==(2048,2048)
        a=np.asarray(image.convert('RGB'))
        if name.startswith('Textures_2K/'):
            # At the crop boundaries all four sides lie in the centered panel joint.
            assert np.max(np.abs(a[0].astype(int)-a[-1].astype(int)))==0
            assert np.max(np.abs(a[:,0].astype(int)-a[:,-1].astype(int)))==0
            if 'ID101_' in name:
                # y=1.2m horizontal panel joint inside the saved PNG, not the generator.
                seam=a[1535:1537,100:1900].mean()
                interior=a[1510:1520,100:1900].mean()
                assert seam<interior*.5,(seam,interior)
        report['maps'][name]={'size':list(image.size),'sha256':hashlib.sha256(z.read(name)).hexdigest()}
    report['png_count']=len(pngs)
for cid in ('01','02','03'):
    filename=f'T_Facades_{cid}_Atlas_d.png'
    old=np.array(Image.open(job/'outputs/metric-v003'/filename))
    new=np.array(Image.open(out/filename))
    assert np.array_equal(old[:1728],new[:1728]),cid
    report['accepted_tile_bands_unchanged'][cid]=True
(job/'texture-package-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ZIP readback OK: 3 atlases + 5 seamless 2048 maps; tile bands unchanged')

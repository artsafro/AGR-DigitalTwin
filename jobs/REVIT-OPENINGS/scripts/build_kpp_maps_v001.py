"""Create the user-specified KPP diffuse UDIM tiles and read them back."""
from pathlib import Path
import hashlib
import json
import zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/maps_kpp_v001'
INFO = OUT / '_info'
INFO.mkdir(parents=True, exist_ok=True)
SOURCE = Path(r'C:\Users\artsafro\AppData\Local\Temp\codex-clipboard-d4f55aaf-0b16-40e5-9367-722d337f097c.png')
legend = np.asarray(Image.open(SOURCE).convert('RGB'))
def sample(x, y):
    return tuple(int(v) for v in np.median(legend[y-8:y+8,x-8:x+8].reshape(-1,3),axis=0))
yellow, white, coral, grey, gold = [sample(x,y) for x,y in [(50,173),(50,82),(50,268),(830,170),(830,365)]]
anthracite = (62,67,73)  # same RAL7016 reference as the main school register
specs = [
    (1,'Жёлтые панели со швами','NCS S 2030-Y20R',4096,yellow),
    (2,'Белые рамы','NCS S 700-N',256,white),
    (3,'Жёлтый металл','RAL 1002',256,gold),
    (4,'Интерьер','RAL 7001',256,grey),
    (5,'Металлические декоративные плашки','NCS S 2030-Y20R',4096,yellow),
    (6,'Металл','RAL 7016',256,anthracite),
    (7,'Кровля','RAL 7001',256,grey),
    (8,'Рамы','RAL 7016',256,anthracite),
    (9,'Стемалит','RAL 7001',256,grey),
    (10,'Красные рамки','NCS S 1060-Y90R',256,coral),
    (11,'Стекло','RGB 255 255 255',256,(255,255,255)),
]

N=4096
panels=np.empty((N,N,3),dtype=np.uint8)
x=np.arange(N,dtype=np.float32)[None,:]
rng=np.random.default_rng(2030)
seams=np.array([0,1365,2731,4096])
dx=np.min(np.abs(x[:,:,None]-seams[None,None,:]),axis=2)
col=np.searchsorted(seams[1:-1],x,side='right')
tints=np.array([[0,1,-1],[1,-1,0],[-1,0,1],[0,-1,0],[1,0,-1],[0,1,0],[-1,0,1],[0,-1,1]])
for top in range(0,N,128):
    y=np.arange(top,top+128,dtype=np.float32)[:,None]
    dy=np.minimum(y%512,512-y%512)
    noise=rng.normal(0,.45,(128,N))
    tone=noise+tints[(y.astype(int)//512),col]
    rgb=np.array(yellow,dtype=float)[None,None,:]+tone[:,:,None]
    # Neutral warm joint, not an illuminated/shaded bevel.
    joint=np.array(yellow,dtype=float)*.73
    rgb=np.where(((dx<2.5)|(dy<2.5))[:,:,None],joint,rgb)
    panels[top:top+128]=np.clip(np.rint(rgb),0,255).astype(np.uint8)
panels[-1]=panels[0]
panels[:,-1]=panels[:,0]

entries=[]
for ident,name,code,size,color in specs:
    path=OUT/f'{1000+ident}.png'
    img=Image.fromarray(panels,'RGB') if ident==1 else Image.new('RGB',(size,size),color)
    img.save(path,optimize=True)
    with Image.open(path) as readback:
        readback.load()
        assert readback.mode=='RGB' and readback.size==(size,size)
        a=np.asarray(readback)
        assert np.array_equal(a[0],a[-1]) and np.array_equal(a[:,0],a[:,-1])
        if ident!=1:
            assert np.all(a==np.array(color))
    entries.append({'id':ident,'udim':1000+ident,'file':path.name,'name':name,
                    'code':code,'size':[size,size],'rgb':color,
                    'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
assert len(list(OUT.glob('*.png')))==11
manifest={'color_space':'sRGB','material_maps':'diffuse/base color',
          'source_legend_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
          'color_note':'RGB sampled from supplied legend, not certified NCS/RAL conversion; RAL7016 reused from school register',
          '1002_note':'User requested white frames; light F.1 swatch takes priority over ambiguous NCS S 700-N code',
          '1001_note':'Three columns and eight rows, working layout; physical panel size not specified',
          '1005_note':'Solid yellow metal; actual gaps and shape belong to slat geometry',
          '1011_note':'White diffuse only; transparency/IOR/roughness require shader settings',
          'maps':entries,'qa':{'maps_read_back':11,'sizes_correct':True,'opposite_edges_equal':True}}
(INFO/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(INFO/'README.txt').write_text('КПП: 1001.png–1011.png, sRGB.\n1001 и 1005 — 4096×4096; остальные — 256×256.\n1001: панели 3×8, физический размер пока не задан. 1005: сплошной жёлтый металл.\nЦвета из приложенной легенды, не точное лабораторное преобразование NCS/RAL.\n1002: светлая плашка Ф.1 по указанию «белые рамы», код NCS S 700-N неоднозначен.\n1011 — белый diffuse; прозрачность стекла настраивается материалом.\nСоответствие ID и хеши: manifest.json.\n',encoding='utf-8')
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
preview=Image.new('RGB',(1500,1150),'#f1f2f3')
draw=ImageDraw.Draw(preview)
draw.text((25,15),'КПП — карты UDIM 1001–1011',font=font,fill='#24282c')
for idx,e in enumerate(entries):
    xx=25+(idx%4)*370; yy=65+(idx//4)*355
    with Image.open(OUT/e['file']) as img:
        preview.paste(img.resize((320,250),Image.Resampling.LANCZOS),(xx,yy))
    draw.rectangle((xx,yy,xx+320,yy+250),outline='#a0a0a0')
    draw.text((xx,yy+257),f"{e['udim']}  |  {e['size'][0]}²",font=font,fill='#24282c')
    draw.text((xx,yy+286),e['name'],font=small,fill='#42474b')
    draw.text((xx,yy+311),e['code'],font=small,fill='#42474b')
preview.save(INFO/'preview.png',optimize=True)
zip_path=OUT.parent/'KPP_UDIM_maps_v001.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in OUT.rglob('*'):
        if path.is_file(): archive.write(path,path.relative_to(OUT))
with zipfile.ZipFile(zip_path) as archive:
    assert archive.testzip() is None
    for e in entries:
        assert hashlib.sha256(archive.read(e['file'])).hexdigest()==e['sha256']
print(json.dumps({'maps':len(entries),'output':str(OUT),'zip':str(zip_path),'colors':{'yellow':yellow,'white':white,'gold':gold,'grey':grey,'coral':coral}},ensure_ascii=False))

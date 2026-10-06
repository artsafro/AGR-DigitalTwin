"""Open v003 in Blender; preserve accepted tiles, fix brick and export periodic 2K maps."""
import bpy, sys, json, shutil
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
from facades_texture_pattern import raster

source=Path(sys.argv[sys.argv.index('--')+1]).resolve()
out=Path(sys.argv[sys.argv.index('--')+2]).resolve()
out.mkdir(parents=True,exist_ok=False)
manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
package=out/'Textures_2K';package.mkdir()
manifest['brick_panel_joint_atlas_visual_m']=.0125
manifest['brick_panel_joint_export_m']=.005
manifest['texture_export_extent_m']=[4.8,4.8]
exports=[]
for name,meta in manifest['objects'].items():
    cid=meta['corpus'];o=bpy.data.objects[name]
    img=next(n.image for n in o.data.materials[100].node_tree.nodes if n.type=='TEX_IMAGE')
    arr=np.array(img.pixels[:],dtype=np.float32).reshape(2048,2048,4)
    x,y,w,h=manifest['regions_px']['101'];pad=16;D=manifest['sampling_px_m']
    arr[y-pad:y+h+pad,x-pad:x+w+pad,:3]=raster(101,w+pad*2,h+pad*2,((w+pad*2)/D,(h+pad*2)/D),meta['base_colors']['101'],.0125,(-pad/D,-pad/D))
    img.pixels.foreach_set(arr.ravel());img.update()
    img.filepath_raw=str(out/f'T_Facades_{cid}_Atlas_d.png');img.save();img.pack()
    img.filepath_raw='//'+Path(img.filepath_raw).name
    shutil.copyfile(source/meta['records_file'],out/meta['records_file'])
    folder=package
    for mid in (range(101,106) if cid=='01' else []):
        rgb=raster(mid,2048,2048,(4.8,4.8),meta['base_colors'][str(mid)])
        rgba=np.ones((2048,2048,4),dtype=np.float32);rgba[:,:,:3]=rgb
        tex=bpy.data.images.new(f'Export_{cid}_{mid}',width=2048,height=2048,alpha=False)
        tex.colorspace_settings.name='sRGB';tex.pixels.foreach_set(rgba.ravel())
        tex.filepath_raw=str(folder/f'ID{mid}_BaseColor_2K_4800x4800mm.png')
        tex.file_format='PNG';tex.save();bpy.data.images.remove(tex)
        exports.append({'reference_corpus':cid,'id':mid,'extent_m':[4.8,4.8],'resolution':[2048,2048]})
    o['atlas_recipe']='FACADES-ATLAS/metric-v004'
    print('FINISHED',name,flush=True)
(package/'manifest.json').write_text(json.dumps(exports,indent=2),encoding='utf-8')
(package/'README.txt').write_text('Бесшовные Base Color / Diffuse, sRGB, PNG 2048x2048.\nКаждая карта покрывает 4800 x 4800 мм: назначьте именно этот размер UVW.\nID101: панели 1600x1200 мм (3 по ширине, 4 по высоте), кирпич 250x65 мм, шов10мм.\nID102-105: панели1200x1600мм (4 по ширине, 3 по высоте).\nШов панелей5мм входит в номинальные размеры; края карты лежат по середине стыка.\nОдин общий набор из пяти карт, оттенки корпуса01.\nТолько цветовые карты, без Normal/Roughness/Displacement.\nВ атласе модели кирпичные стыки усилены до1пикселя для читаемости; здесь физический шов5мм.\n',encoding='utf-8')
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.data.texts['ATLAS_RECIPE.json'].clear();bpy.data.texts['ATLAS_RECIPE.json'].write(json.dumps(manifest,ensure_ascii=False,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(out/'facades_metric_v004.blend'))
shutil.make_archive(str(out/'Facades_Textures_2K'),'zip',package)

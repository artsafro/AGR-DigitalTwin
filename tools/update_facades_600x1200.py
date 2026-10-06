"""Blender: v004 -> new v005, updated panels and phase-preserving UV folds."""
import bpy,sys,json,shutil
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
from facades_texture_pattern import raster
source=Path(sys.argv[sys.argv.index('--')+1]).resolve()
out=Path(sys.argv[sys.argv.index('--')+2]).resolve();out.mkdir(parents=True,exist_ok=False)
manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
manifest['panel_dimensions_m']={str(i):([1.2,.6] if i==101 else [.6,1.2]) for i in range(101,106)}
package=out/'Delivery_3_atlases_5_textures'
for sub in ('Atlases','Textures_2K'):(package/sub).mkdir(parents=True)
D=manifest['sampling_px_m'];N=manifest['atlas_size']
for name,meta in manifest['objects'].items():
    o=bpy.data.objects[name];cid=meta['corpus'];m=o.data
    records=json.loads((source/meta['records_file']).read_text())
    world=np.array([o.matrix_world@v.co for v in m.vertices]);origin=np.array(meta['origin_m'])
    uv=m.uv_layers[meta['new_uv_layer']]
    for p,r in zip(m.polygons,records):
        mid=str(p.material_index+1);period=np.array(manifest['panel_dimensions_m'][mid])
        q=world[list(p.vertices)]-origin
        xy=np.stack((q@np.array(r['tangent']),q@np.array(r['vertical'])),axis=1)
        shift=np.floor((xy.min(0)+1e-9)/period)*period;fold=xy-shift
        for a in range(2):
            if fold[:,a].min()<-1e-8:fold[:,a]+=period[a];shift[a]-=period[a]
        x,y,w,h=manifest['regions_px'][mid]
        assert (fold.min(0)>=-1e-7).all() and (fold.max(0)*D<=np.array([w,h])+1e-5).all()
        for li,value in zip(p.loop_indices,(fold*D+np.array([x,y]))/N):uv.data[li].uv=value
        r['shift_m']=shift.tolist()
    (out/meta['records_file']).write_text(json.dumps(records),encoding='utf-8')
    img=next(n.image for n in m.materials[100].node_tree.nodes if n.type=='TEX_IMAGE')
    arr=np.array(img.pixels[:],dtype=np.float32).reshape(N,N,4)
    for mid in range(101,106):
        x,y,w,h=manifest['regions_px'][str(mid)];pad=16
        arr[y-pad:y+h+pad,x-pad:x+w+pad,:3]=raster(mid,w+32,h+32,((w+32)/D,(h+32)/D),meta['base_colors'][str(mid)],.0125 if mid==101 else .005,(-pad/D,-pad/D),manifest['panel_dimensions_m'][str(mid)])
    img.pixels.foreach_set(arr.ravel());img.update()
    filename=f'T_Facades_{cid}_Atlas_d.png';img.filepath_raw=str(out/filename);img.save();img.pack();img.filepath_raw='//'+filename
    shutil.copyfile(out/filename,package/'Atlases'/filename)
    if cid=='01':
        for mid in range(101,106):
            rgb=raster(mid,N,N,(4.8,4.8),meta['base_colors'][str(mid)],panel_dimensions=manifest['panel_dimensions_m'][str(mid)])
            rgba=np.ones((N,N,4),dtype=np.float32);rgba[:,:,:3]=rgb
            tex=bpy.data.images.new(f'Export_{mid}',width=N,height=N,alpha=False)
            tex.colorspace_settings.name='sRGB';tex.pixels.foreach_set(rgba.ravel())
            tex.filepath_raw=str(package/'Textures_2K'/f'ID{mid}_BaseColor_2K_4800x4800mm.png');tex.file_format='PNG';tex.save();bpy.data.images.remove(tex)
    o['atlas_recipe']='FACADES-ATLAS/metric-v005'
    print('FINISHED',name,flush=True)
(package/'README.txt').write_text('3 атласа для UV модели +5общих бесшовных BaseColor(sRGB) 2048x2048.\nКаждая отдельная текстура: UVW4800x4800мм, Repeat.\nID101: горизонтальные панели1200x600мм (4x8панелей на карту). Кирпич250x65мм, шов10мм.\nID102-105: вертикальные панели600x1200мм (8x4панелей на карту).\nID102 светлая,103 светло-серая,104 тёмно-серая,105 тёплая тёмная.\nШов панелей5мм внутри модуля; в атласе кирпичный стык усилен до1px для читаемости.\nОбщий набор оттенков корпуса01. Normal/Roughness не входят.\n',encoding='utf-8')
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.data.texts['ATLAS_RECIPE.json'].clear();bpy.data.texts['ATLAS_RECIPE.json'].write(json.dumps(manifest,ensure_ascii=False,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(out/'facades_metric_v005.blend'))
shutil.make_archive(str(out/'Facades_3_Atlases_5_Textures_2K_v005'),'zip',package)

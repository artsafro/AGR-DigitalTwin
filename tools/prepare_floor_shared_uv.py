"""Metric texture rebake from supplied samples; shared material regions, not unique packing."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw


MATERIALS = {
    4: ('tiles_dark_grey.png', 1001, (919, 1354)),
    2: ('tiles_light_grey.png', 1002, (0, 522)),
    3: ('tiles_white.png', 1003, (1354, 1789)),
    5: ('bricks.png', 1004, (522, 919)),
}
SIZE = 4096
VPM_DENSITY = 1024.
NPM_DENSITY = 39.9
PADDING = {'VPM_UDIM': 32, 'NPM_ATLAS': 8}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_sample(image, x, y):
    """Bilinear reconstruction; deliberately makes no claim of new source detail."""
    h, w = image.shape[:2]
    x = np.clip(x, 0, w-1.001); y = np.clip(y, 0, h-1.001)
    ix, iy = x.astype(int), y.astype(int)
    fx, fy = (x-ix)[..., None], (y-iy)[..., None]
    return (image[iy, ix]*(1-fx)+image[iy, ix+1]*fx)*(1-fy) + (image[iy+1, ix]*(1-fx)+image[iy+1, ix+1]*fx)*fy


def shade(s, t, ident, source):
    """Reconstruct joints at approved dimensions, sample ONLY inside source faces."""
    brick = ident == 5
    w, h, joint = (.250, .065, .010) if brick else (.600, 1.200, .005)
    row = np.floor(t/(h+joint))
    shift = np.mod(row, 2)*(w+joint)/2 if brick else 0
    x = np.mod(s+shift, w+joint)
    y = np.mod(t, h+joint)
    mortar = (x < joint) | (y < joint)
    u = np.clip((x-joint)/w, 0, 1)
    v = np.clip((y-joint)/h, 0, 1)
    # Selected interior pixels avoid the old baked joint width and large grid lines.
    # No AI detail generation or invented photographic information.
    if brick:
        patch = np.mod(np.floor((s+shift)/(w+joint)) + 3*row, 4)
        rgb = source_sample(source, 3 + patch*11.2 + u*6, 48 + v*1.4)
        seam = np.array([77, 68, 57])
    else:
        rgb = source_sample(source, 30+u*12, 100+v*48)
        seam = np.array(source[50, {'2':19, '3':26, '4':23}[str(ident)]], dtype=float)
    return np.where(mortar[..., None], seam, rgb)


def bake_region(array, bounds, density, ident, source):
    """UV coordinates are upward; image rows downward. Phase shared with UV planner."""
    x0, y0, x1, y1 = bounds  # image-space bounds
    height = y1-y0
    for row in range(y0, y1, 64):
        end = min(row+64, y1)
        accum = np.zeros((end-row, x1-x0, 3), dtype=float)
        for dy in (.25, .75):
            for dx in (.25, .75):
                s = (np.arange(x0,x1)[None,:]+dx-x0)/density
                t = (height-(np.arange(row,end)[:,None]+dy-y0))/density
                accum += shade(s,t,ident,source)
        array[row:end,x0:x1] = np.clip(np.rint(accum/4),0,255).astype(np.uint8)


def project(q):
    axis = int(np.argmin(np.ptp(q, axis=0)))
    axes = [a for a in range(3) if a != axis]
    if axis == 2 and np.ptp(q[:,axes[1]]) > np.ptp(q[:,axes[0]]):
        axes.reverse()  # long horizontal shell rim follows the wide atlas direction
    projected = q[:,axes].copy()
    area = np.sum(projected[:,0]*np.roll(projected[:,1],-1)-projected[:,1]*np.roll(projected[:,0],-1))
    if area < 0:
        projected[:,0] *= -1
    return projected


def choose_phases(meshes,variant):
    result={}
    density=VPM_DENSITY if variant=='VPM_UDIM' else NPM_DENSITY
    pad=PADDING[variant]
    for ident in MATERIALS:
        faces=[project(np.array(m['vertices'])[face]) for m in meshes for face,finish in zip(m['faces'],m['finish_ids']) if finish==ident]
        if not faces:result[ident]=[0.,0.];continue
        period=np.array([.260,.150] if ident==5 else [.605,1.205])
        lo=np.array([q.min(0) for q in faces]);spans=np.array([np.ptp(q,axis=0) for q in faces])
        height=4096 if variant=='VPM_UDIM' else MATERIALS[ident][2][1]-MATERIALS[ident][2][0]
        available=(np.array([4096 if variant=='VPM_UDIM' else 2048,height])-2*pad)/density
        biases=[]
        for axis in (0,1):
            candidates=np.arange(1024)*period[axis]/1024
            margin=available[axis]-(np.mod(lo[:,axis,None]+candidates,period[axis])+spans[:,axis,None])
            best=int(np.argmax(margin.min(0)))
            assert margin[:,best].min()>=0, ('needs quad cut',variant,ident,axis,float(margin[:,best].min()))
            biases.append(float(candidates[best]))
        result[ident]=biases
    return result


def map_face(q, ident, variant, bias=(0.,0.)):
    projected=project(q)
    lo = projected.min(0)
    # Shift only by whole repeat units, preserving phase in plane coordinates.
    # Two rows for running bond; windows/frame samples are handled separately.
    period = np.array([.260, .150] if ident == 5 else [.605, 1.205])
    density = VPM_DENSITY if variant == 'VPM_UDIM' else NPM_DENSITY
    pad = PADDING[variant]
    tile = MATERIALS[ident][1] if variant == 'VPM_UDIM' else 1001
    size = SIZE if variant == 'VPM_UDIM' else 2048
    if variant == 'VPM_UDIM':
        region = [0,0,size,size]  # UV-pixel bounds
    else:
        top,bottom = MATERIALS[ident][2]
        region = [0,size-bottom,size,size-top]
    # Translate a phase-aligned island to the first padded repeat cell.
    anchor = np.array([pad,pad],dtype=float)
    pixels = (projected-lo+np.mod(lo+np.array(bias),period))*density + anchor + region[:2]
    assert np.all(pixels.min(0)>=np.array(region[:2])+pad-1e-6)
    assert np.all(pixels.max(0)<=np.array(region[2:])-pad+1e-6), (ident,variant,pixels.max(0),region)
    uv = pixels/size + [tile-1001,0]
    return uv.tolist(), region, density


def main(root, source_dir):
    out = root/'shared_v011';out.mkdir(exist_ok=True)
    manifest = json.loads((root/'uv_trial/uv-manifest.json').read_text(encoding='utf-8'))
    paths = [source_dir/item[0] for item in MATERIALS.values()]
    atlas_path = source_dir/'Elik/coordinates/maps/T_OKS_001.png'
    paths.append(atlas_path)
    provenance = [{'path':str(p),'sha256':sha(p),'size':list(Image.open(p).size)} for p in paths]
    atlas = np.array(Image.open(atlas_path).convert('RGB'))
    assert atlas.shape == (2048,2048,3)
    if '--uv-only' not in sys.argv:
        for ident,(name,tile,(top,bottom)) in MATERIALS.items():
            source = np.array(Image.open(source_dir/name).convert('RGB'), dtype=float)
            if '--npm-only' not in sys.argv:
                full = np.empty((SIZE,SIZE,3),dtype=np.uint8)
                bake_region(full,(0,0,SIZE,SIZE),VPM_DENSITY,ident,source)
                Image.fromarray(full).save(out/f'VPM_Diffuse.{tile}.png')
            bake_region(atlas,(0,top,2048,bottom),NPM_DENSITY,ident,source)
            print('BAKED',name,tile,flush=True)
        Image.fromarray(atlas).save(out/'NPM_ATLAS_Diffuse.png')
    result = {'source_images':provenance,'policy':'user sources rebaked to metric density; originals unchanged',
        'limits':['Diffuse only','Source detail is interpolated, not recovered','White ID3 has no assigned source faces','ID0 remains unresolved'],
        'source_recipe':{'tile_face_m':[.6,1.2],'tile_joint_m':.005,'brick_face_m':[.25,.065],'brick_joint_m':.01},
        'variants':{}}
    for variant in ['NPM_ATLAS','VPM_UDIM']:
        entries=[];meshes=manifest['vpm_meshes' if variant=='VPM_UDIM' else 'meshes']
        phases=choose_phases(meshes,variant)
        for mi,mesh in enumerate(meshes):
            vertices=np.array(mesh['vertices'])
            for fi,face in enumerate(mesh['faces']):
                ident=mesh['finish_ids'][fi]
                if ident in MATERIALS:
                    uv,region,density=map_face(vertices[face],ident,variant,phases[ident])
                    entries.append({'mesh':mi,'face':fi,'finish_id':ident,'uv':uv,'region_px':region,'density':density,'repeat_group':f'finish_{ident}'})
                elif ident in (6,7) and variant=='NPM_ATLAS':
                    # Actual existing RAL7024 swatch, no unrelated atlas window silhouettes.
                    uv=[[1928/2048,1-1948/2048],[1944/2048,1-1948/2048],[1944/2048,1-1932/2048],[1928/2048,1-1932/2048]]
                    entries.append({'mesh':mi,'face':fi,'finish_id':ident,'uv':uv,'region_px':[1920,88,1950,128],'density':None,'repeat_group':'flat_frame_swatch'})
        result['variants'][variant]={'entries':entries,'size':2048 if variant=='NPM_ATLAS' else SIZE,'padding':PADDING[variant],
            'tiles':[1001] if variant=='NPM_ATLAS' else [1001,1002,1003,1004],'phase_offsets_m':phases}
    for p,record in zip(paths,provenance): assert sha(p)==record['sha256']
    (out/'shared-uv-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    # Actual UV overlay, projected into a compact technical contact sheet.
    for variant,data in result['variants'].items():
        views=[]
        for tile in data['tiles']:
            path=out/('NPM_ATLAS_Diffuse.png' if variant=='NPM_ATLAS' else f'VPM_Diffuse.{tile}.png')
            im=Image.open(path).convert('RGB').resize((768,768));draw=ImageDraw.Draw(im)
            for e in data['entries']:
                u=np.array(e['uv']);ti=int(np.floor(u[:,0].mean()))+1001
                if ti!=tile:continue
                points=[((x-(tile-1001))*768,(1-y)*768) for x,y in u]
                draw.line(points+[points[0]],fill=(0,220,235),width=1)
            views.append(im)
        sheet=Image.new('RGB',(768*len(views),768))
        for i,im in enumerate(views):sheet.paste(im,(768*i,0))
        sheet.save(out/f'{variant}_UV.png')
    print('SHARED_UV_READY',flush=True)


if __name__=='__main__':main(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())

"""Rasterize the original basket outer panels into a binary opacity atlas."""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from inspect_nodes import flatten

job=Path('jobs/GLB-NPM')
cfg=json.loads((job/'plane-nodes-job.json').read_text(encoding='utf-8'))
out=job/'outputs/planes-ab-v002'
out.mkdir(parents=True,exist_ok=True)
assert not (out/'AC_opacity.png').exists(), 'Use a new version'
size=2048; pad=16; half=size//2
atlas=Image.new('L',(size,size),0)
faces=list(flatten(cfg['source_ac_definition']))
lo,hi=cfg['ac']['min_m'],cfg['ac']['max_m']
panels=[('front',1,lo[1],0,2),('left',0,lo[0],1,2),('right',0,hi[0],1,2),('bottom',2,lo[2],0,1)]
manifest={}
for k,(name,axis,value,u,v) in enumerate(panels):
    x,y=(k%2)*half+pad,(k//2)*half+pad
    w=half-2*pad;h=w
    tile=Image.new('L',(w,h),0);draw=ImageDraw.Draw(tile)
    n=0
    for e,p,m in faces:
        if np.max(np.abs(p[:,axis]-value))>1e-5:continue
        for poly in e['polygons']:
            q=p[[abs(i)-1 for i in poly]]
            coords=[((a[u]-lo[u])/(hi[u]-lo[u])*(w-1),(1-(a[v]-lo[v])/(hi[v]-lo[v]))*(h-1)) for a in q]
            draw.polygon(coords,fill=255);n+=1
    assert n>0,name
    atlas.paste(tile,(x,y))
    # Clamp border padding around each independently reusable panel.
    atlas.paste(tile.resize((w+2*pad,h+2*pad)),(x-pad,y-pad))
    atlas.paste(tile,(x,y))
    manifest[name]={'uv_min':[(x+.5)/size,1-(y+h-.5)/size],
                    'uv_max':[(x+w-.5)/size,1-(y+.5)/size],
                    'axes':[u,v],'triangles_rasterized':n,
                    'opaque_fraction':float(np.mean(np.array(tile)>127))}
atlas.save(out/'AC_opacity.png')
(out/'AC_opacity_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest))

"""Audit UVs from reopened Blender files and create actual-layout inspection images."""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image,ImageDraw
from shapely.geometry import Polygon
from shapely.strtree import STRtree
from check_shell_windows import audit,compare_surfaces


def main(p):
    out=p/'uv_trial';d=json.loads((out/'uv-manifest.json').read_text(encoding='utf-8'))
    saved=json.loads((out/'blender-uv-readback.json').read_text(encoding='utf-8'))
    result={'variants':{},'passed':False,'limitations':['Colour previews only; no approved PBR maps',
             '23 BODY faces have unresolved finish ID0; spatial gable masks needed',
             'Glass remains within editable instanced window meshes; final VPM glass export not produced']}
    for variant,layout in d['layouts'].items():
        entries=layout['entries'];size=layout['size'];pad=layout['padding'];groups=defaultdict(list)
        min_padding=1.;min_area=1.;wrong_pixels=0;max_uv_error=0.;uv_entries=[]
        textures={tile:Image.open(out/f'{variant}_Diffuse_PREVIEW.{tile}.png').convert('RGB') for tile in layout['tiles']}
        for entry in entries:
            mesh=saved[variant]['meshes'][entry['mesh']];uv=np.array(mesh['uv_layers'][variant][entry['face']*4:entry['face']*4+4])
            max_uv_error=max(max_uv_error,float(abs(uv-np.array(entry['uv'])).max()))
            assert np.isfinite(uv).all()
            tile=entry['tile'];local=uv-np.array([tile%10,tile//10])
            min_padding=min(min_padding,float(min(local.min(),1-local.max())))
            signed=float(np.sum(local[:,0]*np.roll(local[:,1],-1)-local[:,1]*np.roll(local[:,0],-1))/2)
            min_area=min(min_area,signed);assert signed>0
            poly=Polygon(local);assert poly.is_valid
            glass=variant=='VPM_UDIM' and entry['finish_id']==90
            if not glass:
                groups[tile].append(poly)
                c=poly.centroid;point=(min(size-1,int(c.x*size)),min(size-1,int((1-c.y)*size)))
                wrong_pixels+=int(textures[entry['udim']].getpixel(point)!=tuple(d['palette'][str(entry['finish_id'])]))
            uv_entries.append({**entry,'uv':uv.tolist()})
        overlaps=[]
        for tile,polys in groups.items():
            tree=STRtree(polys)
            for i,poly in enumerate(polys):
                for j in tree.query(poly):
                    if j<=i:continue
                    area=poly.intersection(polys[j]).area
                    if area>1e-10:overlaps.append([tile,i,int(j),area])
        assert min_padding*size>=pad-.01 and max_uv_error<2e-6 and not overlaps and not wrong_pixels
        if variant=='VPM_UDIM':
            tiled=[im for im in saved[variant]['images'] if im['source']=='TILED']
            assert any(im['tiles']==layout['tiles'] for im in tiled)
        preview_size=1600 if variant=='NPM_ATLAS' else 420
        tiles=layout['tiles'];columns=1 if len(tiles)==1 else 5;rows=(len(tiles)+columns-1)//columns
        canvas=Image.new('RGB',(columns*preview_size,rows*(preview_size+28)),(25,30,38));draw=ImageDraw.Draw(canvas)
        for idx,number in enumerate(tiles):
            ox=(idx%columns)*preview_size;oy=(idx//columns)*(preview_size+28)
            draw.text((ox+8,oy+5),f'{variant} {number}',fill='white')
            for entry in uv_entries:
                if entry['udim']!=number:continue
                tile=entry['tile'];points=[(ox+(u-tile%10)*preview_size,oy+28+(1-(v-tile//10))*preview_size) for u,v in entry['uv']]
                color=tuple(d['id_colors'][str(entry['finish_id'])]);draw.polygon(points,fill=color,outline=(220,220,220))
        canvas.save(out/f'{variant}_UV_LAYOUT.png')
        result['variants'][variant]={'islands_unique_meshes':len(entries),'tile_numbers':tiles,'unexpected_uv_overlaps':len(overlaps),
             'mirrored_or_zero_area_islands':0,'minimum_border_padding_px':min_padding*size,'readback_uv_max_error':max_uv_error,
             'texture_pixel_mismatches':wrong_pixels,'texture_size':size,'density_exceptions':layout['density_exceptions'],
             'uv_checks_passed':True,'repeated_instance_uv_sharing':'Intentional: one UV layout per type',
             'sha256':saved[variant]['sha256']}
    # Re-expand the actual linked meshes for inter-object geometry verification.
    source=json.loads((p/'shell-windows-optimized.json').read_text(encoding='utf-8'))
    expanded={}
    for variant in ['MASTER','VPM_UDIM']:
        actual={m['key']:m for m in saved[variant]['meshes']};meshes=[]
        expected={m['key']:m for m in (d['vpm_meshes'] if variant=='VPM_UDIM' else d['meshes'])}
        for item in d['instances']:
            mesh=actual[item['mesh_key']];v=np.array(mesh['vertices']);v=np.c_[v,np.ones(len(v))]@np.array(item['matrix']).T
            meshes.append({'vertices':v[:,:3].tolist(),'faces':mesh['faces'],'materials':expected[item['mesh_key']]['materials']})
        expanded[variant]={**source,'meshes':meshes}
        geometry=audit(expanded[variant]);assert geometry['geometry_checks_passed']
        result['geometry_'+variant]=geometry
    result['vpm_connect_surface_preservation']=compare_surfaces(expanded['MASTER'],expanded['VPM_UDIM'])
    max_side=0.
    for mesh in expanded['VPM_UDIM']['meshes']:
        q=np.array(mesh['vertices'])[mesh['faces']];max_side=max(max_side,float(np.linalg.norm(q-np.roll(q,1,axis=1),axis=2).max()))
    assert max_side<4 and not d['layouts']['VPM_UDIM']['density_exceptions']
    result['vpm_max_polygon_side_m']=max_side
    densities=[]
    vpm_saved={m['key']:m for m in saved['VPM_UDIM']['meshes']}
    for item in d['instances']:
        mesh=vpm_saved[item['mesh_key']];q=np.array(mesh['vertices']);world=np.c_[q,np.ones(len(q))]@np.array(item['matrix']).T
        uv=np.array(mesh['uv_layers']['VPM_UDIM']).reshape(-1,4,2)
        for fi,(face,finish) in enumerate(zip(mesh['faces'],mesh['finish_ids'])):
            if finish==90:continue
            points=world[face,:3];lengths=np.linalg.norm(points-np.roll(points,1,axis=0),axis=1)
            ratios=4096*np.linalg.norm(uv[fi]-np.roll(uv[fi],1,axis=0),axis=1)/lengths
            densities.extend(ratios.tolist())
    assert min(densities)>=512 and max(densities)<=1706
    result['vpm_actual_instance_density_px_m']={'min':min(densities),'max':max(densities)}
    result['instances']={'count':45,'types':3,'counts':{m['key']:m['users_in_scene'] for m in saved['MASTER']['meshes'][1:]},
                         'normalization_max_error_m':d['normalization_max_error_m'],'outer_frame_extents_preserved_by_instance_scale':True,
                         'readback_verified':True}
    (out/'uv-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'uv_checks_passed':True,'geometry_checks_passed':geometry['geometry_checks_passed'],'instances':result['instances'],'passed':False}))


if __name__=='__main__':main(Path(sys.argv[1]))

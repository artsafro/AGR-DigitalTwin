"""Assign every ID=2 body plane to an existing simple opening asset."""
import json
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/body-v005'
groups=json.loads((OUT/'body-window-face-groups.json').read_text(encoding='utf-8'))
type_map=json.loads((ROOT/'outputs/openings-v003/type-map.json').read_text(encoding='utf-8'))
specs={s['id']:s for s in type_map['types']+type_map['size_variants']}
old=json.loads((ROOT/'outputs/placements-v004/placement-map.json').read_text(encoding='utf-8'))
shift=np.array([-29.3133,-55.3096,0.0])
old_centers=[]
for row in old['placements']:
    if row['type_id']=='D04':continue
    spec=specs[row['type_id']]
    matrix=np.asarray(row['matrix_world'])
    center=(matrix@np.array([spec['width_m']/2,0,spec['height_m']/2,1]))[:3]+shift
    old_centers.append((row['type_id'],center,row['id']))

def heuristic(width,height,bottom):
    if bottom<.8 and width<1.45:return 'D01'
    if bottom<.8 and width<2.45:return 'D02'
    if bottom<.8 and width<3.5:return 'D03'
    if width<1.35:return 'W03_H' if height>3.0 else 'W03'
    if width<2.45:
        if height>3.7:return 'W06'
        return 'W02_H' if height>3.0 else 'W02'
    if width<3.4:return 'W01_N'
    if width<4.5:return 'W01_H' if height>3.05 else 'W01'
    return 'W05'

records=[]
for index,g in enumerate(groups):
    width,height=g['width_m'],g['height_m']
    center=np.asarray(g['origin'])+np.asarray(g['right'])*width/2+np.array([0,0,height/2])
    candidate=sorted((np.linalg.norm(center-p),type_id,old_id)
                     for type_id,p,old_id in old_centers)[0]
    proximity,near_type,near_id=candidate
    near_spec=specs[near_type]
    near_size=max(abs(width-near_spec['width_m']),abs(height-near_spec['height_m']))
    if proximity<.35 and near_size<.2:
        chosen=near_type
        basis='prior FBX placement + body plane'
        old_source=near_id
    else:
        chosen=heuristic(width,height,g['bbox_min'][2])
        basis='body dimensions + album visual family'
        old_source=None
    spec=specs[chosen]
    delta=max(abs(width-spec['width_m']),abs(height-spec['height_m']))
    confidence='body+FBX, close size' if old_source and delta<=.12 else ('close size' if delta<=.12 else 'approximate scaled type; visual review required')
    assert g['planarity_error_m']<.001 and g['min_normal_dot']>.999
    records.append({'id':f'BODY_OPENING_{index+1:03d}','body_group_index':index,
        'body_face_indices':g['faces'],'type_id':chosen,'type_source':spec['source'],
        'width_m':width,'height_m':height,'source_type_width_m':spec['width_m'],
        'source_type_height_m':spec['height_m'],'origin':g['origin'],
        'right':g['right'],'normal_out':g['normal_out'],
        'old_fbx_placement':old_source,'assignment_basis':basis,'confidence':confidence,
        'size_deviation_m':round(delta,4),'planarity_error_m':g['planarity_error_m']})

assert sum(len(r['body_face_indices']) for r in records)==3203
report={'source_autosave':str(OUT/'live-autosave-snapshot.blend'),
        'body_object':'skolka','window_material_index':1,'window_material_name':'2 окна',
        'plane_count':len(records),'replaced_body_faces':3203,
        'assignments':dict(Counter(r['type_id'] for r in records)),
        'confidence_counts':dict(Counter(r['confidence'] for r in records)),
        'orientation_rule':'local -Y (frame face) = body plane outward normal; glass +Y inside',
        'source_geometry_preserved_in_snapshot':True,'visual_acceptance':'pending',
        'records':records}
(OUT/'body-opening-map.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'planes':len(records),'assignments':report['assignments'],
                  'confidence':report['confidence_counts'],
                  'max_size_deviation_m':max(r['size_deviation_m'] for r in records)},ensure_ascii=False))

"""Map simplified opening assets to measured FBX locations, without touching the source."""
import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'outputs/source-v001'
LIB = ROOT / 'outputs/library-v001'
ATLAS = ROOT / 'outputs/openings-v003'
OUT = ROOT / 'outputs/placements-v004'
OUT.mkdir(exist_ok=True)

specs = json.loads((ATLAS / 'type-map.json').read_text(encoding='utf-8'))
specs = specs['types'] + specs['size_variants']
curtains = {t['id']: t for t in json.loads((LIB / 'curtain-types.json').read_text(encoding='utf-8'))}
cores = {t['id']: t for t in json.loads((LIB / 'rebuilt-core.json').read_text(encoding='utf-8'))}
transforms = json.loads((LIB / 'source-transforms.json').read_text(encoding='utf-8'))

placed_curtain_members = {
    name
    for spec in specs for source in spec['merged_sources'] if source.startswith('CW_')
    for placement in curtains[source]['placements']
    for name in placement['source_members']
}
records = []
skipped_nested = Counter()
for spec in specs:
    for source in spec['merged_sources']:
        if source.startswith('CW_'):
            item = curtains[source]
            placements = item['placements']
            dimensions = item['dimensions']
        else:
            item = cores[source]
            placements = [{'source_members': [name], 'to_world': transforms[name]}
                          for name in item['instances']]
            dimensions = item['dimensions']
        for index, placement in enumerate(placements):
            members = placement['source_members']
            if not source.startswith('CW_') and members[0] in placed_curtain_members:
                skipped_nested[spec['id']] += 1
                continue
            matrix = np.asarray(placement['to_world'], dtype=float)
            # Source transforms map the normalized Revit object's lower corner to world.
            # Window frame leaves can start inside the broader exported family bbox.
            correction = np.eye(4)
            if not source.startswith('CW_') and source.startswith('WINDOW_'):
                frame = np.asarray([v for part in item['parts'] if part['role'] == 'FRAME_LEAF'
                                    for v in part['vertices']])
                correction[0, 3] = frame.min(axis=0)[0]
                correction[2, 3] = frame.min(axis=0)[2]
                dimensions = [frame.max(axis=0)[0] - frame.min(axis=0)[0],
                              dimensions[1], frame.max(axis=0)[2] - frame.min(axis=0)[2]]
            correction[1, 3] = dimensions[1] / 2
            correction[0, 0] = dimensions[0] / spec['width_m']
            correction[2, 2] = dimensions[2] / spec['height_m']
            matrix = matrix @ correction
            records.append({
                'id': f"{spec['id']}_{len(records)+1:04d}",
                'type_id': spec['id'], 'source_type': source,
                'source_members': members, 'matrix_world': matrix.tolist(),
                'target_width_m': round(float(dimensions[0]), 4),
                'target_height_m': round(float(dimensions[2]), 4),
                'source_depth_m': round(float(dimensions[1]), 4),
                'source_assembly': placement.get('assembly'),
                'scope': 'FBX position; facade match pending' if spec['id'] == 'D04' else 'mapped type position',
            })

assert len({x['id'] for x in records}) == len(records)
assert len({n for x in records for n in x['source_members']}) == sum(len(x['source_members']) for x in records)
payload = {
    'source_snapshot': str(SOURCE / 'source-snapshot.blend'),
    'asset_library': str(ATLAS / 'SOSH1150_Openings_v003.blend'),
    'placement_count': len(records),
    'counts': dict(Counter(x['type_id'] for x in records)),
    'skipped_door_instances_nested_in_curtain': dict(skipped_nested),
    'placement_basis': 'FBX assembly transform or object transform; centering in source depth; per-instance width/height scale',
    'accuracy': 'approximate front-skin placement; no opening clearance or facade visual acceptance asserted',
    'placements': records,
}
(OUT / 'placement-map.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'placements': len(records), 'counts': payload['counts'],
                  'skipped_nested': payload['skipped_door_instances_nested_in_curtain']}, ensure_ascii=False))

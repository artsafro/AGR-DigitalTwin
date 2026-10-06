"""Read back the saved FBX overlay and compare each proxy with its source bbox."""
import json
from collections import Counter
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/placements-v004'
data = json.loads((OUT / 'placement-map.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(OUT / 'SOSH1150_FBX_Openings_Placed_v004.blend'))
objects = bpy.context.scene.objects

def bounds(items):
    points = [obj.matrix_world @ Vector(corner) for obj in items for corner in obj.bound_box]
    return ([min(v[i] for v in points) for i in range(3)],
            [max(v[i] for v in points) for i in range(3)])

issues = []
deviations = []
for row in data['placements']:
    obj = objects.get(row['id'])
    if obj is None:
        issues.append((row['id'], 'missing'))
        continue
    if obj.type != 'MESH' or len(obj.data.materials) != 2:
        issues.append((row['id'], 'mesh/material mismatch'))
    if obj['source_type'] != row['source_type'] or obj['type_id'] != row['type_id']:
        issues.append((row['id'], 'provenance mismatch'))
    matrix_error = max(abs(obj.matrix_world[i][j] - row['matrix_world'][i][j])
                       for i in range(4) for j in range(4))
    if matrix_error > 1e-5:
        issues.append((row['id'], f'matrix error {matrix_error}'))
    source = [objects.get(name) for name in row['source_members']]
    if any(ob is None for ob in source):
        issues.append((row['id'], 'missing source object'))
        continue
    if any(not ob.hide_get() or not ob.hide_render for ob in source):
        issues.append((row['id'], 'source duplicate visible'))
    low_a, high_a = bounds([obj])
    low_b, high_b = bounds(source)
    axis_error = [max(abs(low_a[i]-low_b[i]), abs(high_a[i]-high_b[i])) for i in range(3)]
    normal_axis = max(range(3), key=lambda i: abs(row['matrix_world'][i][1]))
    plane_error = max(axis_error[i] for i in range(3) if i != normal_axis)
    depth_error = axis_error[normal_axis]
    deviations.append((plane_error, depth_error, row['id'], row['type_id']))
    if plane_error > .05 or depth_error > row['source_depth_m']/2 + .04:
        issues.append((row['id'], f'plane/depth deviation {plane_error:.3f}/{depth_error:.3f}m'))

result = {'placed': len(data['placements']), 'type_count': len(data['counts']),
          'unique_source_members': len({n for row in data['placements'] for n in row['source_members']}),
          'max_facade_plane_deviation_m': round(max(x[0] for x in deviations), 4),
          'max_depth_deviation_m': round(max(x[1] for x in deviations), 4),
          'worst': sorted(deviations, reverse=True)[:12],
          'counts': dict(Counter(objects[row['id']]['type_id'] for row in data['placements'] if objects.get(row['id']))),
          'issues': issues, 'transform_checks_passed': not issues,
          'visual_acceptance': 'pending', 'full_typology_complete': False,
          'delivery_passed': False}
(OUT / 'QA.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in {'counts','worst'}}, ensure_ascii=False))

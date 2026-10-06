"""Dominant vertical facade planes (x = const, y = const) of the clipped S3 building, by face area.

    blender --background <floor1_src.blend> --python jobs/PSU275/scripts/facade_planes.py -- <report.json>
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import bpy

out = sys.argv[sys.argv.index("--") + 1]
planes = {"x": defaultdict(float), "y": defaultdict(float)}
for o in bpy.data.objects:
    if o.type != "MESH" or "Сэндвич" not in o.name and "RAL 5015" not in o.name:
        continue
    m = o.data
    for p in m.polygons:
        n = p.normal
        if abs(n.z) > 0.05:
            continue
        c = o.matrix_world @ p.center
        if abs(n.x) > 0.99:
            planes["x"][round(c.x, 2)] += p.area
        elif abs(n.y) > 0.99:
            planes["y"][round(c.y, 2)] += p.area
res = {k: sorted(([v, round(a, 1)] for v, a in d.items()), key=lambda r: -r[1])[:25] for k, d in planes.items()}
Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(res))

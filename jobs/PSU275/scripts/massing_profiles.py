"""Exterior facade profiles of a union of rectangular masses (2.5D), one profile per plane.

    uv run python jobs/PSU275/scripts/massing_profiles.py jobs/PSU275/masses.json <out.json>

Plan is cut on every mass edge. A cell's height is the highest mass covering it. Between two
neighbouring cells (or a cell and outside) with heights h_hi > h_lo, the shared line is an
exterior face from z = top(lo cell) (0 outside) up to h_hi, facing the lower cell. Starting at the
lower parapet top (not its roof) keeps every corner edge manifold; the strip between the lower
roof and its parapet top belongs to the roof element.
With --wells the step wall continues down to the lower roof as a band inset by the shell thickness
at the ends where the lower region has its own parapet; the parapet inner faces (roof element) then
end on the band's vertical edges, and the roof meets the band's bottom edge. Faces on the
same plane and orientation are merged into one shapely profile in (u, z).
"""
import json
import sys
from pathlib import Path

import shapely
from shapely.geometry import box, mapping

cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
WELLS = "--wells" in sys.argv  # extend step walls down to the lower roof (parapet wells in BODY)
SHELL = 0.4
masses = cfg["masses"]
xs = sorted({v for m in masses for v in m["x"]})
ys = sorted({v for m in masses for v in m["y"]})


def cell(i, j):
    """(top, roof, mass) of plan cell i, j; (0, 0, None) outside."""
    if not (0 <= i < len(xs) - 1 and 0 <= j < len(ys) - 1):
        return 0.0, 0.0, None
    cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
    best = (0.0, 0.0, None)
    for m in masses:
        if m["x"][0] < cx < m["x"][1] and m["y"][0] < cy < m["y"][1] and m["top"] > best[0]:
            best = (m["top"], m["roof"], m["name"])
    return best


faces = {}  # (axis, coord, outward_sign) -> list of boxes in (u, z)
for i in range(-1, len(xs) - 1):
    for j in range(-1, len(ys) - 1):
        a = cell(i, j)
        # neighbour in +x (plane x = xs[i+1]) and +y (plane y = ys[j+1])
        for axis, b, coord, span in ((0, cell(i + 1, j), xs[i + 1] if i + 1 < len(xs) else None,
                                      (ys[j], ys[j + 1]) if 0 <= j < len(ys) - 1 else None),
                                     (1, cell(i, j + 1), ys[j + 1] if j + 1 < len(ys) else None,
                                      (xs[i], xs[i + 1]) if 0 <= i < len(xs) - 1 else None)):
            if coord is None or span is None or a[0] == b[0]:
                continue
            hi, lo, sign = (a, b, +1) if a[0] > b[0] else (b, a, -1)
            z0 = lo[0] if lo[2] is not None else 0.0
            if hi[0] <= z0:
                continue
            faces.setdefault((axis, coord, sign), []).append(box(span[0], z0, span[1], hi[0]))
            if WELLS and lo[2] is not None and lo[1] < lo[0]:
                # parapet well band: the upper wall continues down to the lower roof, but stops SHELL
                # short of every end where the lower region turns into its own parapet
                li, lj = ((i + 1, j) if hi is a else (i, j)) if axis == 0 else ((i, j + 1) if hi is a else (i, j))
                prev = cell(li, lj - 1) if axis == 0 else cell(li - 1, lj)
                nxt = cell(li, lj + 1) if axis == 0 else cell(li + 1, lj)
                # trim only where the lower region ends in its own parapet (lower or outside neighbour);
                # next to a taller neighbour the well continues to the concave corner
                u0 = span[0] + (SHELL if prev[0] < lo[0] else 0.0)
                u1 = span[1] - (SHELL if nxt[0] < lo[0] else 0.0)
                if u1 - u0 > 1e-9:
                    faces[(axis, coord, sign)].append(box(u0, lo[1], u1, z0))

profiles = []
for (axis, coord, sign), boxes in sorted(faces.items()):
    shape = shapely.union_all(boxes).simplify(1e-9, preserve_topology=True)
    for poly in getattr(shape, "geoms", [shape]):
        outward = [0.0, 0.0]
        outward[axis] = float(sign)
        profiles.append({"axis": axis, "along_axis": 1 - axis, "plane": coord, "outward": outward,
                         "profile_geojson": json.dumps(mapping(poly)), "area_m2": round(poly.area, 3),
                         "bounds_uz": [round(v, 4) for v in poly.bounds]})
Path(sys.argv[2]).write_text(json.dumps({"source": sys.argv[1], "x_cuts": xs, "y_cuts": ys,
                                         "profiles": profiles}, indent=1), encoding="utf-8")
print("profiles", len(profiles), "area", round(sum(p["area_m2"] for p in profiles), 1))
for p in profiles:
    print(" ", "xy"[p["axis"]], p["plane"], p["outward"], p["bounds_uz"], p["area_m2"])

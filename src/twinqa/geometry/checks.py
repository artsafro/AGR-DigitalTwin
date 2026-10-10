"""Geometry checks of a model against its etalon (docs/HARNESS_PLAN.md §5, benchmark/README.md).

Input: two mesh dumps in one object system, the etalon's spec and the `geometry` block of the
benchmark's tolerances.json; every threshold comes from there. Each check returns
{id, status, value, limit, details}; status is pass, fail or not_measured, and the run passes only
when every check passes (an unmeasured check is an open gate, never a pass). These checks compare
geometry before UV and textures; they do not replace the delivery validator V001-V017.
"""
from pathlib import Path

import numpy as np
import shapely
import yaml

from dt_ai.geometry.from_spec import SEAT_SHARE
from dt_ai.spec.model import Spec
from twinqa.clearance import near_parallel_overlaps
from twinqa.geometry import measure
from twinqa.geometry.mesh import Soup, edge_uses, parts, weld

RANGES = Path(__file__).resolve().parents[3] / "standards" / "material_id_ranges.yaml"


def result(check_id, ok, value, limit, details=None, measured=True):
    return {"id": check_id, "status": ("pass" if ok else "fail") if measured else "not_measured",
            "value": value, "limit": limit, "details": details or {}}


def load_ranges(path: Path = RANGES) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _group_of(mid: int, ranges: dict) -> str | None:
    if mid == ranges["unassigned"]:
        return "unassigned"
    return next((g for g, r in ranges["groups"].items() if r["first"] <= mid <= r["last"]), None)


def check_bbox(model: Soup, etalon: Soup, tol: dict) -> dict:
    a, b = measure.bbox(model.corners()), measure.bbox(etalon.corners())
    worst = float(np.abs(a - b).max())
    return result("bbox", worst <= tol["bbox_m"], round(worst, 4), tol["bbox_m"],
                  {"model": a.round(4).tolist(), "etalon": b.round(4).tolist()})


def check_levels(model: Soup, etalon: Soup, spec: Spec, tol: dict) -> dict:
    """LEVEL_<name> helpers of the model against the etalon's (the spec's levels if the etalon has none)."""
    ref = etalon.levels or {lv.name: lv.elev_m for lv in spec.levels}
    missing = sorted(set(ref) - set(model.levels))
    diffs = {n: round(abs(model.levels[n] - z), 4) for n, z in ref.items() if n in model.levels}
    worst = max(diffs.values(), default=0.0)
    ok = not missing and worst <= tol["level_elev_m"]
    return result("levels", ok, worst, tol["level_elev_m"], {"diff_m": diffs, "missing_in_model": missing})


def check_floor_areas(model: Soup, etalon: Soup, spec: Spec, tol: dict) -> dict:
    """Outer section area of every storey at the sampled heights. Where both sections close they are
    compared; where only one closes the model differs from the etalon there (a fail, never skipped).
    Where neither closes both agree; the height is listed as open_on_both_sides, not judged, because an
    NPM shell open at its reveals has no closed section in a window band (user decision 2026-10-09).
    A storey with no compared height at all fails."""
    names = [lv.name for lv in spec.levels]
    elev = {lv.name: lv.elev_m for lv in spec.levels}
    mc, ec = model.corners(), etalon.corners()
    per_floor, worst, unmeasured, one_sided, both_open = {}, 0.0, [], [], []
    for lo, hi in zip(names, names[1:]):
        rows = []
        for f in tol["section_fractions"]:
            z = elev[lo] + f * (elev[hi] - elev[lo])
            am, ae = measure.section_area(mc, z), measure.section_area(ec, z)
            if am is None or ae is None or ae <= 0:
                rows.append({"z": round(z, 3), "model_m2": am, "etalon_m2": ae})
                if (am is None) != (ae is None):
                    one_sided.append([lo, round(z, 3)])
                elif am is None:
                    both_open.append([lo, round(z, 3)])
                continue
            rel = abs(am - ae) / ae
            worst = max(worst, rel)
            rows.append({"z": round(z, 3), "model_m2": round(am, 3), "etalon_m2": round(ae, 3), "rel": round(rel, 4)})
        if not any("rel" in r for r in rows):
            unmeasured.append(lo)
        per_floor[lo] = rows
    ok = worst <= tol["floor_area_rel"] and not unmeasured and not one_sided
    return result("floor_areas", ok, round(worst, 4), tol["floor_area_rel"],
                  {"floors": per_floor, "no_closed_section": unmeasured, "closed_on_one_side": one_sided,
                   "open_on_both_sides": both_open})


def check_silhouettes(model: Soup, etalon: Soup, tol: dict) -> dict:
    mc, ec = model.corners(), etalon.corners()
    ious = {v: round(measure.iou(measure.silhouette(mc, v), measure.silhouette(ec, v)), 4)
            for v in tol["silhouette_views"]}
    worst = min(ious.values())
    return result("silhouettes", worst >= tol["silhouette_iou_min"], worst, tol["silhouette_iou_min"], {"iou": ious})


def open_loops(model: Soup, ids, counts, side_edges, skip, tol: dict, ranges: dict) -> list[dict]:
    """Open edges grouped into loops and classified (pattern roof-inset-plane, user rule 2026-10-10):
    `bottom` - every vertex at the model's lowest point; `roof-plane` - a horizontal loop of roof-group
    faces facing up, up to roof_inset_max_m above a LEVEL_<name> helper, one per level; `roof-foot` -
    the loop of upright roof-group faces (parapet inner faces) at that level under such a plane, at
    most one. Anything else is `other` and not allowed."""
    tri = np.flatnonzero(~skip)
    sides = side_edges[tri]
    open_mask = counts[sides] == 1
    edge_tris = {}
    for t, k in zip(*np.nonzero(open_mask)):
        edge_tris.setdefault(int(sides[t, k]), (int(tri[t]), int(k)))
    if not edge_tris:
        return []
    welded = np.zeros((int(ids.max()) + 1, 3))
    welded[ids] = model.vertices
    tri_ids = ids[model.triangles]
    parent = {}

    def find(v):
        parent.setdefault(v, v)
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    ends = {}
    for e, (t, k) in edge_tris.items():
        va, vb = int(tri_ids[t][k]), int(tri_ids[t][(k + 1) % 3])
        ends[e] = (va, vb)
        parent[find(va)] = find(vb)
    loops = {}
    for e, (va, _) in ends.items():
        loops.setdefault(find(va), []).append(e)
    g_roof = ranges["groups"]["roof"]
    zmin = float(model.vertices[:, 2].min())
    corners = model.corners()
    out = []
    for edges in loops.values():
        verts = sorted({v for e in edges for v in ends[e]})
        z = welded[verts, 2]
        flat_loop = float(z.max() - z.min()) <= tol["weld_m"]
        tris_ = [edge_tris[e][0] for e in edges]
        mids = model.material_ids[tris_]
        roof_faces = bool(np.all((mids >= g_roof["first"]) & (mids <= g_roof["last"])))
        c = corners[tris_]
        n = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
        nz = n[:, 2] / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
        kind, level = "other", None
        if flat_loop and abs(float(z.mean()) - zmin) <= tol["weld_m"]:
            kind = "bottom"
        elif flat_loop and roof_faces:
            for name, lz in model.levels.items():
                dz = float(z.mean()) - lz
                if np.all(nz > 0.99) and tol["weld_m"] < dz <= tol["roof_inset_max_m"] + tol["weld_m"]:
                    kind, level = "roof-plane", name
                elif np.all(np.abs(nz) < 0.01) and abs(dz) <= tol["weld_m"]:
                    kind, level = "roof-foot", name
        out.append({"kind": kind, "level": level, "edges": len(edges), "z": round(float(z.mean()), 4)})
    for name in {lp["level"] for lp in out if lp["level"]}:
        planes = [lp for lp in out if lp["level"] == name and lp["kind"] == "roof-plane"]
        feet = [lp for lp in out if lp["level"] == name and lp["kind"] == "roof-foot"]
        if len(planes) != 1 or len(feet) > 1:      # one inset plane per roof, its foot only under it
            for lp in planes + feet:
                lp["kind"] = "other"
    for lp in out:
        lp["allowed"] = lp["kind"] != "other"
    return out


def check_mesh(model: Soup, tol: dict, ranges: dict) -> dict:
    """Edge-manifold, no n-gons, no overlapping faces, and open edges only where the pattern
    roof-inset-plane allows them (user rule 2026-10-10): the bottom ring and, per roof, the joint of an
    inset roof plane (its outline and the foot of the faces it is inset into). Parts made only of
    open_part_groups are left out of the open-edge rule."""
    ids = weld(model.vertices, tol["weld_m"])
    _, counts, side_edges = edge_uses(model.triangles, ids)
    part = parts(model.triangles, ids)
    groups = np.array([_group_of(int(m), ranges) for m in model.material_ids], dtype=object)
    open_ok = {p for p in np.unique(part) if set(groups[part == p]) <= set(tol["open_part_groups"])}
    tri_open = np.array([p in open_ok for p in part], dtype=bool)
    boundary = np.zeros(len(counts), dtype=bool)
    boundary[np.unique(side_edges[~tri_open][counts[side_edges[~tri_open]] == 1])] = True
    loops = open_loops(model, ids, counts, side_edges, tri_open, tol, ranges)
    bad_loops = [lp for lp in loops if not lp["allowed"]]
    non_manifold = int((counts > 2).sum())
    boundary_n = int(boundary.sum())
    corners = model.corners()
    faces = [{"object": "model", "index": i, "points": c.tolist()} for i, c in enumerate(corners)]
    overlaps = near_parallel_overlaps(faces, tol["overlap_m"])
    if model.polygon_sizes is None:
        ngons, ngon_measured = None, False
    else:
        ngons, ngon_measured = int((model.polygon_sizes > 4).sum()), True
    details = {"non_manifold_edges": non_manifold, "boundary_edges": boundary_n, "open_loops": loops,
               "open_parts_allowed": len(open_ok), "ngons": ngons, "collision_meshes_left_out": model.collisions,
               "triangles_in_polygons": None if model.polygon_sizes is None else int((model.polygon_sizes == 3).sum()),
               "overlap_pairs": len(overlaps), "overlaps": overlaps[:20]}
    ok = (non_manifold <= tol["non_manifold_edges_max"] and not bad_loops
          and len(overlaps) <= tol["overlap_pairs_max"] and (ngons or 0) <= tol["ngons_max"])
    if not ngon_measured and ok:
        return result("mesh", False, None, None, {**details, "why": "dump has no polygon_sizes matching its triangles"},
                      measured=False)
    return result("mesh", ok, {"non_manifold": non_manifold, "boundary": boundary_n,
                               "open_loops_not_allowed": len(bad_loops), "overlaps": len(overlaps), "ngons": ngons},
                  None, details)


def check_budget(model: Soup, tol: dict) -> dict:
    n = int(len(model.triangles))
    return result("triangle_budget", n <= tol["triangles_max"], n, tol["triangles_max"])


def check_material_ids(model: Soup, tol: dict, ranges: dict) -> dict:
    used = {}
    for mid in np.unique(model.material_ids):
        used.setdefault(_group_of(int(mid), ranges) or "out_of_range", []).append(int(mid))
    unassigned = int((model.material_ids == ranges["unassigned"]).sum())
    out = used.get("out_of_range", [])
    ok = not out and unassigned <= tol["unassigned_ids_max"]
    return result("material_ids", ok, {"out_of_range": out, "unassigned_triangles": unassigned},
                  tol["unassigned_ids_max"], {"groups": used})


def _wall(contour, i):
    pts = np.asarray([p[:2] for p in contour], dtype=float)
    a, b = pts[i], pts[(i + 1) % len(pts)]
    u = (b - a) / np.linalg.norm(b - a)
    x, y = pts[:, 0], pts[:, 1]
    ccw = float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y)) > 0  # spec contours are CCW; never assume
    n = np.array([u[1], -u[0]])
    return a, u, n if ccw else -n


def opening_planes(spec: Spec, kinds) -> list[dict]:
    """Every spec opening the check expects a plane in, with its rectangle in wall coordinates."""
    elev = {lv.name: lv.elev_m for lv in spec.levels}
    rows = []
    for floor in spec.expanded_floors():
        for k, o in enumerate(floor.openings):
            if o.kind not in kinds:
                continue
            rows.append({"level": floor.level, "index": k, "opening": o, "contour": floor.contour,
                         "z0": elev[floor.level] + o.sill_m,
                         "depth": spec.opening_depth_default_m if o.depth_m is None else o.depth_m,
                         "seat": (spec.opening_depth_default_m if o.depth_m is None else o.depth_m) * SEAT_SHARE[spec.profile]})
    return rows


def check_opening_planes(model: Soup, spec: Spec, tol: dict, ranges: dict) -> dict:
    """In every spec opening a plane facing out of the wall, at the profile's seat (C24: npm_min the full
    opening depth, mid half of it) within opening_plane_offset_m, of group `opening`, covering it."""
    g = ranges["groups"]["opening"]
    corners = model.corners()
    in_group = (model.material_ids >= g["first"]) & (model.material_ids <= g["last"])
    n3 = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    norm = np.linalg.norm(n3, axis=1)
    off = tol["opening_plane_offset_m"]
    rows, worst = [], 1.0
    for row in opening_planes(spec, tol["opening_plane_kinds"]):
        o, z0 = row["opening"], row["z0"]
        a, u, n = _wall(row["contour"], o.wall)
        s0, s1, z1 = o.x_m, o.x_m + o.w_m, z0 + o.h_m
        rel = corners[:, :, :2] - a
        s, t, z = rel @ u, rel @ n, corners[:, :, 2]
        facing = (n3[:, :2] @ n) / np.where(norm > 0, norm, 1) > 0.99   # the plane faces out of the wall
        inside = ((s.min(1) >= s0 - off) & (s.max(1) <= s1 + off) & (z.min(1) >= z0 - off) & (z.max(1) <= z1 + off)
                  & (t.max(1) <= -row["seat"] + off) & (t.min(1) >= -row["seat"] - off))   # at the profile's seat (C24)
        hit = in_group & facing & inside
        rect = shapely.box(s0, z0, s1, z1)
        cover = 0.0
        ids = sorted({int(m) for m in model.material_ids[hit]})
        if hit.any():
            flat = np.stack([s[hit], z[hit]], axis=2)
            area = shapely.union_all(shapely.polygons(flat), grid_size=1e-4)
            cover = float(shapely.intersection(area, rect).area / rect.area)
        wrong_id = o.material_id is not None and ids not in ([], [o.material_id])
        worst = min(worst, 0.0 if wrong_id else cover)
        rows.append({"level": row["level"], "opening": row["index"], "wall": o.wall, "kind": o.kind,
                     "cover": round(cover, 4), "material_ids": ids, "expected_id": o.material_id})
    ok = bool(rows) and worst >= tol["opening_plane_cover_min"]
    return result("opening_planes", ok, round(worst, 4) if rows else None, tol["opening_plane_cover_min"],
                  {"openings": rows}, measured=bool(rows))


def run(model: Soup, etalon: Soup, spec: Spec, tol: dict, ranges: dict | None = None) -> dict:
    """All §5 checks; tol is the `geometry` block of tolerances.json."""
    ranges = ranges or load_ranges()
    checks = [check_bbox(model, etalon, tol), check_levels(model, etalon, spec, tol),
              check_floor_areas(model, etalon, spec, tol), check_silhouettes(model, etalon, tol),
              check_mesh(model, tol, ranges), check_budget(model, tol),
              check_opening_planes(model, spec, tol, ranges), check_material_ids(model, tol, ranges)]
    return {"passed": all(c["status"] == "pass" for c in checks),
            "failed": [c["id"] for c in checks if c["status"] == "fail"],
            "not_measured": [c["id"] for c in checks if c["status"] == "not_measured"],
            "checks": checks}

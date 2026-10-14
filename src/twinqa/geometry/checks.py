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

from dt_ai.geometry.from_spec import DECOR_INSET_M, SEAT_SHARE
from dt_ai.spec.model import Spec
from twinqa.clearance import near_parallel_overlaps
from twinqa.geometry import measure
from shapely.ops import polygonize

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


def check_floor_areas(model: Soup, etalon: Soup, spec: Spec, tol: dict, basis: str = "etalon") -> dict:
    """Outer section area of every storey at the sampled heights. Where both sections close they are
    compared; where only one closes the model differs from the etalon there (a fail, never skipped).
    Where neither closes both agree; the height is listed as open_on_both_sides, not judged, because an
    NPM shell open at its reveals has no closed section in a window band (user decision 2026-10-09).
    A storey with no compared height at all fails. basis "spec" (a panelised source, user 2026-10-14: its
    sections never close): the model's section, decor left out, against the area of the storey's spec contour less
    the recesses of the spec's openings at that height (width x depth; npm_min at the full depth, mid at half)."""
    names = [lv.name for lv in spec.levels]
    elev = {lv.name: lv.elev_m for lv in spec.levels}
    mc, ec = model.corners(), etalon.corners()
    contour = {f.level: shapely.Polygon([p[:2] for p in f.contour]).area for f in spec.expanded_floors()}
    share = 1.0 if spec.profile == "npm_min" else 0.5
    recess = {f.level: [(o.sill_m, o.sill_m + o.h_m, o.w_m * (o.depth_m if o.depth_m is not None
                                                             else spec.opening_depth_default_m) * share)
                        for o in f.openings if o.kind in ("window", "door", None)] for f in spec.expanded_floors()}
    if basis == "spec" and model.mesh_index is not None and DECOR_MESH in model.mesh_names:
        mc = mc[model.mesh_index != model.mesh_names.index(DECOR_MESH)]
    per_floor, worst, unmeasured, one_sided, both_open = {}, 0.0, [], [], []
    for lo, hi in zip(names, names[1:]):
        rows = []
        for f in tol["section_fractions"]:
            z = elev[lo] + f * (elev[hi] - elev[lo])
            am = measure.section_area(mc, z)
            ae = (contour[lo] - sum(a for s0, s1, a in recess.get(lo, []) if s0 < z - elev[lo] < s1)
                  if basis == "spec" and lo in contour else measure.section_area(ec, z))
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
                   "open_on_both_sides": both_open, "basis": "spec-based" if basis == "spec" else "etalon"})


def check_silhouettes(model: Soup, etalon: Soup, tol: dict) -> dict:
    mc, ec = model.corners(), etalon.corners()
    ious = {v: round(measure.iou(measure.silhouette(mc, v), measure.silhouette(ec, v)), 4)
            for v in tol["silhouette_views"]}
    worst = min(ious.values())
    return result("silhouettes", worst >= tol["silhouette_iou_min"], worst, tol["silhouette_iou_min"], {"iou": ious})


GAP_NOISE_M = 1e-6   # a readback gap measured within this of the pattern range is in it


def inner_outlines_match(hole, plate, overlap, weld):
    """Every inner outline of the hole (a shaft) shrunk by the overlap is one outline, and the plate's inner
    outlines are exactly these, one to one (reviews 1-2 of PR #65: a shaft that vanishes or splits never
    hides behind a matching count)."""
    want = []
    for ring in hole.interiors:
        shrunk = shapely.Polygon(ring).buffer(-overlap, join_style="mitre", mitre_limit=1e6)
        if shrunk.geom_type != "Polygon" or shrunk.is_empty:
            return False
        want.append(shrunk.exterior)
    have = list(plate.interiors)
    if len(want) != len(have):
        return False
    used = set()
    for w_ in want:
        hit = [k for k, h in enumerate(have) if k not in used and w_.hausdorff_distance(h) <= weld]
        if len(hit) != 1:
            return False
        used.add(hit[0])
    return True


def open_loops(model: Soup, ids, counts, side_edges, skip, tol: dict, ranges: dict, structures=()) -> list[dict]:
    """Open edges grouped into loops and classified (pattern roof-inset-plane, user rules 2026-10-10):
    `bottom` - flat, at the model's lowest point. The joint of an inset slab (a roof in a parapet or a
    terrace) is exactly two closed loops per slab: `roof-foot` (contour A, the hole in the body: the
    foot of the upright faces around it - parapet inner faces, and walls of the floor above for a
    terrace - at a LEVEL_<name>) and `roof-plane` (contour B, the outline of a flat roof-group plate facing up,
    roof_inset_gap_m above that level, embedded into the faces around the hole: in plan B is A grown
    by one even offset within roof_inset_embed_m, so the outlines never cross). A roof without an inset
    has no loop. Anything else - a third loop, a lone A or B, a loop that is not one simple closed
    cycle - is `other`. `roof-structure` (spec v0.7, pattern roof-screen-enclosure): the bottom of a roof
    structure's walls - a flat closed loop at the top level on one of the spec's outlines; it takes no part in
    the slab joints. structures: [(outline Polygon, roof level z)]."""
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
        degree = {}
        for e in edges:
            for v in ends[e]:
                degree[v] = degree.get(v, 0) + 1
        closed = all(d == 2 for d in degree.values())
        z = welded[verts, 2]
        flat_loop = float(z.max() - z.min()) <= tol["weld_m"]
        tris_ = [edge_tris[e][0] for e in edges]
        mids = model.material_ids[tris_]
        roof_faces = bool(np.all((mids >= g_roof["first"]) & (mids <= g_roof["last"])))
        c = corners[tris_]
        n = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
        nz = n[:, 2] / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
        kind, level = "other", None
        gap_lo, gap_hi = tol["roof_inset_gap_m"]
        if flat_loop and abs(float(z.mean()) - zmin) <= tol["weld_m"]:
            kind = "bottom"
        elif flat_loop and closed:
            for name, lz in model.levels.items():
                dz = float(z.mean()) - lz
                # an inset gap is never welded (user 2026-10-13): past weld_m, within the pattern's range
                if (roof_faces and np.all(nz > 0.99) and dz > tol["weld_m"]
                        and gap_lo - GAP_NOISE_M <= dz <= gap_hi + GAP_NOISE_M):
                    kind, level = "roof-plane", name
                elif np.all(np.abs(nz) < 0.01) and abs(dz) <= tol["weld_m"]:
                    kind, level = "roof-foot", name
        segs = [welded[list(ends[e]), :2] for e in edges]
        upward = bool(np.all(c_mid > float(z.mean()) + tol["weld_m"])) if (c_mid := corners[tris_][:, :, 2].mean(
            axis=1)).size else False
        if flat_loop and closed and structures and roof_faces and upward:   # walls standing on it, roof ids: a
            ring = list(polygonize(shapely.linestrings(segs)))              # shaft's open top is none (review 1)
            if len(ring) == 1 and any(abs(float(z.mean()) - zs) <= tol["weld_m"]
                                      and ring[0].exterior.hausdorff_distance(poly.exterior) <= tol["weld_m"]
                                      for poly, zs in structures):
                kind, level = "roof-structure", None
        out.append({"kind": kind, "level": level, "edges": len(edges), "z": round(float(z.mean()), 4), "_z": float(z.mean()),
                    "closed": closed, "_segs": segs})
    shape = lambda lp: list(polygonize(shapely.linestrings(lp["_segs"])))  # noqa: E731
    lo, hi = tol["roof_inset_embed_m"]
    w = tol["weld_m"]
    for name in {lp["level"] for lp in out if lp["level"]}:
        planes = [lp for lp in out if lp["level"] == name and lp["kind"] == "roof-plane"]
        feet = [lp for lp in out if lp["level"] == name and lp["kind"] == "roof-foot"]
        # one slab = the hole A (outer foot loop, and an inner one per shaft) and the plate B (its outline,
        # and an inner one around each shaft): regions by even-odd of the loops of a level, so a shaft's
        # loops are the region's inner outlines (KPP1, user 2026-10-10); every A region lies under exactly
        # one B region and every B region over exactly one A; B is A grown by one even overlap, outer
        # outline out and inner outlines in; a level may hold several slabs (a ledge in parts)
        rings = {id(lp): shape(lp) for lp in planes + feet}
        good_feet = [lp for lp in feet if len(rings[id(lp)]) == 1]
        good_planes = [lp for lp in planes if len(rings[id(lp)]) == 1]

        def regions(loops):
            area = shapely.Polygon()
            for lp in loops:
                area = area.symmetric_difference(rings[id(lp)][0])
            return [g for g in shapely.get_parts(area) if g.geom_type == "Polygon" and g.area > w * w]

        def owners(region, loops):
            edge = region.boundary.buffer(w)
            return [lp for lp in loops if edge.contains(rings[id(lp)][0].exterior)]

        a_regions, b_regions = regions(good_feet), regions(good_planes)
        paired = set()
        for b_ in b_regions:
            under = [a_ for a_ in a_regions if b_.buffer(-w).contains(a_)]
            if len(under) != 1 or sum(1 for g in b_regions if g.buffer(-w).contains(under[0])) != 1:
                continue
            a_ = under[0]
            embed = float(a_.boundary.distance(b_.boundary))
            # sharp corners keep their full mitre (no clipping); evenness within the weld tolerance
            grown = a_.buffer(embed, join_style="mitre", mitre_limit=1e6)
            # every inner outline of A (a shaft) survives the overlap and has its own in B (review 1 of PR #65)
            even = (grown.geom_type == "Polygon" and inner_outlines_match(a_, b_, embed, w)
                    and float(grown.exterior.hausdorff_distance(b_.exterior)) <= w)
            if even and lo - w <= embed <= hi + w:
                for pl in owners(b_, good_planes):
                    pl["embed_m"], pl["_embed"] = round(embed, 4), embed
                    paired.add(id(pl))
                paired |= {id(f) for f in owners(a_, good_feet)}
        for lp in planes + feet:
            if id(lp) not in paired:
                lp["kind"] = "other"
    _seat(model, out, tol["weld_m"])
    for lp in out:
        lp.pop("_segs")
    for lp in out:
        lp["allowed"] = lp["kind"] != "other"
    return out


def fan_vertices(triangles, ids, side_edges, skip) -> list[int]:
    """Non-manifold vertices (issue #57): welded vertices whose faces form more than one fan, i.e. two
    face groups meet only at that point (no shared edge through it). An open fan (a boundary vertex)
    is one fan. Triangles in `skip` are left out."""
    tri = np.flatnonzero(~skip)
    tri_ids = ids[triangles[tri]]
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_edge = {}
    for t, row in zip(tri, side_edges[tri]):
        for k in range(3):
            by_edge.setdefault(int(row[k]), []).append((int(t), k))
    for faces in by_edge.values():
        for (t0, k0), (t1, _) in zip(faces, faces[1:]):
            for v in (int(ids[triangles[t0][k0]]), int(ids[triangles[t0][(k0 + 1) % 3]])):
                parent[find((v, t1))] = find((v, t0))
    fans = {}
    for t, row in zip(tri, tri_ids):
        for v in row:
            fans.setdefault(int(v), set()).add(find((int(v), int(t))))
    return sorted(v for v, roots in fans.items() if len(roots) > 1)


def check_mesh(model: Soup, tol: dict, ranges: dict, slabs=None, plate=None, structures=()) -> dict:
    """Edge- and vertex-manifold (one face fan per vertex, issue #57), no n-gons, no overlapping faces, and open edges only where the pattern
    roof-inset-plane allows them (user rule 2026-10-10): the bottom ring and, per roof, the joint of an
    inset roof plane (its outline and the foot of the faces it is inset into). Parts made only of
    open_part_groups are left out of the open-edge rule. A mesh named DECOR_MESH is facade decor of its own
    (pattern facade-decor-inset: the body is never cut; user 2026-10-13, 2a): it is left out of these checks -
    its boxes may meet and overlap - and check_decor reads it. An open loop flat on a horizontal face of the
    model at its height is closed by contact ("seated": a wall standing on a slab, user 2026-10-13); a
    separate closed part whose top lies at a slab level over the slab's region is that slab (a slab box)."""
    left_out = 0
    if model.mesh_index is not None and DECOR_MESH in model.mesh_names:
        keep = model.mesh_index != model.mesh_names.index(DECOR_MESH)
        left_out = int((~keep).sum())
        model = _sub_soup(model, keep)
    ids = weld(model.vertices, tol["weld_m"])
    _, counts, side_edges = edge_uses(model.triangles, ids)
    part = parts(model.triangles, ids)
    groups = np.array([_group_of(int(m), ranges) for m in model.material_ids], dtype=object)
    open_ok = {p for p in np.unique(part) if set(groups[part == p]) <= set(tol["open_part_groups"])}
    tri_open = np.array([p in open_ok for p in part], dtype=bool)
    boundary = np.zeros(len(counts), dtype=bool)
    boundary[np.unique(side_edges[~tri_open][counts[side_edges[~tri_open]] == 1])] = True
    loops = open_loops(model, ids, counts, side_edges, tri_open, tol, ranges, structures)
    # every slab is inset (user rule 2026-10-10). With the spec's slabs known (a list): a slab joint at a
    # level the spec implies no slab at is not allowed, each slab level needs a joint, and no up-facing
    # face of the model may lie flat at a slab level - that is a solid slab beside an inset one
    # (Codex review 1 of PR #63). slabs=None: the spec is unknown, joints are only allowed.
    not_inset, solid = [], {}
    if slabs is not None:
        for lp in loops:
            if lp["kind"] in ("roof-foot", "roof-plane") and lp["level"] not in slabs:
                lp["kind"], lp["allowed"] = "other", False
        inset = {lp["level"] for lp in loops if lp["kind"] == "roof-plane" and lp["allowed"]}
        c = model.corners()
        n = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
        up = n[:, 2] > 0.99 * np.maximum(np.linalg.norm(n, axis=1), 1e-12)
        boxes = _slab_boxes(model, part, counts, side_edges)
        boxed = set()
        for name in slabs:                             # with no inset joint at a level, a separate closed part
            lz, region = model.levels.get(name), slabs[name] if isinstance(slabs, dict) else None   # topped at it
            if lz is None or name in inset:            # is that slab; beside a joint it stays a solid slab
                continue                               # (review 2 of PR #63)
            top = boxes & up & (np.abs(c[:, :, 2] - lz).max(axis=1) <= tol["weld_m"])
            cover = shapely.union_all([shapely.Polygon(t[:, :2]) for t in c[top] if shapely.Polygon(t[:, :2]).area > 0]
                                      or [shapely.Polygon()])
            if top.any() and (region is None or cover.intersection(region).area >= 0.9 * region.area):
                boxed.add(name)
        inset |= boxed
        mid = c.mean(axis=1)
        for name in slabs:
            lz = model.levels.get(name)
            mine = up & ~boxes if name in boxed else up       # a slab box's own top is no solid slab
            flat = mine & (np.abs(c[:, :, 2] - lz).max(axis=1) <= tol["weld_m"]) if lz is not None else up & False
            region = slabs[name] if isinstance(slabs, dict) else None
            if region is None:
                area = float(np.linalg.norm(n[flat], axis=1).sum() / 2)
            else:                                      # only the part inside the slab's own region counts (a cap
                inner = region.buffer(-tol["weld_m"])  # of a lower terrace may lie there), whatever the
                area = sum(shapely.Polygon(t[:, :2]).intersection(inner).area   # triangulation (review 3 of PR #63)
                           for t in c[flat] if shapely.Polygon(t[:, :2]).area > 0)
            if area > tol["weld_m"] ** 2:
                solid[name] = round(area, 4)
        not_inset = [name for name in slabs if name not in inset or name in solid]
    # the plates match the building's plate_gap_m / plate_overlap_m (spec, user 2026-10-10) within plate_tol_m
    plate_off = []
    if plate is not None:
        gap_s, overlap_s = plate
        for lp in loops:
            if lp["kind"] == "roof-plane" and lp["allowed"]:   # raw values, rounded only in the report
                gap = lp["_z"] - model.levels[lp["level"]]       # (review 1 of PR #64)
                lp["gap_m"] = round(gap, 4)
                limit = tol["plate_tol_m"] + 1e-9               # the limit itself passes (review 2 of PR #64)
                if abs(gap - gap_s) > limit or abs(lp["_embed"] - overlap_s) > limit:
                    plate_off.append({"level": lp["level"], "gap_m": round(gap, 4), "overlap_m": lp["embed_m"]})
    bad_loops = [lp for lp in loops if not lp["allowed"]]
    for lp in loops:
        lp.pop("_z", None)
        lp.pop("_embed", None)
    non_manifold = int((counts > 2).sum())
    fan_v = fan_vertices(model.triangles, ids, side_edges, tri_open)
    boundary_n = int(boundary.sum())
    corners = model.corners()
    faces = [{"object": "model", "index": i, "points": c.tolist()} for i, c in enumerate(corners)]   # decor left out
    # an overlap is a crossing deeper than the weld (user 2026-10-14): two faces within weld_m are one weld; an
    # inset 5 mm off a face (plate_gap_m) is no overlap
    overlaps = near_parallel_overlaps(faces, tol["weld_m"])
    if model.polygon_sizes is None:
        ngons, ngon_measured = None, False
    else:
        ngons, ngon_measured = int((model.polygon_sizes > 4).sum()), True
    details = {"non_manifold_edges": non_manifold, "non_manifold_vertices": len(fan_v),
               "non_manifold_vertex_points": [[round(float(c), 4) for c in model.vertices[ids == v][0]] for v in fan_v[:20]],
               "boundary_edges": boundary_n, "open_loops": loops, "slabs": None if slabs is None else list(slabs), "slabs_not_inset": not_inset,
               "solid_slab_m2": solid, "plates_off_spec": plate_off,
               "open_parts_allowed": len(open_ok), "ngons": ngons, "collision_meshes_left_out": model.collisions,
               "triangles_in_polygons": None if model.polygon_sizes is None else int((model.polygon_sizes == 3).sum()),
               "overlap_pairs": len(overlaps), "overlaps": overlaps[:20], "decor_triangles_left_out": left_out}
    ok = (non_manifold <= tol["non_manifold_edges_max"] and not fan_v and not bad_loops and not not_inset
          and not plate_off
          and len(overlaps) <= tol["overlap_pairs_max"] and (ngons or 0) <= tol["ngons_max"])
    if not ngon_measured and ok:
        return result("mesh", False, None, None, {**details, "why": "dump has no polygon_sizes matching its triangles"},
                      measured=False)
    return result("mesh", ok, {"non_manifold": non_manifold, "non_manifold_vertices": len(fan_v), "boundary": boundary_n,
                               "open_loops_not_allowed": len(bad_loops), "slabs_not_inset": len(not_inset),
                               "overlaps": len(overlaps), "ngons": ngons},
                  None, details)


DECOR_MESH = "decor"


def _sub_soup(model: Soup, keep) -> Soup:
    """The soup of the kept triangles (vertices unchanged)."""
    return Soup(model.vertices, model.triangles[keep], model.material_ids[keep],
                None if model.polygon_sizes is None else _sizes_of(model, keep), model.levels, model.collisions,
                model.mesh_names, model.mesh_index[keep])


def _sizes_of(model: Soup, keep):
    """Polygon sizes of the kept triangles; a polygon is kept whole or not at all."""
    out, k = [], 0
    for n in model.polygon_sizes:
        span = keep[k:k + int(n) - 2]
        if span.all():
            out.append(int(n))
        elif span.any():
            return None
        k += int(n) - 2
    return np.asarray(out, dtype=int)


def _seat(model: Soup, loops, w):
    """Mark open loops of no other kind that lie flat on a horizontal face of the model at their height as seated."""
    c = model.corners()
    n = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
    flat = np.abs(n[:, 2]) > 0.99 * np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    zc = c[:, :, 2].mean(axis=1)
    for lp in loops:
        if lp["kind"] != "other" or not lp["_segs"]:
            continue
        at = flat & (np.abs(zc - lp["_z"]) <= w)
        if not at.any():
            continue
        faces = shapely.union_all([shapely.Polygon(t[:, :2]) for t in c[at] if shapely.Polygon(t[:, :2]).area > 0]
                                  or [shapely.Polygon()]).buffer(w)
        if all(faces.covers(shapely.Point(*((s[0] + s[1]) / 2))) for s in lp["_segs"]):
            lp["kind"] = "seated"


def _slab_boxes(model: Soup, part, counts, side_edges):
    """Triangles of separate closed parts (no open edge) other than the largest part: slab boxes, decks."""
    if len(part) == 0:
        return np.zeros(0, dtype=bool)
    ids, sizes = np.unique(part, return_counts=True)
    largest = ids[sizes.argmax()]
    closed = {p for p in ids if p != largest and (counts[side_edges[part == p]] == 2).all()}
    return np.array([p in closed for p in part], dtype=bool)


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


def slabs(spec: Spec) -> dict:
    """Slabs that must be inset (user rule 2026-10-10), level name -> plan region: the roof inside the top
    floor's contour when it has a parapet, every terrace on its ledge (the floor below minus its own floor)."""
    floors = spec.expanded_floors()
    contour = {f.level: shapely.Polygon(f.contour) for f in floors}
    names = [lv.name for lv in spec.levels]
    out = {}
    if spec.roof and spec.roof.parapet_h_m > 0 and floors:
        out[names[-1]] = contour[floors[-1].level]
    for t in spec.terraces:
        k = names.index(t.level)
        if names[k - 1] in contour and t.level in contour:
            out[t.level] = contour[names[k - 1]].difference(contour[t.level])
    return out


FACE_M = 0.001        # a body vertex on the wall face within this; one line of the body within this


def _plan(t3):
    """A part's own geometry in the plan: its non-vertical faces as polygons, its vertical faces as segments.
    Nothing is filled: a hole, a recess or a missing cap adds no area (reviews 1-4 of #78)."""
    xy = t3[..., :2]
    e1, e2 = xy[:, 1] - xy[:, 0], xy[:, 2] - xy[:, 0]
    flat = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) > 1e-12
    out = [shapely.Polygon(q) for q in xy[flat]]
    for q in xy[~flat]:                              # a vertical face is a segment: its two farthest corners
        a, b = max(((0, 1), (1, 2), (2, 0)), key=lambda ij: float(np.linalg.norm(q[ij[0]] - q[ij[1]])))
        if np.linalg.norm(q[a] - q[b]) > 1e-12:
            out.append(shapely.LineString(q[[a, b]]))
    return shapely.union_all(out)


def _pieces_outside(plan, body, weld_m) -> int:
    """Connected pieces of a part's own geometry outside the body: closer than the weld distance is one piece,
    a bit smaller than it is a weld, not a piece (no threshold of its own; review 2 of #78)."""
    out = plan.difference(body)
    if out.is_empty:
        return 0
    bits = [g for g in getattr(out, "geoms", [out]) if not g.is_empty]
    group = list(range(len(bits)))                   # grouped by their real distance, not a faceted buffer

    def root(i):                                     # (review 5 of #78)
        while group[i] != i:
            group[i] = group[group[i]]
            i = group[i]
        return i
    for i, j in zip(*shapely.STRtree(bits).query(bits, predicate="dwithin", distance=weld_m)):
        group[root(int(i))] = root(int(j))
    bounds = {}
    for i, g in enumerate(bits):
        x0, y0, x1, y1 = g.bounds
        b = bounds.get(root(i), (x0, y0, x1, y1))
        bounds[root(i)] = (min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1))
    return sum(max(x1 - x0, y1 - y0) > weld_m for x0, y0, x1, y1 in bounds.values())


def _matches(e, d, dt, elev, contours):
    """A model element read back (d) is the spec element (e) within dt: same kind, same wall line (whatever
    storey it is filed under), same absolute height, extent and projection."""
    if e.kind != d["kind"]:
        return False
    ez0, dz0 = elev[e.level] + e.z_m, elev[d["level"]] + d["z_m"]
    if abs(ez0 - dz0) > dt or abs(e.h_m - d["h_m"]) > dt:
        return False
    if e.kind == "column":
        return all(abs(x - y) <= dt for x, y in zip(e.footprint, d["footprint"]))
    ea, eu, en = _wall(contours[e.level], e.wall)
    da, du, dn = _wall(contours[d["level"]], d["wall"])
    if eu @ du < 1 - 1e-6 or abs(float((da - ea) @ en)) > dt:
        return False
    dx = float((da - ea) @ eu) + d["x_m"]
    return all(abs(x - y) <= dt for x, y in ((e.x_m, dx), (e.w_m, d["w_m"]), (e.projection_m, d["projection_m"])))


def check_decor(model: Soup, spec: Spec, tol: dict, ranges: dict) -> dict:
    """Facade decor (pattern facade-decor-inset, spec v0.5). The model's decor is read back as the extractor
    reads a source (dt_ai.spec.decor: boxes, merged pieces, run-ins, corner arms; reviews of PR #75) and
    matched one to one with the spec within decor_tol_m: every geometry element built, with ids of the
    attachment group (its own id when the spec gives one); nothing built over a texture element; nothing the
    spec does not list; no decor the extractor cannot read. Built elements keep plate_gap_m off every opening
    of their wall line, do not cut the body (no body vertex on their outline that is not on a line the body
    has anyway), meet another element only by a run-in of at most decor_inset_m + decor_tol_m and never with
    a face in the plane of the other's face. No decor in the spec: nothing to check (pass)."""
    if not spec.decor:
        return result("decor", True, 0, 0, {"elements": []})
    from dt_ai.spec import decor as reader                 # one reading for the extractor and the checker
    dt, weld_m = tol["decor_tol_m"], tol["weld_m"]
    # decor ids by the element's material (user 2026-10-12): metal 16-20, plaster / stone / tile 26-30; the
    # finish behind an id is the object's materials table's (ADR 0001), so the check is the group, one per element
    groups = [ranges["groups"][g] for g in ("metal", "attachment")]
    attachment = frozenset(i for g in groups for i in range(g["first"], g["last"] + 1))
    names = [lv.name for lv in spec.levels]
    elev = {lv.name: lv.elev_m for lv in spec.levels}
    contours = {f.level: f.contour for f in spec.expanded_floors()}
    storeys = [contours[n] for n in names[:-1]]
    polys = [shapely.Polygon(c) for c in storeys]
    tri_part = parts(model.triangles, weld(model.vertices, weld_m))
    area = np.linalg.norm(np.cross(*(model.corners()[:, k] - model.corners()[:, 0] for k in (1, 2))), axis=1) / 2
    labels = np.unique(tri_part)
    body = labels[np.argmax([area[tri_part == p].sum() for p in labels])]
    others = [np.flatnonzero(tri_part == p) for p in labels if p != body]
    levels = [{"name": lv.name, "elev_m": lv.elev_m} for lv in spec.levels]
    got, asked, _, owned = reader.extract(model.vertices, model.triangles, model.material_ids, others, levels, storeys,
                                          polys, spec.plate_gap_m, attachment, with_parts=True)
    rows = [{"index": k, "kind": e.kind, "level": e.level, "texture": e.texture, "problems": []}
            for k, e in enumerate(spec.decor)]
    used = set()
    for row, e in zip(rows, spec.decor):
        if e.texture:
            continue
        k = next((k for k, d in enumerate(got) if k not in used and not d.get("texture") and _matches(e, d, dt, elev, contours)), None)
        if k is None:
            row["problems"].append("not built")
            continue
        used.add(k)
        row["read"], row["k"] = got[k], k
        ids = sorted({int(m) for m in model.material_ids[owned[k]]})
        row["material_ids"] = ids
        one_group = len({next((g["first"] for g in groups if g["first"] <= i <= g["last"]), None) for i in ids}) == 1
        if not set(ids) <= attachment or not one_group or (e.material_id is not None and ids != [e.material_id]):
            row["problems"].append(f"ids {ids}")
    def over_texture(d):
        """The spec texture element a read-back element lies over (wall line, absolute height), or None."""
        if d.get("wall") is None:
            return None
        da, du, dn = _wall(contours[d["level"]], d["wall"])
        dz0 = elev[d["level"]] + d["z_m"]
        for row, e in zip(rows, spec.decor):
            if not e.texture:
                continue
            ea, eu, en = _wall(contours[e.level], e.wall)
            if eu @ du < 1 - 1e-6 or abs(float((da - ea) @ en)) > dt:
                continue
            dx = float((da - ea) @ eu) + d["x_m"]
            ez0 = elev[e.level] + e.z_m
            if (min(e.x_m + e.w_m, dx + d["w_m"]) > max(e.x_m, dx) + FACE_M
                    and min(ez0 + e.h_m, dz0 + d["h_m"]) > max(ez0, dz0) + FACE_M):
                return row
        return None

    for k, d in enumerate(got):                          # read back but not in the spec (or over a texture element);
        if k in used:                                    # a read-back element is built geometry whatever its
            continue                                     # projection (review 3 of PR #75)
        over = over_texture(d)
        if over is not None:
            over["problems"].append("texture built as geometry")
        else:
            rows.append({"index": None, "kind": d["kind"], "level": d["level"],
                         "problems": [f"decor the spec does not list ({d['kind']} at {d['level']} z {d['z_m']})"]})
    for q in asked:                                      # over 0.8 m is an attachment candidate, no decor (EG2,
        if q["kind"] == "decor-deep":                    # user 2026-10-12)
            continue
        rows.append({"index": None, "kind": q["kind"], "level": q["levels"][0],
                     "problems": [f"decor the extractor cannot read ({q['kind']}, {q['count']} piece(s))"]})
    openings = opening_planes(spec, ("window", "door", None))
    decor_owned = np.zeros(len(model.triangles), bool)
    for o in owned:
        decor_owned[o] = True
    bv = np.unique(model.triangles[~decor_owned])        # everything but the decor read back
    # a box on one wall set into the body deeper than decor is (reader.EMBED_MAX_M) is decor-like geometry the
    # spec does not list, read or not (review 3 of PR #75); attachments - a coping ring round the roof, ladder
    # rungs, anything deeper than 0.8 m - are no decor (K01, PR #76)
    stray = 0
    for part in others:
        free = part[~decor_owned[part]]
        if not len(free):
            continue
        t3 = model.corners()[free]
        p = model.vertices[np.unique(model.triangles[free])]
        z0 = float(p[:, 2].min())
        z1 = float(p[:, 2].max())
        storey = reader._storey(levels, z0)
        bands = [i for i in range(len(storeys))          # every storey it stands in by more than a weld
                 if min(z1, levels[i + 1]["elev_m"]) - max(z0, levels[i]["elev_m"]) > weld_m] or [storey]
        plan = _plan(t3)                                 # its own geometry, not its bounding rectangle (#78)
        for a, u, n, length in reader._walls(storeys[storey]):
            s, dd = (p[:, :2] - a) @ u, (p[:, :2] - a) @ n
            # set into the body deeper than decor is, and not through it: in every storey it stands in, the
            # part of its plan outside the body is one piece (in front of the wall, past a corner or into a
            # concave one); a box through the building (a coping ring round the roof) comes out on the far side
            # too and is an attachment (user 2026-10-12: against the body between storey contours, no new number)
            if (dd.min() < -reader.EMBED_MAX_M and 0 < dd.max() <= reader.ATTACHMENT_FROM_M
                    and s.max() > FACE_M and s.min() < length - FACE_M
                    and all(_pieces_outside(plan, polys[i], weld_m) == 1 for i in bands)
                    and reader._is_box(t3, u, n, float(a @ n)) is not None):
                stray += len(free)
                break
    if stray:
        rows.append({"index": None, "kind": "unspecified", "level": None,
                     "problems": [f"{stray} triangles set into the body and standing out of it that no spec decor lists"]})
    for row, e in zip(rows, spec.decor):
        if e.kind == "column" or "read" not in row:
            continue
        a, u, n = _wall(contours[e.level], e.wall)
        d = row["read"]
        z0 = elev[d["level"]] + d["z_m"]
        da, _, _ = _wall(contours[d["level"]], d["wall"])
        x0 = float((da - a) @ u) + d["x_m"]                # in the spec wall's frame
        rect = shapely.box(x0, z0, x0 + d["w_m"], z0 + d["h_m"])
        for r in openings:                               # openings on its wall line, any floor
            oa, ou, _ = _wall(r["contour"], r["opening"].wall)
            if ou @ u < 1 - 1e-6 or abs(float((oa - a) @ n)) > dt:
                continue
            os0 = float((oa - a) @ u) + r["opening"].x_m
            gap = rect.distance(shapely.box(os0, r["z0"], os0 + r["opening"].w_m, r["z0"] + r["opening"].h_m))
            row["opening_gap_m"] = min(row.get("opening_gap_m", gap), round(gap, 4))
            if gap < spec.plate_gap_m - 1e-4:
                row["problems"].append(f"{gap:.4f} m from an opening")
        # the body is not cut: a body vertex on its outline only on a line the body has anyway
        p = model.vertices[bv]
        s, dd, z = (p[:, :2] - a) @ u, (p[:, :2] - a) @ n, p[:, 2]
        ms0, ms1, mz0, mz1 = x0, x0 + d["w_m"], z0, z0 + d["h_m"]
        face = np.abs(dd) <= FACE_M
        under = face & (s >= ms0 - FACE_M) & (s <= ms1 + FACE_M) & (z >= mz0 - FACE_M) & (z <= mz1 + FACE_M)
        cut = 0
        wall_pts = np.asarray([q[:2] for q in contours[e.level]], float)
        wall_len = float(np.linalg.norm(wall_pts[(e.wall + 1) % len(wall_pts)] - wall_pts[e.wall]))
        ends = face & ((np.abs(s) <= FACE_M) | (np.abs(s - wall_len) <= FACE_M))
        for zl in (mz0, mz1):                            # horizontal outline edges: a body line runs on along this
            on = under & (np.abs(z - zl) <= FACE_M)      # wall or reaches its corners (review 3: not another wall)
            elsewhere = (np.abs(z - zl) <= FACE_M) & ((face & ~under) | ends)
            cut += int(on.sum()) if on.any() and not elsewhere.any() else 0
        for sl in (ms0, ms1):                            # vertical outline edges
            on = under & (np.abs(s - sl) <= FACE_M)
            elsewhere = face & (np.abs(s - sl) <= FACE_M) & ((z < mz0 - FACE_M) | (z > mz1 + FACE_M))
            cut += int(on.sum()) if on.any() and not elsewhere.any() else 0
        if cut:
            row["problems"].append(f"body cut: {cut} body vertices on its outline")
    # meetings: a run-in of at most decor_inset_m (+ decor_tol_m), no face in the plane of another's face
    built = [(row, owned[row["k"]]) for row in rows if "read" in row]
    for i, (ra, ta) in enumerate(built):
        for rb, tb in built[i + 1:]:
            ca, cb = model.vertices[np.unique(model.triangles[ta])], model.vertices[np.unique(model.triangles[tb])]
            za, zb = (ca[:, 2].min(), ca[:, 2].max()), (cb[:, 2].min(), cb[:, 2].max())
            zov = min(za[1], zb[1]) - max(za[0], zb[0])
            fa, fb = shapely.MultiPoint(ca[:, :2]).convex_hull, shapely.MultiPoint(cb[:, :2]).convex_hull
            meet = fa.intersection(fb)
            if zov < -FACE_M or fa.distance(fb) > FACE_M:
                continue
            if meet.area > FACE_M * FACE_M and zov > FACE_M:
                box = meet.minimum_rotated_rectangle
                side = min(np.linalg.norm(np.diff(np.asarray(box.exterior.coords)[:3], axis=0), axis=1)) \
                    if box.geom_type == "Polygon" else 0.0
                depth = min(float(side), float(zov))
                if depth > DECOR_INSET_M + dt:
                    ra["problems"].append(f"runs {depth:.3f} m into decor element {rb['index']} (over decor_inset_m)")
            elif ra["kind"] != "column" and rb["kind"] != "column" and spec.decor[ra["index"]].wall == \
                    spec.decor[rb["index"]].wall and spec.decor[ra["index"]].level == spec.decor[rb["index"]].level:
                ra["problems"].append(f"butt joint with decor element {rb['index']}: a face in the plane of its face")
    bad = sum(bool(r["problems"]) for r in rows)
    return result("decor", bad == 0, bad, 0, {"elements": [{k: v for k, v in r.items() if k != "k"} for r in rows]})


def run(model: Soup, etalon: Soup, spec: Spec, tol: dict, ranges: dict | None = None,
        source_class: str | None = None) -> dict:
    """All §5 checks; tol is the `geometry` block of tolerances.json. The weld is the building's (spec weld_m,
    user 2026-10-13): open edges, T-junctions and non-manifold are counted after welding the readback by it."""
    ranges = ranges or load_ranges()
    tol = {**tol, "weld_m": spec.weld_m}
    checks = [check_bbox(model, etalon, tol), check_levels(model, etalon, spec, tol),
              check_floor_areas(model, etalon, spec, tol, "spec" if source_class == "panelised" else "etalon"),
              check_silhouettes(model, etalon, tol),
              check_mesh(model, tol, ranges, slabs(spec), (spec.plate_gap_m, spec.plate_overlap_m),
                         [(shapely.Polygon(rs.outline), spec.levels[-1].elev_m) for rs in spec.roof_structures]),
              check_budget(model, tol),
              check_opening_planes(model, spec, tol, ranges), check_material_ids(model, tol, ranges),
              check_decor(model, spec, tol, ranges)]
    return {"passed": all(c["status"] == "pass" for c in checks),
            "failed": [c["id"] for c in checks if c["status"] == "fail"],
            "not_measured": [c["id"] for c in checks if c["status"] == "not_measured"],
            "checks": checks}

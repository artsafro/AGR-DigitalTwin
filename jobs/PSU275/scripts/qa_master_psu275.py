"""Master-geometry QA (copy of jobs/KPP1/scripts/qa_master.py, accepted case KPP1 v005; PSU275 change:
leak rays never start inside the building masses, because the PSU275 shell is open inside by project
rule; set PSU275_MASSES=<masses.json>). Original description:
Master-geometry QA for KPP1: quads, quad size, gaps (T-junctions, open edges), flipped normals.

Usage: blender --background --factory-startup <file.blend|-> --python qa_master.py -- <out.json> [fbx]
With an FBX path the scene is reset and the FBX is imported first (readback of an export).

Checks per mesh object (UCX_* skipped for normals/size):
- non_quads: faces with != 4 verts (project rule: editable master 100 % quads);
- oversize: quads with any edge > MAX_EDGE (user rule 2026-10-07: quads up to 4 x 4 m);
- t_junctions: a vertex lying on the interior of an edge of the same object (distance < 1 mm,
  not an endpoint, not connected to it) -> a crack in the surface unless the edge is split there;
- open_edges: boundary edges (1 face). Reported with a count of those NOT covered by another face of
  the same object within 1 mm (uncovered open edges = visible slits/holes);
- flipped: ray probe. From each face centre (+1 mm along the normal) a ray is cast along the normal;
  a hit on the BACK of a face of a closed body means the face looks into material -> wrong normal.
  A second ray from outside (centre + 50 m along the normal, pointing back) that reaches the BACK of
  this face first means the face is seen from behind from the outside.
"""
import bpy, bmesh, sys, os, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

MAX_EDGE = 4.0 + 1e-4
TOL = 0.001

argv = sys.argv[sys.argv.index("--") + 1:]
_masses = json.load(open(os.environ["PSU275_MASSES"], encoding="utf-8"))["masses"] if os.environ.get("PSU275_MASSES") else []


def inside_masses(p):
    return any(m["x"][0] < p.x < m["x"][1] and m["y"][0] < p.y < m["y"][1] and p.z < m["top"] for m in _masses)


out = argv[0]
if len(argv) > 1:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=argv[1])

depsgraph = bpy.context.evaluated_depsgraph_get()
scene_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"
              and not any(c.name.startswith("REF_") for c in o.users_collection)]


def world_bm(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.transform(o.matrix_world)
    bm.normal_update()
    return bm


def seg_dist(p, a, b):
    ab = b - a
    t = (p - a).dot(ab) / max(ab.length_squared, 1e-18)
    if t <= 1e-6 or t >= 1 - 1e-6:
        return None
    return (a + ab * t - p).length


report = {"objects": []}
# one BVH over all visible meshes (non-UCX) for the normal probes
all_v, all_f, owner = [], [], []
for o in scene_objs:
    if o.name.startswith("UCX_"):
        continue
    bm = world_bm(o)
    base = len(all_v)
    all_v += [v.co.copy() for v in bm.verts]
    for f in bm.faces:
        all_f.append([base + v.index for v in f.verts])
        owner.append((o.name, f.index))
    bm.free()
bvh_all = BVHTree.FromPolygons(all_v, all_f, epsilon=0.0) if all_f else None
fnorm = []
for poly in all_f:
    pts = [all_v[i] for i in poly]
    n = Vector()
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
    fnorm.append(n.normalized())

# outside visibility: orthographic ray grids from many directions; first hit must be a front face
import math
lo = Vector([min(v[i] for v in all_v) for i in range(3)]) if all_v else Vector()
hi = Vector([max(v[i] for v in all_v) for i in range(3)]) if all_v else Vector()
ctr, rad = (lo + hi) / 2, (hi - lo).length / 2 + 1.0
STEP = 0.2
GRADE = -0.05
FOOT = (lo.x, hi.x, lo.y, hi.y) if all_v else (0, 0, 0, 0)  # conservative: whole bbox
dirs = []
for el in (-60, -35, -10, 10):  # elevation of the view direction (negative = looking down)
    for k in range(16):
        az = 2 * math.pi * k / 16 + math.radians(7)  # off-axis: no ray lies in a facade plane
        dirs.append(Vector((math.cos(az) * math.cos(math.radians(el)), math.sin(az) * math.cos(math.radians(el)),
                            math.sin(math.radians(el)))))
dirs.append(Vector((0.05, 0.03, -1)).normalized())
for o in scene_objs:
    bm = world_bm(o)
    bm.verts.ensure_lookup_table()
    r = {"object": o.name, "faces": len(bm.faces), "tris": sum(len(f.verts) - 2 for f in bm.faces)}
    r["non_quads"] = [[round(c, 3) for c in f.calc_center_median()] + [len(f.verts)]
                      for f in bm.faces if len(f.verts) != 4]
    if not o.name.startswith("UCX_"):
        conc = 0
        for f in bm.faces:
            if len(f.verts) == 4:
                v = [l.vert.co for l in f.loops]
                if min((v[(i + 1) % 4] - v[i]).cross(v[(i + 2) % 4] - v[(i + 1) % 4]).dot(f.normal) for i in range(4)) <= 1e-9:
                    conc += 1
        r["concave_or_twisted_quads"] = conc
        over = [f for f in bm.faces if max(e.calc_length() for e in f.edges) > MAX_EDGE]
        r["oversize"] = len(over)
        r["oversize_samples"] = [[round(c, 2) for c in f.calc_center_median()] +
                                 [round(max(e.calc_length() for e in f.edges), 3)] for f in over[:15]]
        r["max_edge"] = round(max((e.calc_length() for e in bm.edges), default=0), 3)
    # T-junctions
    kd = KDTree(len(bm.verts))
    for v in bm.verts:
        kd.insert(v.co, v.index)
    kd.balance()
    tj = []
    for e in bm.edges:
        a, b = e.verts[0].co, e.verts[1].co
        mid, half = (a + b) / 2, (b - a).length / 2 + TOL
        for co, idx, _ in kd.find_range(mid, half):
            v = bm.verts[idx]
            if v in e.verts:
                continue
            d = seg_dist(co, a, b)
            if d is not None and d < TOL and (co - a).length > TOL and (co - b).length > TOL:
                tj.append([round(c, 3) for c in co])
    r["t_junctions"] = len(tj)
    r["t_junction_samples"] = tj[:20]
    # open edges, covered or not
    bnd = [e for e in bm.edges if len(e.link_faces) == 1]
    bvh = BVHTree.FromBMesh(bm, epsilon=0.0)
    unc = []
    for e in bnd:
        own = e.link_faces[0]
        mid = (e.verts[0].co + e.verts[1].co) / 2
        hits = bvh.find_nearest_range(mid, TOL)
        if not any(h[2] != own.index for h in hits):
            unc.append([round(c, 3) for c in mid])
    # classify uncovered open edges: below grade (Ground hides), enclosed in a body (hidden), exposed
    cls = {"below_grade": 0, "enclosed": 0, "exposed": 0}
    exp = []
    axes = [Vector(d) for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
    for m in unc:
        p = Vector(m)
        if p.z < -0.05:
            cls["below_grade"] += 1
            continue
        inside = 0
        for d in axes:
            h = bvh_all.ray_cast(p + d * 0.0005, d, 1000.0) if bvh_all else (None,)
            if h[0] is not None and fnorm[h[2]].dot(d) > 0.2:
                inside += 1
        if inside >= 5:
            cls["enclosed"] += 1
        else:
            cls["exposed"] += 1
            exp.append(m)
    # leak probe: aim rays from outside at a point 1 mm beyond each exposed open edge (in the face plane);
    # a leak = the point is reachable from outside and the ray then escapes or meets a back face.
    leaks = []
    if bvh_all:
        fin_l = bm.faces.layers.int.get("finish")
        alpha_ids = {i for i, n in enumerate(o.get("finish_names", "").split(",")) if "Alpha" in n}
        for e in bnd:
            mid = (e.verts[0].co + e.verts[1].co) / 2
            if mid.z < -0.05:
                continue
            f = e.link_faces[0]
            if fin_l is not None and f[fin_l] in alpha_ids:
                continue  # free edge of an alpha-cut plane (railing, ladder): open air beyond, not a slit
            ed = (e.verts[1].co - e.verts[0].co).normalized()
            side = f.normal.cross(ed)
            if (f.calc_center_median() - mid).dot(side) > 0:
                side = -side
            tgt = mid + side * 0.001
            for d in dirs:
                org = tgt - d * 60.0
                if d.z > 0 and org.z < GRADE:
                    continue
                if inside_masses(org):
                    continue  # PSU275: the open shell interior is not "outside"
                h = bvh_all.ray_cast(org, d, 60.0 - 0.0005)
                if h[0] is not None:
                    continue  # occluded before reaching the slit
                h2 = bvh_all.ray_cast(tgt, d, 100.0)
                if h2[0] is None or fnorm[h2[2]].dot(d) > 1e-4:
                    leaks.append([round(x, 3) for x in mid] + [round(x, 2) for x in d])
                    break
    r["leaks"] = len(leaks)
    r["leak_samples"] = leaks[:40]
    r["open_uncovered_class"] = cls
    r["open_exposed_samples"] = exp[:400]
    r["open_edges"] = len(bnd)
    r["open_edges_uncovered"] = len(unc)
    r["open_uncovered_samples"] = unc[:20]
    bm.free()
    report["objects"].append(r)

# normals probe over all non-UCX faces
flip_in, flip_out, embedded = [], [], []
if bvh_all:
    for fi, poly in enumerate(all_f):
        c = sum((all_v[i] for i in poly), Vector()) / len(poly)
        n = fnorm[fi]
        hit = bvh_all.ray_cast(c + n * 0.001, n, 1000.0)
        if hit[0] is not None and hit[2] != fi and fnorm[hit[2]].dot(n) > 0.2 and hit[3] < 0.5:
            # looks at the back of a face within 0.5 m. If the ray backwards also meets a back face,
            # the face lies inside a closed body (constructive embed, hidden) -> not a flipped normal.
            back = bvh_all.ray_cast(c - n * 0.001, -n, 1000.0)
            if back[0] is not None and back[2] != fi and fnorm[back[2]].dot(-n) > 0.2:
                embedded.append([owner[fi][0]] + [round(x, 3) for x in c])
            else:
                flip_in.append([owner[fi][0]] + [round(x, 3) for x in c])
if bvh_all:
    for d in dirs:
        u = d.cross(Vector((0, 0, 1)) if abs(d.z) < 0.99 else Vector((1, 0, 0))).normalized()
        w = d.cross(u).normalized()
        n = int(rad / STEP)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                org = ctr - d * (rad + 1) + u * (i * STEP) + w * (j * STEP)
                if d.z > 0:  # looking up: the ray starts at grade, never under the building (Ground)
                    if org.z >= GRADE:
                        continue
                    org = org + d * ((GRADE - org.z) / d.z)
                    if FOOT[0] - 0.5 < org.x < FOOT[1] + 0.5 and FOOT[2] - 0.5 < org.y < FOOT[3] + 0.5:
                        continue
                hit = bvh_all.ray_cast(org, d, 3 * rad)
                if hit[0] is None or hit[0].z < -0.05:  # below grade is hidden by Ground
                    continue
                if fnorm[hit[2]].dot(d) > 1e-4:
                    flip_out.append([owner[hit[2]][0], owner[hit[2]][1]] + [round(x, 3) for x in hit[0]])
uniq = {}
for s_ in flip_out:
    uniq.setdefault((s_[0], s_[1]), s_)
flip_out = list(uniq.values())
report["normals_probe"] = {"faces": len(all_f), "looks_into_material": len(flip_in),
                           "embedded_hidden": len(embedded), "samples_embedded": embedded[:20],
                           "samples_in": flip_in[:30], "samples_in_all": flip_in, "back_faces_seen_from_outside": len(flip_out),
                           "samples_out": flip_out[:30], "samples_out_all": flip_out}
json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("QA-MASTER", json.dumps({o["object"]: {k: o[k] for k in o if not k.endswith("samples") and k != "non_quads"}
                               | {"non_quads": len(o["non_quads"])} for o in report["objects"]}, ensure_ascii=False))
print("QA-NORMALS", report["normals_probe"]["looks_into_material"], report["normals_probe"]["embedded_hidden"], report["normals_probe"]["back_faces_seen_from_outside"])

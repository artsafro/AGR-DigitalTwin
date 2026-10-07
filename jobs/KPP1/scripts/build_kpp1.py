"""Build the KPP1 VPM model in Blender stage by stage from the Revit FBX export.

Usage (headless):
  blender --background --factory-startup --python build_kpp1.py -- <src_dir> <census_dir> <out_dir> <stage>

Stages are cumulative and deterministic: stage N rebuilds stages 1..N and saves
KPP1_VPM_v00N_<name>.blend. Coordinates stay in Revit internal metres (FBX world);
VPM placement (pivot at plan centre, Z = 0.000) is applied only at publish.

Source facts (tmp/kpp1/census-v001, Revit 2025 copy of 26_KPP1_AR_MEP_RVT22):
- facade outer plane: vent-facade cassettes x -0.33..27.33, y -0.33..11.33;
- finish bands: plinth porcelain RAL 7004 up to +0.9, cassettes RAL 7047 0.9-2.7,
  RAL 5015 2.7-7.1, RAL 7047 7.1-8.1, RAL 5015 8.1-8.65 (parapet top);
- blind area (otmostka) top -0.10 -> body sunk to -1.20 (VPM: >= 1 m below grade);
- openings (stage 2, census/openings_spec.json from extract_openings.py):
  window surrounds of 200x75 mullions project 0.09 m (y -0.42..-0.22 on the south),
  curtain/window plane at -0.10 (depth 0.23), doors set in the same plane,
  perforated RAL 9016 cassettes flush with the facade (finish, not geometry, reg p.32 §7).
"""
import bpy, bmesh, sys, os, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vpm_uv  # noqa: E402  (stage 5: texel cuts, UDIM UVs, materials)
import vpm_ucx  # noqa: E402  (stage 6: UCX collision hulls)
import seal  # noqa: E402  (stage 5: weld + T-junction ring splits, quads only)

ADDRESS = "Kpp_1"  # placeholder until the real address/cadastral number is known
MAIN = f"SM_{ADDRESS}_Main"
GLASS = f"SM_{ADDRESS}_MainGlass"

X0, X1, Y0, Y1 = -0.33, 27.33, -0.33, 11.33
Z_BOTTOM, Z_TOP = -1.20, 8.65
BANDS = [(0.90, "Plinth_RAL7004"), (2.70, "Cassette_RAL7047"), (7.10, "Cassette_RAL5015"),
         (8.10, "Cassette_RAL7047"), (8.65, "Cassette_RAL5015_Top")]

# Opening depths, metres inward from the outer cassette plane (d < 0 projects outward).
D_SURROUND = -0.09   # front of 200x75 surround mullions
D_INFILL = 0.23      # curtain mullions / window frames / door leaves
D_GLASS = 0.26       # glass plane: 30 mm behind the frame face (project window library rule)
D_INTERIOR = 1.26    # dark interior placeholder 1 m behind glass (VPM: interiors -> solid walls)
WINDOW_FRAME = 0.07  # visible AGS68 frame+sash width around glass (assumed; not in Revit export)
INF = 99.0

FINISHES = {  # working finishes (internal ids); collapsed to M_<Address>_Main_1 at publish
    "Plinth_RAL7004": (0.33, 0.33, 0.32),
    "Cassette_RAL7047": (0.80, 0.80, 0.80),
    "Cassette_RAL5015": (0.05, 0.27, 0.55),
    "Cassette_RAL5015_Top": (0.05, 0.27, 0.55),
    "Roof_Top": (0.25, 0.25, 0.27),
    "Frame_RAL9016": (0.95, 0.95, 0.93),
    "Perforated_RAL9016": (0.85, 0.86, 0.86),
    "Door_RAL7004": (0.38, 0.38, 0.37),
    "Interior": (0.06, 0.06, 0.07),
    "Membrane_Logicroof": (0.55, 0.56, 0.57),
    "Walkway_Logicroof": (0.42, 0.43, 0.44),
    "Metal_RAL5015": (0.05, 0.27, 0.55),
    "Plastic_Black": (0.04, 0.04, 0.04),
    "Grille_RAL7004": (0.30, 0.30, 0.29),
    "Slat_RAL5015": (0.07, 0.30, 0.58),
    "Membrane_Solo": (0.12, 0.12, 0.13),
    "Asphalt": (0.20, 0.20, 0.21),
    "Railing_Alpha": (0.55, 0.56, 0.58),
    "Ladder_Alpha_RAL1021": (0.93, 0.74, 0.0),
    "Cage_Alpha_RAL1021": (0.85, 0.68, 0.0),
    "Glass": (0.55, 0.70, 0.75),
}

# Facade frames: point(u, z, d) and the outward normal.
FACADES = {
    "S": (lambda u, z, d: Vector((u, Y0 + d, z)), Vector((0, -1, 0)), Vector((1, 0, 0)), (X0, X1)),
    "N": (lambda u, z, d: Vector((u, Y1 - d, z)), Vector((0, 1, 0)), Vector((1, 0, 0)), (X0, X1)),
    "W": (lambda u, z, d: Vector((X0 + d, u, z)), Vector((-1, 0, 0)), Vector((0, 1, 0)), (Y0, Y1)),
    "E": (lambda u, z, d: Vector((X1 - d, u, z)), Vector((1, 0, 0)), Vector((0, 1, 0)), (Y0, Y1)),
}
UP = Vector((0, 0, 1))


class MeshBuilder:
    """Quad-only bmesh builder. Each piece() gets its own weld cache, so separate shells stay unwelded."""

    def __init__(self):
        self.bm = bmesh.new()
        self.layer = self.bm.faces.layers.int.new("finish")
        self.uvx = self.bm.faces.layers.int.new("uvx")       # 1 = explicit UVs in metres (layer UVM)
        self.uvm = self.bm.loops.layers.uv.new("UVM")
        self.names = []
        self.cache = {}
        self.weld = False
        self.weld_verts = []

    @property
    def finish(self):
        return self.names

    def piece(self, weld=False):
        """Start a new shell. weld=True marks its vertices for the exact-contact weld in to_object
        (body and opening reliefs only; stairs, decor and alpha planes are never welded)."""
        self.cache = {}
        self.weld = weld

    def v(self, p):
        k = (round(p.x, 5), round(p.y, 5), round(p.z, 5))
        if k not in self.cache:
            self.cache[k] = self.bm.verts.new(p)
            if self.weld:
                self.weld_verts.append(self.cache[k])
        return self.cache[k]

    def quad(self, pts, normal, finish, uvm=None):
        """Add a planar polygon (quad, or a triangle where unavoidable) facing `normal`.
        uvm: optional explicit UVs in metres per point (alpha planes)."""
        n = Vector()
        for a, b in zip(pts, pts[1:] + pts[:1]):  # Newell normal
            n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
        if n.dot(normal) < 0:
            pts = pts[::-1]
            uvm = uvm[::-1] if uvm else None
        f = self.bm.faces.new([self.v(p) for p in pts])
        if uvm:
            for l, uv in zip(f.loops, uvm):
                l[self.uvm].uv = uv
            f[self.uvx] = 1
        if finish not in self.names:
            self.names.append(finish)
        f[self.layer] = self.names.index(finish)

    def to_object(self, name, process=None, single_material=None):
        """process(bm, names) -> bm runs after the weld (stage 5 cuts/UVs). With single_material all
        faces use it; the finish stays as the integer face attribute `finish`."""
        # Weld only exact contacts between shells (opening walls meeting hole edges of the body).
        # Inputs are snapped to 1 mm, so 0.5 mm cannot collapse real thickness or openings.
        bmesh.ops.remove_doubles(self.bm, verts=[v for v in self.weld_verts if v.is_valid], dist=0.0005)
        if process:
            self.bm = process(self.bm, self.names)
        fl = self.bm.faces.layers.int["finish"]
        for f in self.bm.faces:
            f.material_index = 0 if single_material else f[fl]
        me = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, me)
        obj["finish_names"] = ",".join(self.names)  # finish attribute index -> name (QA; not exported)
        bpy.context.scene.collection.objects.link(obj)
        self.bm.to_mesh(me)
        self.bm.free()
        if single_material:
            me.materials.append(single_material)
            for n in ("UVM",):
                if n in me.uv_layers:
                    me.uv_layers.remove(me.uv_layers[n])
            if "uvx" in me.attributes:
                me.attributes.remove(me.attributes["uvx"])
        else:
            for f in self.names:
                me.materials.append(material(f))
        return obj


def material(name):
    m = bpy.data.materials.get("WIP_" + name)
    if m is None:
        m = bpy.data.materials.new("WIP_" + name)
        c = (*FINISHES[name], 1.0)
        m.diffuse_color = c
        m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = c
        if name == "Glass":
            m.diffuse_color = (*FINISHES[name], 0.35)
            bsdf.inputs["Alpha"].default_value = 0.35
            if hasattr(m, "surface_render_method"):
                m.surface_render_method = "BLENDED"
    return m


REVEAL = "Reveal"  # sentinel: reveals take the finish of the neighbouring cassette band (user, 2026-10-06)


def band(zc):
    return next((fin for top, fin in BANDS if zc < top), BANDS[-1][1])


def inside(uc, zc, r):
    return r[0] < uc < r[1] and r[2] < zc < r[3]


def cuts(values):
    return sorted({round(v, 4) for v in values})


# ---------------------------------------------------------------- stage 1/2: body
def load_spec(census):
    return json.load(open(os.path.join(census, "openings_spec.json"), encoding="utf-8"))


def body(mb, spec, closed=True, decor=False):
    """Facade shell with finish bands; holes for surrounds and doors when spec is given.

    closed=False (stage 3+): no top cap (parapet cap + roof take over) and no bottom cap (buried
    >= 1 m below grade, never visible), so u cuts no longer propagate to the opposite facade."""
    mb.piece(weld=True)
    holes = {f: [] for f in FACADES}
    portals = {f: [] for f in FACADES}
    if spec:
        for f, s in spec.items():
            holes[f] = [x["rect"] for x in s["surrounds"]] + [x["rect"] for x in s["doors"]]
            portals[f] = [x["rect"] for x in s["portals"]]
            if decor:
                holes[f] += [x["rect"] for x in s["features"]]
                portals[f] += s["grilles"]
    grilles = {f: (spec[f]["grilles"] if spec and decor else []) for f in FACADES}
    zs = cuts([Z_BOTTOM] + [z for z, _ in BANDS] + [v for f in FACADES for r in holes[f] + portals[f] for v in r[2:]])
    u_sn = cuts([X0, X1] + [v for f in "SN" for r in holes[f] + portals[f] for v in r[:2]])
    u_we = cuts([Y0, Y1] + [v for f in "WE" for r in holes[f] + portals[f] for v in r[:2]])
    for f, (P, out, _, _) in FACADES.items():
        us = u_sn if f in "SN" else u_we
        if not closed:
            lo, hi = FACADES[f][3]
            us = cuts([lo, hi] + [v for r in holes[f] + portals[f] for v in r[:2]])
        for i in range(len(us) - 1):
            for j in range(len(zs) - 1):
                u0, u1, z0, z1 = us[i], us[i + 1], zs[j], zs[j + 1]
                uc, zc = (u0 + u1) / 2, (z0 + z1) / 2
                if any(inside(uc, zc, r) for r in holes[f]):
                    continue
                fin = ("Grille_RAL7004" if any(inside(uc, zc, r) for r in grilles[f]) else
                       "Perforated_RAL9016" if any(inside(uc, zc, r) for r in portals[f]) else band(zc))
                mb.quad([P(u0, z0, 0), P(u1, z0, 0), P(u1, z1, 0), P(u0, z1, 0)], out, fin)
    for z, n, fin in ((Z_TOP, UP, "Roof_Top"), (Z_BOTTOM, -UP, "Plinth_RAL7004")) if closed else ():
        for i in range(len(u_sn) - 1):
            for j in range(len(u_we) - 1):
                x0, x1, y0, y1 = u_sn[i], u_sn[i + 1], u_we[j], u_we[j + 1]
                mb.quad([Vector((x0, y0, z)), Vector((x1, y0, z)), Vector((x1, y1, z)), Vector((x0, y1, z))], n, fin)


# ---------------------------------------------------------------- stage 2: openings
def relief(mb, gb, f, rect, extra_cuts, cell):
    """Height-field piece over `rect` on facade f.

    cell(uc, zc) -> list of solid depth intervals [(start, end, front_finish, side_finish)];
    the region around the rect is wall mass solid from d=0. Front faces are made at every
    interval start, side walls wherever exactly one neighbour is solid; walls deeper than the
    glass plane get the interior finish. Back faces are never visible from outside and are omitted.
    """
    mb.piece(weld=True)
    P, out, udir, _ = FACADES[f]
    us = cuts([rect[0], rect[1]] + [v for r in extra_cuts for v in r[:2] if rect[0] <= v <= rect[1]])
    zs = cuts([rect[2], rect[3]] + [v for r in extra_cuts for v in r[2:] if rect[2] <= v <= rect[3]]
              + [z for z, _ in BANDS if rect[2] < z < rect[3]])
    outside = [(0.0, INF, None, REVEAL)]
    nu, nz = len(us) - 1, len(zs) - 1
    grid = [[cell((us[i] + us[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2) for j in range(nz)] for i in range(nu)]
    get = lambda i, j: grid[i][j] if 0 <= i < nu and 0 <= j < nz else outside
    dirv = lambda du, dz, dd: udir * du + UP * dz - out * dd

    for i in range(nu):
        for j in range(nz):
            u0, u1, z0, z1 = us[i], us[i + 1], zs[j], zs[j + 1]
            for s, e, ff, sf in grid[i][j]:
                if ff == "Glass_Cell":
                    continue
                mb.quad([P(u0, z0, s), P(u1, z0, s), P(u1, z1, s), P(u0, z1, s)], out, ff)
            for s, e, ff, sf in grid[i][j]:
                if ff == "Glass_Cell":  # glass pane at D_GLASS, interior back plate deeper
                    gb.quad([P(u0, z0, D_GLASS), P(u1, z0, D_GLASS), P(u1, z1, D_GLASS), P(u0, z1, D_GLASS)], out, "Glass")
                    mb.quad([P(u0, z0, s), P(u1, z0, s), P(u1, z1, s), P(u0, z1, s)], out, "Interior")

    def solid(iv, d):
        return next((x for x in iv if x[0] <= d < x[1]), None)

    def walls(a, b, edge, toward_b, zc):
        """a, b: interval lists of the two cells; edge(d0, d1) -> 4 points; toward_b: unit normal a->b;
        zc(owner_is_a) -> height used to pick the cassette band of a reveal."""
        bp = cuts([x for iv in (a, b) for t in iv for x in t[:2] if x < INF] + [D_GLASS])
        for d0, d1 in zip(bp, bp[1:]):
            m = (d0 + d1) / 2
            sa, sb = solid(a, m), solid(b, m)
            if bool(sa) == bool(sb):
                continue
            owner, n = (sa, toward_b) if sa else (sb, -toward_b)
            fin = "Interior" if d0 >= D_GLASS - 1e-6 else owner[3]
            if fin == REVEAL:
                fin = band(zc(bool(sa)))
            mb.quad(edge(d0, d1), n, fin)

    for i in range(-1, nu):          # walls on constant-u lines
        u = us[i + 1]
        for j in range(nz):
            z0, z1 = zs[j], zs[j + 1]
            walls(get(i, j), get(i + 1, j),
                  lambda d0, d1: [P(u, z0, d0), P(u, z1, d0), P(u, z1, d1), P(u, z0, d1)], dirv(1, 0, 0),
                  lambda _a: (z0 + z1) / 2)
    for j in range(-1, nz):          # walls on constant-z lines
        z = zs[j + 1]
        for i in range(nu):
            u0, u1 = us[i], us[i + 1]
            walls(get(i, j), get(i, j + 1),
                  lambda d0, d1: [P(u0, z, d0), P(u1, z, d0), P(u1, z, d1), P(u0, z, d1)], dirv(0, 1, 0),
                  lambda owner_below: z - 1e-3 if owner_below else z + 1e-3)


def surround_cell(s):
    mullions = s["mullions"]
    bays = s["bays"]

    def cell(uc, zc):
        if any(inside(uc, zc, r) for r in mullions):
            return [(D_SURROUND, INF, "Frame_RAL9016", "Frame_RAL9016")]
        for b in bays:
            if inside(uc, zc, b["rect"]):
                glass = [[w[0] + WINDOW_FRAME, w[1] - WINDOW_FRAME, w[2] + WINDOW_FRAME, w[3] - WINDOW_FRAME]
                         for w in b["windows"]] + b["glass"]
                if any(inside(uc, zc, g) for g in glass):
                    return [(D_INTERIOR, INF, "Glass_Cell", "Interior")]
                return [(D_INFILL, D_GLASS, "Frame_RAL9016", "Frame_RAL9016"),
                        (D_INTERIOR, INF, "Interior", "Interior")]
        return [(0.0, INF, "Perforated_RAL9016", "Perforated_RAL9016")]  # pier: perforated cassette, flush
    return cell


def openings(mb, gb, spec, decor=False):
    for f, s in spec.items():
        cx = [v for _, r in canopy_rects() for v in r[:2]] if decor else []

        def feat(x):
            r = x["rect"]
            edge = lambda v: abs(v - r[0]) < 1e-3 or abs(v - r[1]) < 1e-3 or any(abs(v - c) < 1e-3 for c in cx)
            ms = []
            for m in x["mullions"]:
                u0 = m[0] + (INSET if edge(m[0]) else 0.0)   # step back from canopy / feature sides
                u1 = m[1] - (INSET if edge(m[1]) else 0.0)
                ms.append([u0, u1, m[2] - 0.01, m[3]])
            return dict(x, mullions=ms)
        for sur in s["surrounds"] + ([feat(x) for x in s["features"]] if decor else []):
            # feature mullions stand on the portal canopy (top +3.30): run 10 mm into it (embed)
            rects = sur["mullions"] + [b["rect"] for b in sur["bays"]]
            for b in sur["bays"]:
                rects += [[w[0] + WINDOW_FRAME, w[1] - WINDOW_FRAME, w[2] + WINDOW_FRAME, w[3] - WINDOW_FRAME]
                          for w in b["windows"]] + b["glass"]
            relief(mb, gb, f, sur["rect"], rects, surround_cell(sur))
        for d in s["doors"]:
            relief(mb, gb, f, d["rect"], [], lambda uc, zc: [(D_INFILL, INF, "Door_RAL7004", "Door_RAL7004")])


# ---------------------------------------------------------------- stage 3: roof
PARAPET_IN = 0.225     # inner parapet face at x/y 0.225 and 26.775 / 10.775 (Revit parapet walls)
PARAPET_TOP_IN = 8.58  # inner parapet face runs up into the cap
SHAFT = (11.915, 12.46, 7.405, 9.365, 9.50)                 # brick vent shaft x0, x1, y0, y1, top
HOOD = (11.887, 12.487, 7.385, 9.385, 9.645, 9.665, 9.83)   # x0, x1, y0, y1, rim bottom, rim top, ridge
# Parapet cap (RAL 5015 sheet), profile (d inward from the cassette plane, z) as a closed loop. Outer drip,
# sloped top and inner drip are from Revit; the underside is embedded in the parapet so that the facade
# top edge (8.65) and the inner parapet face (top 8.58) end inside the cap.
CAP = [(-0.0116, 8.58), (-0.0116, 8.679), (0.5716, 8.628), (0.5716, 8.508), (0.53, 8.508),
       (0.53, 8.60), (0.01, 8.60), (0.01, 8.58)]


def ref_object(prefix):
    return next(o for o in bpy.data.objects if o.name.startswith(prefix) and o.type == "MESH")


def roof_surface():
    """Top membrane surface from the Revit roof, clipped to the inner parapet faces, shaft cut out."""
    src = ref_object("Базовая крыша Покрытие_ТН-КРО")
    bm = bmesh.new()
    bm.from_mesh(src.data)
    bm.transform(src.matrix_world)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < 0.9], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    d = 0.33 + PARAPET_IN
    xi0, xi1, yi0, yi1 = X0 + d, X1 - d, Y0 + d, Y1 - d
    for co, no in (((xi0, 0, 0), (-1, 0, 0)), ((xi1, 0, 0), (1, 0, 0)), ((0, yi0, 0), (0, -1, 0)), ((0, yi1, 0), (0, 1, 0))):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=co, plane_no=no, clear_outer=True)
    x0, x1, y0, y1, _ = SHAFT
    inner = [f for f in bm.faces if x0 < f.calc_center_median().x < x1 and y0 < f.calc_center_median().y < y1]
    bmesh.ops.delete(bm, geom=inner, context="FACES")
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.join_triangles(bm, faces=bm.faces, angle_face_threshold=3.1416, angle_shape_threshold=3.1416)
    split_concave(bm)
    return bm, (xi0, xi1, yi0, yi1)


def split_concave(bm):
    """Quads that are concave/twisted fold when triangulated (flipped triangle, mirrored UV): split
    them back into triangles; stage 5 turns every triangle into three convex quads (seal.quadify)."""
    bm.normal_update()
    bad = []
    for f in bm.faces:
        if len(f.verts) != 4:
            continue
        v = [l.vert.co for l in f.loops]
        if min((v[(i + 1) % 4] - v[i]).cross(v[(i + 2) % 4] - v[(i + 1) % 4]).dot(f.normal) for i in range(4)) <= 1e-9:
            bad.append(f)
    if bad:
        bmesh.ops.triangulate(bm, faces=bad, quad_method="BEAUTY")
    return len(bad)


def roof(mb):
    mb.piece()
    bm, (xi0, xi1, yi0, yi1) = roof_surface()
    for f in bm.faces:
        mb.quad([v.co.copy() for v in f.verts], UP, "Membrane_Logicroof")
    on = lambda v, axis, val: abs(v.co[axis] - val) < 1e-4 and v.is_boundary

    def side_walls(axis, val, n, ztop, finish):
        vs = sorted((v.co.copy() for v in bm.verts if on(v, axis, val)), key=lambda c: c[1 - axis])
        for a, b in zip(vs, vs[1:]):
            mb.quad([a, b, Vector((b.x, b.y, ztop)), Vector((a.x, a.y, ztop))], n, finish)
        return len(vs)

    # inner parapet faces, welded to the roof boundary (membrane upturn)
    for axis, val, n in ((0, xi0, Vector((1, 0, 0))), (0, xi1, Vector((-1, 0, 0))),
                         (1, yi0, Vector((0, 1, 0))), (1, yi1, Vector((0, -1, 0)))):
        side_walls(axis, val, n, PARAPET_TOP_IN, "Membrane_Logicroof")
    # vent shaft walls from the roof hole to the shaft top; dark top = duct opening under the hood
    x0, x1, y0, y1, zt = SHAFT
    for axis, val, n in ((0, x0, Vector((-1, 0, 0))), (0, x1, Vector((1, 0, 0))),
                         (1, y0, Vector((0, -1, 0))), (1, y1, Vector((0, 1, 0)))):
        assert side_walls(axis, val, n, zt, "Membrane_Logicroof") == 2, "shaft side must be one quad"
    mb.quad([Vector((x0, y0, zt)), Vector((x1, y0, zt)), Vector((x1, y1, zt)), Vector((x0, y1, zt))], UP, "Interior")
    bm.free()
    parapet_cap(mb)
    hood(mb)
    roof_items(mb)
    walkways(mb)


def parapet_cap(mb):
    """Sweep the CAP profile around the facade rectangle; corners are mitred by construction."""
    mb.piece()
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(CAP, CAP[1:] + CAP[:1]))
    order = ((0, -1), (1, 0), (0, 1), (-1, 0))  # S, E, N, W outward directions for corners k -> k+1
    for (da, za), (db, zb) in zip(CAP, CAP[1:] + CAP[:1]):
        # profile edge normal pointing out of the (d, z) loop; d grows inward
        nd, nz = ((zb - za), -(db - da)) if area > 0 else (-(zb - za), (db - da))
        ring = lambda d, z: [Vector((X0 + d, Y0 + d, z)), Vector((X1 - d, Y0 + d, z)),
                             Vector((X1 - d, Y1 - d, z)), Vector((X0 + d, Y1 - d, z))]
        a, b = ring(da, za), ring(db, zb)
        for k, (ox, oy) in enumerate(order):
            k2 = (k + 1) % 4
            n = Vector((ox, oy, 0)) * -nd + UP * nz
            mb.quad([a[k], a[k2], b[k2], b[k]], n, "Metal_RAL5015")


def box(mb, x0, x1, y0, y1, z0, z1, finish):
    mb.piece()
    p = lambda x, y, z: Vector((x, y, z))
    mb.quad([p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1)], UP, finish)
    for a, b, n in (((x0, y0), (x1, y0), (0, -1, 0)), ((x1, y0), (x1, y1), (1, 0, 0)),
                    ((x1, y1), (x0, y1), (0, 1, 0)), ((x0, y1), (x0, y0), (-1, 0, 0))):
        mb.quad([p(*a, z0), p(*b, z0), p(*b, z1), p(*a, z1)], Vector(n), finish)


def hood(mb):
    """Exhaust hood over the shaft (RAL 5015): gable canopy on four 40 mm posts, open vent gap below."""
    x0, x1, y0, y1, zb, zr, zp = HOOD
    xm = (x0 + x1) / 2
    mb.piece()
    p = lambda x, y, z: Vector((x, y, z))
    mb.quad([p(x0, y0, zb), p(x1, y0, zb), p(x1, y1, zb), p(x0, y1, zb)], -UP, "Metal_RAL5015")
    for a, b, n in (((x0, y0), (x1, y0), (0, -1, 0)), ((x1, y0), (x1, y1), (1, 0, 0)),
                    ((x1, y1), (x0, y1), (0, 1, 0)), ((x0, y1), (x0, y0), (-1, 0, 0))):
        mb.quad([p(*a, zb), p(*b, zb), p(*b, zr), p(*a, zr)], Vector(n), "Metal_RAL5015")
    mb.quad([p(x0, y0, zr), p(xm, y0, zp), p(xm, y1, zp), p(x0, y1, zr)], Vector((-0.5, 0, 1)), "Metal_RAL5015")
    mb.quad([p(xm, y0, zp), p(x1, y0, zr), p(x1, y1, zr), p(xm, y1, zp)], Vector((0.5, 0, 1)), "Metal_RAL5015")
    mb.quad([p(x0, y0, zr), p(x1, y0, zr), p(xm, y0, zp)], Vector((0, -1, 0)), "Metal_RAL5015")  # gable ends
    mb.quad([p(x1, y1, zr), p(x0, y1, zr), p(xm, y1, zp)], Vector((0, 1, 0)), "Metal_RAL5015")
    sx0, sx1, sy0, sy1, st = SHAFT
    for cx, cy in ((sx0 + 0.04, sy0 + 0.04), (sx1 - 0.04, sy0 + 0.04), (sx1 - 0.04, sy1 - 0.04), (sx0 + 0.04, sy1 - 0.04)):
        box(mb, cx - 0.02, cx + 0.02, cy - 0.02, cy + 0.02, st - 0.01, zb + 0.01, "Metal_RAL5015")


def cylinder(mb, cx, cy, z0, z1, r0, r1, finish, top=True, sides=8):
    """Low-poly frustum: side quads; octagonal top as 3 quads."""
    import math
    ring = lambda z, r: [Vector((cx + r * math.cos(2 * math.pi * k / sides), cy + r * math.sin(2 * math.pi * k / sides), z))
                         for k in range(sides)]
    a, b = ring(z0, r0), ring(z1, r1)
    mb.piece()
    for k in range(sides):
        k2 = (k + 1) % sides
        mid = (a[k] + a[k2] + b[k] + b[k2]) / 4
        mb.quad([a[k], a[k2], b[k2], b[k]], Vector((mid.x - cx, mid.y - cy, 0)), finish)
    if top:
        for q in ((0, 1, 2, 3), (3, 4, 5, 6), (6, 7, 0, 3)):
            mb.quad([b[i] for i in q], UP, finish)


def walkways(mb):
    """Roof walkways: Revit 'ПВХ Logicroof Walkway Puzzle 0.6 x 0.6' tiles (25 mm), merged into strips
    along their chaining direction (the 0.76 bbox side holds the puzzle teeth), draped on the membrane:
    top = membrane + 25 mm, sides embedded 10 mm below the membrane, cut every tile (0.6 m)."""
    bm, _ = roof_surface()
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    zm = lambda x, y: bvh.ray_cast(Vector((x, y, 20.0)), Vector((0, 0, -1)))[0].z
    rows, cols = {}, {}
    tiles = refs("TN_ПВХ Logicroof")
    assert len(tiles) == 136, len(tiles)
    for o in tiles:
        b = bbox_of(o)
        cx, cy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
        if b[1] - b[0] < b[3] - b[2]:   # 0.6 x 0.76: chains along x
            rows.setdefault(round(cy, 2), []).append(cx)
        else:
            cols.setdefault(round(cx, 2), []).append(cy)
    strips = []
    for key, cs, along in [(k, v, "x") for k, v in rows.items()] + [(k, v, "y") for k, v in cols.items()]:
        cs = sorted(cs)
        run = [cs[0]]
        for c in cs[1:]:
            if c - run[-1] < 0.65:
                run.append(c)
            else:
                strips.append((key, run, along)); run = [c]
        strips.append((key, run, along))
    for key, run, along in strips:
        ts = [run[0] - 0.3] + [c + 0.3 for c in run]          # tile boundaries along the strip
        P = (lambda t, s: Vector((t, key + s, 0))) if along == "x" else (lambda t, s: Vector((key + s, t, 0)))
        mb.piece()
        top = lambda t, s: (lambda p: Vector((p.x, p.y, zm(p.x, p.y) + 0.025)))(P(t, s))
        bot = lambda t, s: (lambda p: Vector((p.x, p.y, zm(p.x, p.y) - 0.01)))(P(t, s))
        side = Vector((0, 1, 0)) if along == "x" else Vector((1, 0, 0))
        dirv = Vector((1, 0, 0)) if along == "x" else Vector((0, 1, 0))
        for a, b in zip(ts, ts[1:]):
            mb.quad([top(a, -0.3), top(b, -0.3), top(b, 0.3), top(a, 0.3)], UP, "Walkway_Logicroof")
            mb.quad([bot(a, -0.3), bot(b, -0.3), top(b, -0.3), top(a, -0.3)], -side, "Walkway_Logicroof")
            mb.quad([bot(a, 0.3), bot(b, 0.3), top(b, 0.3), top(a, 0.3)], side, "Walkway_Logicroof")
        for t, n in ((ts[0], -dirv), (ts[-1], dirv)):
            mb.quad([bot(t, -0.3), bot(t, 0.3), top(t, 0.3), top(t, -0.3)], n, "Walkway_Logicroof")


def roof_items(mb):
    """Aerators (pipe 110 mm + hat 390 mm) and roof funnel grates; sizes from the Revit bounding boxes."""
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            continue
        ws = [o.matrix_world @ Vector(c) for c in o.bound_box]
        lo = Vector([min(w[i] for w in ws) for i in range(3)])
        hi = Vector([max(w[i] for w in ws) for i in range(3)])
        cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
        if o.name.startswith("TN_Аэратор"):
            # Revit profile: flange cone r 0.065 -> 0.195 (+0.06), pipe r 0.05, hat r 0.09 (top 0.155..0.035 below hi)
            cylinder(mb, cx, cy, lo.z - 0.01, lo.z + 0.064, 0.195, 0.195, "Plastic_Black")
            cylinder(mb, cx, cy, lo.z + 0.054, hi.z - 0.145, 0.05, 0.05, "Plastic_Black", top=False)
            cylinder(mb, cx, cy, hi.z - 0.155, hi.z - 0.005, 0.09, 0.09, "Plastic_Black")
        elif o.name.startswith("TN_Воронка с обжимным"):
            cylinder(mb, cx, cy, 7.835, hi.z, 0.19, 0.10, "Plastic_Black")


# ---------------------------------------------------------------- stage 4: decor and perimeter
FOOT = (X0, X1, Y0, Y1)  # cassette outline = building mass for the plan column builder
EMBED = 0.011            # parts against the facade run 11 mm into the wall (>= 10 mm embed rule)
INSET = 0.006            # flush faces of an embedded part step back 6 mm (> 5 mm overlap tolerance)
Z_PORCH_BASE = -0.60     # porch/step sides run below the blind-area surface (embedded)
SMALL_CANOPY = (2.70, 3.30, 2.70, 2.94, 0.21)   # z0, z1, inner soffit, inner top, rim (Revit Kozyrek walls/slabs)
PORTAL_CANOPY = (2.70, 3.30, 2.82, 3.08, 0.22)  # 220 frame, slab Karkas160 2.82..3.08


def in_foot(x, y):
    return FOOT[0] < x < FOOT[1] and FOOT[2] < y < FOOT[3]


def columns(mb, rects, cell):
    """Plan height-field: grid from rect bounds; cell(xc, yc) -> list of solid z intervals
    (z0, z1, top_finish, side_finish, bottom_finish), touching intervals merge. Cells inside the
    building mass are solid with no faces, so nothing is generated against the facade."""
    mb.piece()
    # Embed: the building mass starts EMBED inside the facade plane, so faces built against it end
    # inside the wall instead of on the facade (no shared vertices, no 3-face edges, no overlaps).
    fx0, fx1, fy0, fy1 = FOOT[0] + EMBED, FOOT[1] - EMBED, FOOT[2] + EMBED, FOOT[3] - EMBED
    in_mass = lambda x, y: fx0 < x < fx1 and fy0 < y < fy1

    def axis(vals, f0, f1, g0, g1):
        vs = cuts(vals + [v for v in (f0, f1) if min(vals) < v < max(vals)])
        return [v for v in vs if not (g0 - 1e-6 <= v < f0 - 1e-6 or f1 + 1e-6 < v <= g1 + 1e-6)]
    xs = axis([v for r in rects for v in r[:2]], fx0, fx1, FOOT[0], FOOT[1])
    ys = axis([v for r in rects for v in r[2:4]], fy0, fy1, FOOT[2], FOOT[3])
    nx, ny = len(xs) - 1, len(ys) - 1
    MASS = [(-INF, INF, None, None, None)]

    def get(i, j):
        if not (0 <= i < nx and 0 <= j < ny):
            xc = xs[0] - 1e-3 if i < 0 else xs[-1] + 1e-3 if i >= nx else (xs[i] + xs[i + 1]) / 2
            yc = ys[0] - 1e-3 if j < 0 else ys[-1] + 1e-3 if j >= ny else (ys[j] + ys[j + 1]) / 2
            return MASS if in_mass(xc, yc) else []
        xc, yc = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
        return MASS if in_mass(xc, yc) else sorted(cell(xc, yc))

    grid = {(i, j): get(i, j) for i in range(-1, nx + 1) for j in range(-1, ny + 1)}
    p = lambda x, y, z: Vector((x, y, z))
    for i in range(nx):
        for j in range(ny):
            iv = grid[(i, j)]
            x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
            for k, (z0, z1, ft, fs, fb) in enumerate(iv):
                if ft and not (k + 1 < len(iv) and abs(iv[k + 1][0] - z1) < 1e-6):
                    mb.quad([p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1)], UP, ft)
                if fb and not (k > 0 and abs(iv[k - 1][1] - z0) < 1e-6):
                    mb.quad([p(x0, y0, z0), p(x1, y0, z0), p(x1, y1, z0), p(x0, y1, z0)], -UP, fb)

    def solid(iv, z):
        return next((t for t in iv if t[0] <= z < t[1]), None)

    def walls(a, b, quad_at, n_ab):
        bp = cuts([z for iv in (a, b) for t in iv for z in t[:2] if abs(z) < INF])
        for z0, z1 in zip(bp, bp[1:]):
            sa, sb = solid(a, (z0 + z1) / 2), solid(b, (z0 + z1) / 2)
            if bool(sa) == bool(sb):
                continue
            owner, n = (sa, n_ab) if sa else (sb, -n_ab)
            if owner[3]:
                mb.quad(quad_at(z0, z1), n, owner[3])

    for i in range(-1, nx):
        x = xs[i + 1]
        for j in range(ny):
            y0, y1 = ys[j], ys[j + 1]
            walls(grid[(i, j)], grid[(i + 1, j)], lambda z0, z1: [p(x, y0, z0), p(x, y1, z0), p(x, y1, z1), p(x, y0, z1)],
                  Vector((1, 0, 0)))
    for j in range(-1, ny):
        y = ys[j + 1]
        for i in range(nx):
            x0, x1 = xs[i], xs[i + 1]
            walls(grid[(i, j)], grid[(i, j + 1)], lambda z0, z1: [p(x0, y, z0), p(x1, y, z0), p(x1, y, z1), p(x0, y, z1)],
                  Vector((0, 1, 0)))


def bbox_of(o):
    ws = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return [round(min(w[0] for w in ws), 3), round(max(w[0] for w in ws), 3), round(min(w[1] for w in ws), 3),
            round(max(w[1] for w in ws), 3), round(min(w[2] for w in ws), 3), round(max(w[2] for w in ws), 3)]


def refs(prefix, collection=None):
    out = []
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith(prefix):
            if collection and not any(c.name == collection for c in o.users_collection):
                continue
            out.append(o)
    return out


def clusters(rects, gap=0.05):
    """Group plan rects that touch or overlap (union-find)."""
    parent = list(range(len(rects)))
    find = lambda i: i if parent[i] == i else find(parent[i])
    for a in range(len(rects)):
        for b in range(a + 1, len(rects)):
            ra, rb = rects[a], rects[b]
            if ra[0] <= rb[1] + gap and rb[0] <= ra[1] + gap and ra[2] <= rb[3] + gap and rb[2] <= ra[3] + gap:
                parent[find(a)] = find(b)
    groups = {}
    for i in range(len(rects)):
        groups.setdefault(find(i), []).append(rects[i])
    return list(groups.values())


def canopy_rects():
    """Canopy outlines from the Revit Kozyrek walls (rim boxes) and portal frames, extended to the facade."""
    rims = [bbox_of(o) for o in refs("Базовая стена ADSK_Стена (Козыре") if bbox_of(o)[5] - bbox_of(o)[4] > 0.5]
    frames = [bbox_of(o) for o in refs("Базовая стена ADSK_Вент фасад_220")]
    out = []
    for kind, parts in (("small", rims), ("portal", frames)):
        for g in clusters([r[:4] for r in parts]):
            x0, x1 = min(r[0] for r in g), max(r[1] for r in g)
            y0, y1 = min(r[2] for r in g), max(r[3] for r in g)
            out.append((kind, [x0, x1, y0, y1]))  # rims already run into the facade (y -0.1 / -0.22)
    return out


def canopy_cell(rect, spec):
    z0, z1, zs, zt, t = spec
    x0, x1, y0, y1 = rect
    # which sides are free (not against the facade): rim runs along free sides only
    free = {"x0": not in_foot(x0 - 0.01, (y0 + y1) / 2), "x1": not in_foot(x1 + 0.01, (y0 + y1) / 2),
            "y0": not in_foot((x0 + x1) / 2, y0 - 0.01), "y1": not in_foot((x0 + x1) / 2, y1 + 0.01)}

    def cell(xc, yc):
        if not (x0 < xc < x1 and y0 < yc < y1):
            return []
        rim = ((free["x0"] and xc < x0 + t) or (free["x1"] and xc > x1 - t) or
               (free["y0"] and yc < y0 + t) or (free["y1"] and yc > y1 - t))
        if rim:
            return [(z0, z1, "Cassette_RAL5015", "Cassette_RAL5015", "Slat_RAL5015")]
        return [(zs, zt, "Membrane_Solo", "Cassette_RAL5015", "Slat_RAL5015")]
    return cell, [x0 + t, x1 - t], [y0 + t, y1 - t]


def perimeter(mb):
    # --- canopies (6 small over doors, 3 entrance portals) with portal piers
    piers = [bbox_of(o) for o in refs("Базовая стена ADSK_Вент фасад_150")]
    pier_boxes = []
    for g in clusters([r[:4] for r in piers]):
        pier_boxes.append([min(r[0] for r in g), max(r[1] for r in g), min(r[2] for r in g), max(r[3] for r in g)])
    porches = porch_rects()

    def inset_pier(pb):
        """Pier sides flush with a porch side step back INSET (the pier stands 10 mm deep in the porch)."""
        x0, x1, y0, y1 = pb
        for r in porches:
            if r[2] - 1e-3 <= y0 and y1 <= r[3] + 1e-3:
                if abs(x0 - r[0]) < 1e-3: x0 += INSET
                if abs(x1 - r[1]) < 1e-3: x1 -= INSET
            if r[0] - 1e-3 <= x0 and x1 <= r[1] + 1e-3:
                if abs(y0 - r[2]) < 1e-3: y0 += INSET
                if abs(y1 - r[3]) < 1e-3: y1 -= INSET
        return [x0, x1, y0, y1]
    pier_boxes = [inset_pier(pb) for pb in pier_boxes]
    for kind, r in canopy_rects():
        spec = PORTAL_CANOPY if kind == "portal" else SMALL_CANOPY
        cell, xi, yi = canopy_cell(r, spec)
        mine = [pb for pb in pier_boxes if r[0] - 0.01 <= pb[0] and pb[1] <= r[1] + 0.01 and r[2] - 0.01 <= pb[2] and pb[3] <= r[3] + 0.01]
        def full(xc, yc, cell=cell, mine=mine, z0=spec[0]):
            iv = list(cell(xc, yc))
            if any(pb[0] < xc < pb[1] and pb[2] < yc < pb[3] for pb in mine):
                iv.append((-0.04, z0, None, "Cassette_RAL5015", None))   # 10 mm into the porch (top -0.03)
            return iv
        rects = [r, [xi[0], xi[1], yi[0], yi[1]]] + mine
        columns(mb, [q[:4] for q in rects], full)
    # --- canopy drain spouts (TN outlet elbows), ~100x135x150 mm
    for o in refs("TN_Отвод угловой"):
        b = bbox_of(o)
        closed_box(mb, b[0], b[1], b[2], b[3], b[4], b[5], "Plastic_Black")
    porches_and_blind_area(mb)
    stair_east(mb)
    alpha_planes(mb)


def porch_rects():
    out = []
    for o in refs("Перекрытие ADSK_Перекрытие_Кр"):
        b = bbox_of(o)
        out.append([b[0], b[1], b[2], b[3], b[5]])
    return out


def porches_and_blind_area(mb):
    """Porches and steps as plan columns (tile tops); blind area from the Revit surface (asphalt)."""
    pr = []
    assert len(refs("Перекрытие ADSK_Перекрытие_Кр")) == 11, [o.name for o in refs("Перекрытие ADSK_Перекрытие_Кр")]
    for o in refs("Перекрытие ADSK_Перекрытие_Кр"):
        b = bbox_of(o)
        pr.append([b[0], b[1], b[2], b[3], b[5]])
    for g in clusters([r[:4] for r in pr], gap=0.001):
        members = [r for r in pr if any(r[:4] == q for q in g)]
        def cell(xc, yc, members=members):
            tops = [r[4] for r in members if r[0] < xc < r[1] and r[2] < yc < r[3]]
            return [(Z_PORCH_BASE, max(tops), "Plinth_RAL7004", "Plinth_RAL7004", None)] if tops else []
        columns(mb, [r[:4] for r in members], cell)
    # blind area: up-facing faces of the Revit surface outside the facade, not under porches
    src = max(refs("Перекрытие МЕР_Перекрытие_Отм"), key=lambda o: len(o.data.polygons))
    bm = bmesh.new()
    bm.from_mesh(src.data)
    bm.transform(src.matrix_world)
    under = lambda c: any(r[0] < c.x < r[1] and r[2] < c.y < r[3] for r in pr) or in_foot(c.x, c.y)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < 0.2 or under(f.calc_center_median())], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    # Revit's triangulated patches are resampled on a regular quad grid (<= 2.5 m, under the asphalt
    # texel limit) with cuts at the facade and porch outlines; heights come from the Revit surface.
    bvh = BVHTree.FromBMesh(bm)
    bx = (min(v.co.x for v in bm.verts), max(v.co.x for v in bm.verts))
    by = (min(v.co.y for v in bm.verts), max(v.co.y for v in bm.verts))
    bm.free()

    def axis_cuts(lo, hi, extra, step=2.5):
        base = cuts([lo, hi] + [v for v in extra if lo < v < hi])
        out = []
        for a, b in zip(base, base[1:]):
            n = max(1, -int(-(b - a) // step))
            out += [a + (b - a) * k / n for k in range(n)]
        return cuts(out + [hi])

    xs = axis_cuts(bx[0], bx[1], [X0, X1] + [v for r in pr for v in r[:2]])
    ys = axis_cuts(by[0], by[1], [Y0, Y1] + [v for r in pr for v in r[2:4]])

    def zat(x, y):
        hit = bvh.ray_cast(Vector((x, y, 50.0)), Vector((0, 0, -1)))
        if hit[0] is None:
            hit = bvh.find_nearest(Vector((x, y, -0.2)))
        return round(hit[0].z, 4)

    keep = lambda xc, yc: not in_foot(xc, yc) and not any(r[0] < xc < r[1] and r[2] < yc < r[3] for r in pr)
    mb.piece()
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
            if not keep((x0 + x1) / 2, (y0 + y1) / 2):
                continue
            mb.quad([Vector((x, y, zat(x, y))) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))], UP, "Asphalt")
            # outer outline goes down >= 1 m below grade (VPM reg p.28 §3.6)
            for (xa, ya), (xb, yb), n, edge in (((x0, y0), (x1, y0), (0, -1, 0), j == 0), ((x1, y0), (x1, y1), (1, 0, 0), i == len(xs) - 2),
                                                ((x1, y1), (x0, y1), (0, 1, 0), j == len(ys) - 2), ((x0, y1), (x0, y0), (-1, 0, 0), i == 0)):
                if edge:
                    a, b = Vector((xa, ya, zat(xa, ya))), Vector((xb, yb, zat(xb, yb)))
                    mb.quad([a, b, Vector((b.x, b.y, Z_BOTTOM)), Vector((a.x, a.y, Z_BOTTOM))], Vector(n), "Asphalt")


def closed_box(mb, x0, x1, y0, y1, z0, z1, finish):
    """Closed six-sided box (seen from below too)."""
    box(mb, x0, x1, y0, y1, z0, z1, finish)
    p = lambda x, y: Vector((x, y, z0))
    mb.quad([p(x0, y0), p(x0, y1), p(x1, y1), p(x1, y0)], -UP, finish)


def prism(mb, quads, frame, w, finish, skip_caps=(), skip_sides=()):
    """Closed prism from planar 2D quads [(u, z) x4] extruded across t = 0..w.
    frame(u, z, t) -> world point. Quads share edges; only outline edges get side faces.
    skip_caps: {(quad_index, 0 | 1)} caps left open; skip_sides: outline edges ((u, z), (u, z)) left open
    (faces removed where another solid is stitched on)."""
    mb.piece()
    used = {}
    for q in quads:
        for a, b in zip(q, q[1:] + q[:1]):
            k = tuple(sorted((a, b)))
            used[k] = used.get(k, 0) + 1
    n_t = (frame(0, 0, 1) - frame(0, 0, 0)).normalized()
    for qi, q in enumerate(quads):
        if (qi, 0) not in skip_caps:
            mb.quad([frame(u, z, 0) for u, z in q], -n_t, finish)
        if (qi, 1) not in skip_caps:
            mb.quad([frame(u, z, w) for u, z in q], n_t, finish)
        c = sum((Vector((u, z)) for u, z in q), Vector((0.0, 0.0))) / 4
        for a, b in zip(q, q[1:] + q[:1]):
            if used[tuple(sorted((a, b)))] != 1 or tuple(sorted((a, b))) in skip_sides:
                continue
            m = (Vector(a) + Vector(b)) / 2
            out = frame(m.x, m.y, w / 2) - frame(c.x, c.y, w / 2)
            mb.quad([frame(*a, 0), frame(*b, 0), frame(*b, w), frame(*a, w)], out, finish)


def stair_band(mb, profile, plane, w, finish="Metal_RAL5015", skip_caps=(), skip_sides=()):
    """Closed prism of a stair band: profile = convex quads [(u, z) x4] sharing edges (frame + stringer
    stitched in one plane), extruded across w. plane = ('x', y0): u runs along x at y0..y0+w;
    ('y', x0): u runs along y at x0..x0+w."""
    axis, c0 = plane
    frame = (lambda u, z, t: Vector((u, c0 + t, z))) if axis == "x" else (lambda u, z, t: Vector((c0 + t, u, z)))
    prism(mb, profile, frame, w, finish, {tuple(c) for c in skip_caps}, {tuple(sorted(e)) for e in skip_sides})


def slope_profile(u_top, z_top, u_end, slope=0.8, depth=0.3, z_cut=None):
    """Quads of a sloped stringer: top edge z_top at u_top falling by slope towards u_end, vertical ends,
    optional horizontal cut at z_cut (grade)."""
    sg = 1 if u_end > u_top else -1
    top = lambda u: z_top - slope * abs(u - u_top)
    u_g = None if z_cut is None else u_top + sg * (z_top - depth - z_cut) / slope
    if u_g is None or (u_g - u_end) * sg >= 0:
        return [[(u_top, z_top), (u_top, z_top - depth), (u_end, top(u_end) - depth), (u_end, top(u_end))]]
    return [[(u_top, z_top), (u_top, z_top - depth), (u_g, z_cut), (u_g, top(u_g))],
            [(u_g, top(u_g)), (u_g, z_cut), (u_end, z_cut), (u_end, top(u_end))]]


def stair_east(mb):
    """East steel stair rebuilt from Revit parameters as closed quad solids (RAL 5015, Revit material
    'Настил рифленый (RAL 5015)'; ИД facade 1-4/A-B): flight 1 = 10 treads, rise 0.2, going 0.25,
    width 1.2 (x 28.83..31.33, y 2.4..3.6) to landing +2.10; flight 2 = 8 treads (y 3.6..5.6,
    x 27.63..28.83) to landing +3.90; treads/landings 40 mm, stringers/frames 80 x 300 mm.
    Joints (no overlapping faces at 5 mm, no shared vertices, no 3-face edges):
    - a frame and the stringer in the same plane are one stitched prism;
    - perpendicular joints: the incoming band runs EMBED_S (10 mm) into the receiving one, and the
      receiving band's end steps back INSET (6 mm) so no two faces are coplanar;
    - treads run 10 mm into the stringers; landing decks sit 6 mm below the frame tops (and below the
      +3.90 door sill) and run 10 mm into the frames; parts at the facade run into the wall."""
    E, I = 0.01, INSET
    zc = -0.11  # stringers end 10 mm below grade
    for k in range(10):
        zt = 0.1 + 0.2 * k
        x1 = 31.33 - 0.25 * k - (I if k == 0 else 0.0)  # first tread steps back from the stringer ends
        closed_box(mb, 31.33 - 0.25 * (k + 1), x1, 2.4 - E, 3.6 + E, zt - 0.04, zt, "Metal_RAL5015")
    for k in range(8):
        zt = 2.3 + 0.2 * k
        closed_box(mb, 27.63 - E, 28.83 + E, 3.6 + 0.25 * k, 3.6 + 0.25 * (k + 1), zt - 0.04, zt, "Metal_RAL5015")
    # Corners of the landing frames are stitched: the incoming band has no end cap, the receiving band
    # has an extra edge and no face where they meet; the shared border welds edge to edge (one L solid).
    # south band y 2.32..2.40: landing frame + flight-1 stringer, stitched to the west band at x 27.63
    stair_band(mb, [[(27.63, 2.1), (27.63, 1.8), (28.7289, 1.8), (28.7289, 2.1)]]
               + slope_profile(28.7289, 2.1, 31.33, z_cut=zc), ("x", 2.32), 0.08,
               skip_sides=[((27.63, 2.1), (27.63, 1.8))])
    # west band x 27.55..27.63: corner square + landing frame + flight-2 stringer
    stair_band(mb, [[(2.32, 2.1), (2.32, 1.8), (2.4, 1.8), (2.4, 2.1)], [(2.4, 2.1), (2.4, 1.8), (3.3459, 1.8), (3.3459, 2.1)]]
               + slope_profile(3.3459, 2.1, 5.52, slope=-0.8), ("y", 27.55), 0.08, skip_caps=[(0, 1)])
    # east band x 28.83..28.91: flight-2 stringer (lower end stepped back) + upper landing frame + corner
    y0 = 3.6 + I
    stair_band(mb, slope_profile(5.7011, 3.9, y0) + [[(5.7011, 3.9), (5.7011, 3.6), (8.5, 3.6), (8.5, 3.9)],
                                                     [(8.5, 3.9), (8.5, 3.6), (8.58, 3.6), (8.58, 3.9)]],
               ("y", 28.83), 0.08, skip_caps=[(len(slope_profile(5.7011, 3.9, y0)) + 1, 0)])
    # flight-1 north stringer y 3.60..3.68, 10 mm into the east band
    stair_band(mb, slope_profile(28.91 - E, 2.0393 + 0.8 * E, 31.33, z_cut=zc), ("x", 3.6), 0.08)
    # upper landing frames: north one stitched to the east band at x 28.83, both run into the wall
    stair_band(mb, [[(27.33 - 0.01, 3.9), (27.33 - 0.01, 3.6), (28.83, 3.6), (28.83, 3.9)]], ("x", 8.5), 0.08,
               skip_sides=[((28.83, 3.9), (28.83, 3.6))])
    # south frame of the upper landing: steps back INSET from the west stringer's top end (no touching
    # coplanar faces: 3ds Max xView counts those as overlapping); the deck covers the joint from above
    closed_box(mb, 27.33 - 0.01, 27.55, 5.52 + I, 5.6, 3.6, 3.9, "Metal_RAL5015")
    # landing decks
    closed_box(mb, 27.63 - E, 28.83, 2.4 - E, 3.6, 2.1 - I - 0.04, 2.1 - I, "Metal_RAL5015")         # +2.10 deck
    closed_box(mb, 27.33 - 0.03, 28.83 + E, 5.6 - E, 8.5 + E, 3.9 - I - 0.04, 3.9 - I, "Metal_RAL5015")  # +3.90


def alpha_strip(mb, pts, height, finish, offset=0.008, v_mode="rail", u0=0.0):
    """Vertical alpha-cut strip along a polyline [(x, y, z_base)], two-sided by a flipped copy offset
    5 mm along the normal (VPM reg p.36 §12.3). UVs in metres: u = run length along the polyline + u0;
    v = 0.05 + height above the base line (v_mode 'rail': sheared, bars follow the stair slope) or
    world z (v_mode 'world': rungs/hoops at fixed heights)."""
    P = [Vector(p) for p in pts]
    segn = []
    for a, b in zip(P, P[1:]):
        d = b - a
        d.z = 0
        segn.append(Vector((-d.y, d.x, 0)).normalized())
    def miter(k):
        """Offset direction at polyline point k: bisector scaled so both copies stay closed at corners."""
        ns = [segn[i] for i in (k - 1, k) if 0 <= i < len(segn)]
        m = sum(ns, Vector()).normalized()
        return m / max(m.dot(ns[0]), 0.2)
    for side in (1, -1):
        mb.piece()
        run = u0
        for k, (a, b) in enumerate(zip(P, P[1:])):
            d = (b - a)
            d.z = 0
            n = segn[k] * side
            oa, ob = miter(k) * side * offset * 0.5, miter(k + 1) * side * offset * 0.5
            ua, ub = run, run + d.length
            run = ub
            if v_mode == "rail":
                uv = [Vector((ua, 0.05)), Vector((ub, 0.05)), Vector((ub, 0.05 + height)), Vector((ua, 0.05 + height))]
            else:
                uv = [Vector((ua, a.z)), Vector((ub, b.z)), Vector((ub, b.z + height)), Vector((ua, a.z + height))]
            mb.quad([a + oa, b + ob, b + ob + UP * height, a + oa + UP * height], n, finish, uv)


def alpha_planes(mb):
    """Railings of the east stair and the roof ladder P1-2 with its cage: details < 5 cm -> alpha planes."""
    fz = lambda x: 0.1593 + (31.24 - x) * 0.8          # lower flight (posts fit, slope 0.8)
    fy = lambda y: 2.319 + (y - 3.6) * 0.8             # upper flight
    south = [(31.33, 2.36, fz(31.33)), (28.83, 2.36, 2.1), (27.59, 2.36, 2.1), (27.59, 3.6, 2.1),
             (27.59, 3.6, fy(3.6)), (27.59, 5.6, fy(5.6))]
    north = [(31.33, 3.64, fz(31.33)), (28.87, 3.64, fz(28.87)), (28.87, 5.6, 3.9),
             (28.87, 8.54, 3.9), (27.33, 8.54, 3.9)]
    for line in (south, north):
        clean = [q for k, q in enumerate(line) if k == 0 or (Vector(q[:2]) - Vector(line[k - 1][:2])).length > 1e-6]
        alpha_strip(mb, clean, 1.2, "Railing_Alpha")
    # roof ladder: vertical rung plane, top walkway over the parapet, side handrails, cage (U of 3 planes)
    y0, y1 = 7.3414, 8.1414
    alpha_strip(mb, [(27.53, y0, 3.9), (27.53, y1, 3.9)], 5.015, "Ladder_Alpha_RAL1021", v_mode="world", u0=0.04)
    for nz in (1, -1):  # walkway over the parapet: same rung pattern, u across the ladder, v along x
        mb.piece()
        z = 8.915 + (0.004 if nz > 0 else -0.004)
        pts = [Vector((26.63, y0, z)), Vector((27.53, y0, z)), Vector((27.53, y1, z)), Vector((26.63, y1, z))]
        mb.quad(pts, UP * nz, "Ladder_Alpha_RAL1021", [Vector((0.04 + p.y - y0, p.x)) for p in pts])
    for y in (7.39, 8.14):
        alpha_strip(mb, [(26.605, y, 8.915), (27.555, y, 8.915)], 1.01, "Cage_Alpha_RAL1021", v_mode="world")
    alpha_strip(mb, [(27.53, 7.311, 6.375), (28.455, 7.311, 6.375), (28.455, 8.171, 6.375), (27.53, 8.171, 6.375)],
                2.55, "Cage_Alpha_RAL1021", v_mode="world")


# ---------------------------------------------------------------- stage 6: collision
def collisions(report):
    """UCX_SM_<Address>_Main_NNN convex hulls from vpm_ucx; checks closed/convex/no overlap/budget."""
    canopies = [(r, 2.70, 3.30) for kind, r in canopy_rects()]
    piers = []
    for g in clusters([bbox_of(o)[:4] for o in refs("Базовая стена ADSK_Вент фасад_150")]):
        piers.append([min(r[0] for r in g), max(r[1] for r in g), min(r[2] for r in g), max(r[3] for r in g)])
    pr = [bbox_of(o) for o in refs("Перекрытие ADSK_Перекрытие_Кр")]
    porches = []
    for g in clusters([b[:4] for b in pr], gap=0.001):
        tops = [b[5] for b in pr if b[:4] in g]
        porches.append(([min(r[0] for r in g), max(r[1] for r in g), min(r[2] for r in g), max(r[3] for r in g)], max(tops)))
    d = 0.33 + PARAPET_IN
    parts = vpm_ucx.pieces(FOOT, 7.962, d, 8.68, SHAFT, HOOD, canopies, piers, porches)
    hulls = [(label, vpm_ucx.hull(pts)) for label, pts in parts]
    objs, tris = [], 0
    for k, (label, bm) in enumerate(hulls, 1):
        closed, convex = vpm_ucx.convex_closed(bm)
        tris += len(bm.faces)
        report.append({"name": f"UCX_{MAIN}_{k:03d}", "part": label, "tris": len(bm.faces),
                       "closed": closed, "convex": convex})
    overlaps = [(hulls[i][0], hulls[j][0]) for i in range(len(hulls)) for j in range(i + 1, len(hulls))
                if vpm_ucx.intersect(hulls[i][1], hulls[j][1])]
    for k, (label, bm) in enumerate(hulls, 1):
        me = bpy.data.meshes.new(f"UCX_{MAIN}_{k:03d}")
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(me.name, me)
        o.display_type = "WIRE"
        bpy.context.scene.collection.objects.link(o)
        objs.append(o)
    report.append({"total_tris": tris, "budget": 15000, "overlapping_pairs": overlaps})
    return objs


# ---------------------------------------------------------------- reference, QA, main
def import_reference(src):
    """Load source FBX groups into an excluded REF collection for side-by-side comparison."""
    ref = bpy.data.collections.new("REF_Revit_source-v001")
    bpy.context.scene.collection.children.link(ref)
    for f in sorted(os.listdir(src)):
        if not f.endswith(".fbx") or f.startswith("full_model") or f == "walls_int.fbx":
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=os.path.join(src, f))
        sub = bpy.data.collections.new("REF_" + f[:-4])
        ref.children.link(sub)
        for o in set(bpy.data.objects) - before:
            for c in o.users_collection:
                c.objects.unlink(o)
            if o.type == "CAMERA":
                bpy.data.objects.remove(o)
            else:
                sub.objects.link(o)
    bpy.context.view_layer.layer_collection.children[ref.name].exclude = True


def qa(obj):
    """Geometry QA (VPM reg p.29 §3.11, §3.15; project quad rule). Open boundaries are intentional
    (opening pieces omit back faces) and reported separately from >2-face edges."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    faces = len(bm.faces)
    keys = {}
    for f in bm.faces:
        k = (tuple(round(c, 3) for c in f.calc_center_median()), tuple(round(c, 2) for c in f.normal))
        keys[k] = keys.get(k, 0) + 1
    res = {"object": obj.name, "faces": faces, "quads": sum(len(f.verts) == 4 for f in bm.faces),
           "tris_after_triangulate": sum(len(f.verts) - 2 for f in bm.faces),
           "boundary_edges": sum(len(e.link_faces) == 1 for e in bm.edges),
           "edges_gt2_faces": sum(len(e.link_faces) > 2 for e in bm.edges),
           "loose_verts": sum(not v.link_edges for v in bm.verts),
           "edges_lt_2mm": sum(e.calc_length() < 0.002 for e in bm.edges),
           "duplicate_verts_2mm": len(bmesh.ops.find_doubles(bm, verts=bm.verts, dist=0.002)["targetmap"]),
           "duplicate_faces": sum(n - 1 for n in keys.values() if n > 1),
           "shells": 0}
    seen = set()
    for f in bm.faces:
        if f.index in seen:
            continue
        res["shells"] += 1
        stack = [f]
        while stack:
            g = stack.pop()
            if g.index in seen:
                continue
            seen.add(g.index)
            stack += [h for e in g.edges for h in e.link_faces if h.index not in seen]
    bm.free()
    pts = [v.co for v in me.vertices]
    res["bounds_min"] = [round(min(p[i] for p in pts), 3) for i in range(3)]
    res["bounds_max"] = [round(max(p[i] for p in pts), 3) for i in range(3)]
    res["finish_faces"] = {m.name: sum(p.material_index == i for p in me.polygons) for i, m in enumerate(me.materials)}
    return res


STAGES = {1: "body", 2: "openings", 3: "roof", 4: "decor", 5: "uv", 6: "ucx"}


def main():
    src, census, out, stage = sys.argv[sys.argv.index("--") + 1:][:4]
    stage = int(stage)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system, sc.unit_settings.scale_length = "METRIC", 1.0
    import_reference(src)
    spec = load_spec(census) if stage >= 2 else None
    mb, gb = MeshBuilder(), MeshBuilder()
    body(mb, spec, closed=stage < 3, decor=stage >= 4)
    if stage >= 2:
        openings(mb, gb, spec, decor=stage >= 4)
    if stage >= 3:
        roof(mb)
    if stage >= 4:
        perimeter(mb)
    uvqa = {}
    if stage >= 5:
        here = os.path.dirname(os.path.abspath(__file__))
        tspec = vpm_uv.load_spec(os.path.join(here, "vpm_textures.json"))
        tex_dir = os.path.join(out, "..", "textures-v001")

        def main_uv(bm, names):
            uvqa["seal_main"] = []
            bm = seal.quadify(bm, uvqa["seal_main"])
            bm = vpm_uv.texel_cut(bm, names, tspec)
            bm = seal.seal(bm, log=uvqa["seal_main"])
            uvqa["main"] = vpm_uv.pack_uv(bm, names, tspec)
            uvqa["density_px_per_m"] = vpm_uv.density_qa(bm, names, tspec)
            uvqa["finish_ids"] = {i: n for i, n in enumerate(names)}
            return bm

        def glass_uv(bm, names):
            uvqa["seal_glass"] = []
            bm = seal.seal(bm, log=uvqa["seal_glass"])
            uvqa["glass"] = vpm_uv.pack_uv(bm, names, tspec, glass=True)
            return bm
        built = [mb.to_object(MAIN, main_uv, vpm_uv.main_material(bpy, tspec, tex_dir)),
                 gb.to_object(GLASS, glass_uv, vpm_uv.glass_material(bpy, tspec))]
    else:
        built = [mb.to_object(MAIN)]
        if gb.finish:
            built.append(gb.to_object(GLASS))
        else:
            gb.bm.free()
    ucx_report = []
    if stage >= 6:
        built += collisions(ucx_report)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"KPP1_VPM_v{stage:03d}_{STAGES[stage]}.blend")
    report = {"stage": stage, "file": path, "qa": [qa(o) for o in built if not o.name.startswith("UCX_")],
              "uv": uvqa, "ucx": ucx_report}
    json.dump(report, open(path[:-6] + ".qa.json", "w"), indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    print("QA", json.dumps(report, indent=1))


main()

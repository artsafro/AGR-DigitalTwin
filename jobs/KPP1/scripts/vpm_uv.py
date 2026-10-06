"""VPM texel cuts, UDIM UV packing and materials for the KPP1 build (stage 5).

Faces carry a `finish` int layer (index into the builder's finish names). Texture sets per finish are
in vpm_textures.json. Rules (docs/domain/uv-textures.md, geometry.md):
- texel cuts: quads are split along edge rings (n = ceil(L / Lmax), bilinear), so shared edges get
  identical splits and no T-junctions; Lmax = S - 2*pad - period, so every face fits its tile after
  a whole-period shift;
- one UV channel, one UDIM tile per finish, sequential from 1001;
- full textures: world-metre projection, shifted by whole pattern periods (phase kept, overlap of
  identical islands), density = size / S;
- placeholders (256 px, density-exempt) and glass (tile 1001, overlaps allowed): islands scaled into
  the tile with a margin;
- no mirrored islands: UV winding must follow the face winding.
"""
import json, math, os
import bmesh
from mathutils import Vector


def load_spec(path):
    return json.load(open(path, encoding="utf-8"))


LMAX_PLAIN = 3.9  # user rule 2026-10-07: quads up to 4 x 4 m on every finish (conflict #26 default 3.9 m)


def lmax(spec, f):
    t = spec["finishes"].get(f)
    if not t or t["kind"] != "full":
        return LMAX_PLAIN
    per = max([p for p, s in zip(t["P"], t["shift"]) if s] or [0.0])
    return t["S"] - 2 * spec["pad_m"] - per


# ------------------------------------------------------------------ texel cuts
def texel_cut(bm, names, spec):
    """Return a new bmesh with quads split along edge rings where textured finishes need it."""
    fl = bm.faces.layers.int["finish"]
    uvm = bm.loops.layers.uv.get("UVM")
    bm.edges.index_update()
    bm.verts.index_update()
    parent = list(range(len(bm.edges)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for f in bm.faces:
        if len(f.loops) == 4:
            e = [l.edge.index for l in f.loops]
            parent[find(e[0])] = find(e[2])
            parent[find(e[1])] = find(e[3])
    n = {}
    for f in bm.faces:
        lm = lmax(spec, names[f[fl]])
        if not lm:
            continue
        for e in f.edges:
            r = find(e.index)
            n[r] = max(n.get(r, 1), math.ceil(e.calc_length() / lm - 1e-9))
    seg = lambda e: n.get(find(e.index), 1)

    nb = bmesh.new()
    nfl = nb.faces.layers.int.new("finish")
    nflag = nb.faces.layers.int.new("uvx")
    nuvm = nb.loops.layers.uv.new("UVM")
    oflag = bm.faces.layers.int.get("uvx")
    vmap, emap = {}, {}

    def vert(key, co):
        if key not in vmap:
            vmap[key] = nb.verts.new(co)
        return vmap[key]

    def edge_point(e, start, k, ne, co):
        if k == 0:
            return vert(("v", start.index), co)
        if k == ne:
            return vert(("v", e.other_vert(start).index), co)
        kk = k if start == e.verts[0] else ne - k
        return vert(("e", e.index, kk), co)

    for f in bm.faces:
        ls = list(f.loops)
        uv0 = [l[uvm].uv.copy() if uvm else Vector((0, 0)) for l in ls]
        if len(ls) == 4:
            v = [l.vert.co for l in ls]
            na, nbb = seg(ls[0].edge), seg(ls[1].edge)
            P = lambda s, t, a=v: (1 - s) * (1 - t) * a[0] + s * (1 - t) * a[1] + s * t * a[2] + (1 - s) * t * a[3]
            U = lambda s, t, a=uv0: (1 - s) * (1 - t) * a[0] + s * (1 - t) * a[1] + s * t * a[2] + (1 - s) * t * a[3]
            grid = {}
            for i in range(na + 1):
                for j in range(nbb + 1):
                    s, t = i / na, j / nbb
                    co = P(s, t)
                    if j == 0:
                        vv = edge_point(ls[0].edge, ls[0].vert, i, na, co)
                    elif j == nbb:
                        vv = edge_point(ls[2].edge, ls[3].vert, i, na, co)
                    elif i == 0:
                        vv = edge_point(ls[3].edge, ls[0].vert, j, nbb, co)
                    elif i == na:
                        vv = edge_point(ls[1].edge, ls[1].vert, j, nbb, co)
                    else:
                        vv = nb.verts.new(co)
                    grid[(i, j)] = (vv, U(s, t))
            for i in range(na):
                for j in range(nbb):
                    cs = [grid[(i, j)], grid[(i + 1, j)], grid[(i + 1, j + 1)], grid[(i, j + 1)]]
                    nf = nb.faces.new([c[0] for c in cs])
                    for l, c in zip(nf.loops, cs):
                        l[nuvm].uv = c[1]
                    nf[nfl] = f[fl]
                    nf[nflag] = f[oflag] if oflag else 0
        else:
            pts = []
            for k, l in enumerate(ls):
                e, ne = l.edge, seg(l.edge)
                a, b = l.vert.co, l.link_loop_next.vert.co
                ua, ub = uv0[k], uv0[(k + 1) % len(ls)]
                for i in range(ne):
                    pts.append((edge_point(e, l.vert, i, ne, a.lerp(b, i / ne)), ua.lerp(ub, i / ne)))
            nf = nb.faces.new([p[0] for p in pts])
            for l, p in zip(nf.loops, pts):
                l[nuvm].uv = p[1]
            nf[nfl] = f[fl]
            nf[nflag] = f[oflag] if oflag else 0
    bm.free()
    nb.normal_update()
    return nb


# ------------------------------------------------------------------ UV packing
def project(co, n):
    """World-metre planar projection whose winding follows the face normal (no mirroring)."""
    ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
    if az >= ax and az >= ay:
        return Vector((co.x, co.y)) if n.z > 0 else Vector((co.x, -co.y))
    if ax >= ay:
        return Vector((co.y, co.z)) if n.x > 0 else Vector((-co.y, co.z))
    return Vector((-co.x, co.z)) if n.y > 0 else Vector((co.x, co.z))


def signed_area(uvs):
    return sum(a.x * b.y - b.x * a.y for a, b in zip(uvs, uvs[1:] + uvs[:1])) / 2


def tile_offset(udim):
    i = udim - 1001
    return Vector((i % 10, i // 10))


def pack_uv(bm, names, spec, glass=False):
    """Write the final UDIM layer 'UVMap'; returns per-finish QA."""
    fl = bm.faces.layers.int["finish"]
    uvm = bm.loops.layers.uv.get("UVM")
    flag = bm.faces.layers.int.get("uvx")
    out = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    pad = spec["pad_m"]
    metres = {}
    for f in bm.faces:
        if flag and f[flag] and uvm:
            uvs = [l[uvm].uv.copy() for l in f.loops]
        else:
            uvs = [project(l.vert.co, f.normal) for l in f.loops]
        if signed_area(uvs) < 0:  # explicit UVs on a flipped copy: mirror about the finish axis
            m = spec["finishes"].get(names[f[fl]], {}).get("mirror_u", 0.0) if not glass else 0.0
            uvs = [Vector((2 * m - u.x, u.y)) for u in uvs]
        metres[f] = uvs
    # placeholder / glass scale: largest island side of the finish
    ext = {}
    for f, uvs in metres.items():
        key = "glass" if glass else names[f[fl]]
        d = max(max(u.x for u in uvs) - min(u.x for u in uvs), max(u.y for u in uvs) - min(u.y for u in uvs))
        ext[key] = max(ext.get(key, 0.0), d)
    qa = {}
    for f, uvs in metres.items():
        name = "glass" if glass else names[f[fl]]
        t = spec["glass"] if glass else spec["finishes"][name]
        off = tile_offset(t["udim"])
        q = qa.setdefault(name, {"udim": t["udim"], "faces": 0, "overflow": 0, "min_margin_px": 1e9})
        q["faces"] += 1
        umin, vmin = min(u.x for u in uvs), min(u.y for u in uvs)
        if not glass and t["kind"] == "full":
            S = t["S"]
            su = math.floor((umin - pad) / t["P"][0]) * t["P"][0] if t["shift"][0] else 0.0
            sv = math.floor((vmin - pad) / t["P"][1]) * t["P"][1] if t["shift"][1] else 0.0
            local = [Vector((u.x - su, u.y - sv)) / S for u in uvs]
            size = spec["size_full"]
        else:
            S = ext[name] / (1 - 2 * 0.05) if ext[name] > 0 else 1.0  # 5 % margin each side
            local = [Vector((u.x - umin, u.y - vmin)) / S + Vector((0.05, 0.05)) for u in uvs]
            size = spec["size_placeholder"]
        lo = min(min(p.x, p.y) for p in local)
        hi = max(max(p.x, p.y) for p in local)
        q["min_margin_px"] = min(q["min_margin_px"], round(min(lo, 1 - hi) * size, 1))
        if lo < 0 or hi > 1:
            q["overflow"] += 1
        for l, p in zip(f.loops, local):
            l[out].uv = p + off
    return qa


def density_qa(bm, names, spec):
    """Texel density (px/m) of full-texture faces from UV vs world area (reg p.32 §6.2: 512..1706)."""
    fl = bm.faces.layers.int["finish"]
    out = bm.loops.layers.uv["UVMap"]
    res = {}
    for f in bm.faces:
        t = spec["finishes"].get(names[f[fl]])
        if not t or t["kind"] != "full" or f.calc_area() < 1e-4:
            continue
        a_uv = abs(signed_area([l[out].uv.copy() for l in f.loops])) * spec["size_full"] ** 2
        d = math.sqrt(a_uv / f.calc_area())
        r = res.setdefault(names[f[fl]], [1e9, 0])
        r[0], r[1] = min(r[0], round(d)), max(r[1], round(d))
    return res


# ------------------------------------------------------------------ materials
def udim_image(bpy, tex_dir, kind, address, colorspace):
    path = os.path.join(tex_dir, f"T_{address}_{kind}_1.1001.png")
    img = bpy.data.images.load(path, check_existing=True)
    img.source = "TILED"
    img.colorspace_settings.name = colorspace
    return img


def main_material(bpy, spec, tex_dir):
    """M_<Address>_Main_1 with UDIM Diffuse/ERM/Normal. ERM: R emissive, G roughness, B metallic.
    Normal maps are DirectX; green is inverted only in this preview node tree (project rule)."""
    a = spec["address"]
    m = bpy.data.materials.new(f"M_{a}_Main_1")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    dif = nt.nodes.new("ShaderNodeTexImage"); dif.image = udim_image(bpy, tex_dir, "Diffuse", a, "sRGB")
    erm = nt.nodes.new("ShaderNodeTexImage"); erm.image = udim_image(bpy, tex_dir, "ERM", a, "Non-Color")
    nrm = nt.nodes.new("ShaderNodeTexImage"); nrm.image = udim_image(bpy, tex_dir, "Normal", a, "Non-Color")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(dif.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(dif.outputs["Alpha"], bsdf.inputs["Alpha"])
    nt.links.new(erm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nsep = nt.nodes.new("ShaderNodeSeparateColor")
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
    comb = nt.nodes.new("ShaderNodeCombineColor")
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nrm.outputs["Color"], nsep.inputs["Color"])
    nt.links.new(nsep.outputs["Red"], comb.inputs["Red"])
    nt.links.new(nsep.outputs["Green"], inv.inputs[1])
    nt.links.new(inv.outputs["Value"], comb.inputs["Green"])
    nt.links.new(nsep.outputs["Blue"], comb.inputs["Blue"])
    nt.links.new(comb.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    nt.nodes.active = dif  # Workbench texture preview uses the active image node
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "DITHERED"
    return m


def glass_material(bpy, spec):
    """M_<Address>_MainGlass_1: no texture maps (reg p.32 §8); glass values go to GeoJSON later."""
    m = bpy.data.materials.new(f"M_{spec['address']}_MainGlass_1")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.85, 0.92, 0.95, 1)
    b.inputs["Roughness"].default_value = 0.05
    b.inputs["IOR"].default_value = 1.5
    for k in ("Transmission Weight", "Transmission"):
        if k in b.inputs:
            b.inputs[k].default_value = 1.0
    b.inputs["Alpha"].default_value = 0.3
    m.diffuse_color = (0.6, 0.75, 0.8, 0.3)
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    return m

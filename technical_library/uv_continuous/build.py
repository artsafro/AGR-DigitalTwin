
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import arguments, require_stage, mark_stage, run_dcc
"""Scoped SOSH1150 v006 stage; see README and replay evidence."""

def build_v005(root):
    """Cut at repeat boundaries; retain the supplied image and metric scale."""
    import json, math
    from pathlib import Path
    import numpy as np
    from collections import defaultdict
    d = json.loads((root / 'source.json').read_text())
    plan = json.loads((root / 'plan.json').read_text())
    v = np.array(d['vertices'])
    uvs = plan['metric_uv']
    scale = 600 / 4056
    polys = []
    edge_splits = defaultdict(dict)
    tris = defaultdict(list)
    for tri in d['triangles']:
        tris[tri['face']].append(tri['vertices'])

    def key(p):
        return tuple(np.round(p, 6))

    def clip(poly, axis, value, positive):
        out = []
        for a, b in zip(poly, poly[1:] + poly[:1]):
            da = (a[1][axis] - value) * (1 if positive else -1)
            db = (b[1][axis] - value) * (1 if positive else -1)
            ina = da >= -1e-10
            inb = db >= -1e-10
            if ina:
                out.append(a)
            if ina != inb:
                f = da / (da - db)
                out.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])))
        clean = []
        for p in out:
            if not clean or np.linalg.norm(p[0] - clean[-1][0]) > 1e-07:
                clean.append(p)
        if len(clean) > 1 and np.linalg.norm(clean[0][0] - clean[-1][0]) < 1e-07:
            clean.pop()
        return clean
    for fi, face in enumerate(d['faces']):
        xy = np.array(uvs[fi]) * scale
        p = [(v[a].copy(), b.copy()) for a, b in zip(face, xy)]
        cross = []
        for i in range(len(xy)):
            a = xy[(i + 1) % len(xy)] - xy[i]
            bb = xy[(i + 2) % len(xy)] - xy[(i + 1) % len(xy)]
            cross.append(a[0] * bb[1] - a[1] * bb[0])
        n = np.array(d['normals'][fi])
        nonplanar = np.ptp(v[face] @ n) > 1e-05
        concave = min(cross) < -1e-09 and max(cross) > 1e-09
        chunks = [p]
        if concave or nonplanar:
            chunks = []
            for tri in tris[fi]:
                coords = np.array([xy[face.index(a)] for a in tri])
                if nonplanar and abs(n[2]) > 0.1:
                    q = v[tri]
                    a = q[1] - q[0]
                    a /= np.linalg.norm(a)
                    normal = np.cross(a, q[2] - q[0])
                    normal /= np.linalg.norm(normal)
                    bb = np.cross(normal, a)
                    coords = np.column_stack(((q - q[0]) @ a, (q - q[0]) @ bb)) * scale + xy[face.index(tri[0])]
                chunks.append([(v[a].copy(), c.copy()) for a, c in zip(tri, coords)])
            xy = np.array([c for chunk in chunks for _, c in chunk])
        for axis in (0, 1):
            for cut in range(math.floor(xy[:, axis].min()) + 1, math.ceil(xy[:, axis].max() - 1e-09)):
                new = []
                for poly in chunks:
                    for positive in (False, True):
                        c = clip(poly, axis, cut, positive)
                        if len(c) >= 3 and abs(sum((a[1][0] * b[1][1] - b[1][0] * a[1][1] for a, b in zip(c, c[1:] + c[:1])))) > 1e-12:
                            new.append(c)
                chunks = new
        for c in chunks:
            shift = np.floor(np.mean([a[1] for a in c], axis=0))
            polys.append(([(a, (b - shift) * (4056 / 4096) + 20 / 4096) for a, b in c], fi))
            for point, xy in c:
                for a, b in zip(face, face[1:] + face[:1]):
                    e = v[b] - v[a]
                    den = e @ e
                    if den < 1e-16:
                        continue
                    t = (point - v[a]) @ e / den
                    if -1e-07 < t < 1 + 1e-07 and np.linalg.norm(point - (v[a] + t * e)) < 2e-06:
                        ek = tuple(sorted((key(v[a]), key(v[b]))))
                        edge_splits[ek][key(point)] = point
    outv = []
    outf = []
    outuv = []
    parents = []
    lookup = {}

    def vert(p):
        k = key(p)
        if k not in lookup:
            lookup[k] = len(outv)
            outv.append(p.tolist())
        return lookup[k]
    for poly, fi in polys:
        expanded = []
        face = d['faces'][fi]
        for a, b in zip(poly, poly[1:] + poly[:1]):
            candidates = []
            e = b[0] - a[0]
            den = e @ e
            if den < 1e-14:
                continue
            for ia, ib in zip(face, face[1:] + face[:1]):
                oe = v[ib] - v[ia]
                od = oe @ oe
                if od < 1e-16:
                    continue
                if all((np.linalg.norm(x[0] - (v[ia] + (x[0] - v[ia]) @ oe / od * oe)) < 2e-06 for x in (a, b))):
                    ek = tuple(sorted((key(v[ia]), key(v[ib]))))
                    for p in edge_splits[ek].values():
                        t = (p - a[0]) @ e / den
                        if 1e-06 < t < 1 - 1e-06:
                            candidates.append((t, (p, a[1] + t * (b[1] - a[1]))))
            expanded.append(a)
            expanded.extend((x for _, x in sorted(candidates, key=lambda x: x[0])))
        clean = []
        for x in expanded:
            if not clean or np.linalg.norm(x[0] - clean[-1][0]) > 4e-06:
                clean.append(x)
        if len(clean) > 1 and np.linalg.norm(clean[0][0] - clean[-1][0]) <= 4e-06:
            clean.pop()
        expanded = clean
        center = (np.mean([a[0] for a in expanded], axis=0), np.mean([a[1] for a in expanded], axis=0))
        mids = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(expanded, expanded[1:] + expanded[:1])]
        for i, a in enumerate(expanded):
            q = [a, mids[i], center, mids[i - 1]]
            ids = [vert(x[0]) for x in q]
            if len(set(ids)) < 4:
                continue
            outf.append(ids)
            outuv.append([x[1].tolist() for x in q])
            parents.append(fi)
    result = {'vertices': outv, 'faces': outf, 'uv': outuv, 'parents': parents, 'source': d['name'], 'density': 600, 'texture_modified': False, 'unresolved_phase_edges': plan['report']['conflicts']}
    (root / 'build.json').write_text(json.dumps(result), encoding='utf-8')
    print(json.dumps({'vertices': len(outv), 'quads': len(outf), 'phase_edges': len(result['unresolved_phase_edges']), 'uv_min': np.min(outuv), 'uv_max': np.max(outuv)}))

def build_final_texture(root):
    """Native editable periodic F1 texture source; mirrored, with wrap padding."""
    import numpy as np, json, hashlib
    from pathlib import Path
    from PIL import Image
    N = 4096
    PAD = 20
    PERIOD = N - 2 * PAD
    source = root / 'T_Template_Address_001_Diffuse_1.1001.png'
    with Image.open(source) as im:
        base = float(np.median(np.asarray(im)[768:900, 430:560]))
    image = np.empty((N, N, 3), np.uint8)
    x = np.arange(N, dtype=np.float32)[None, :]
    for top in range(0, N, 128):
        y = np.arange(top, top + 128, dtype=np.float32)[:, None]
        u = 1 - (x + 0.5 - PAD) / PERIOD
        v = (y + 0.5 - PAD) / PERIOD
        plain = base + 0.55 * np.sin(2 * np.pi * 16 * u) * np.sin(2 * np.pi * 16 * v)
        cx = abs(3 * u - np.rint(3 * u)) * PERIOD / 3
        cy = abs(8 * v - np.rint(8 * v)) * PERIOD / 8
        grey = np.where((cx < 2.5) | (cy < 2.5), 85.0, plain)
        h = abs(8 * v - 0.5 - np.rint(8 * v - 0.5)) * PERIOD / 8
        ha = 0.68 * np.exp(-0.5 * (h / 7.5) ** 2) + 0.15 * np.exp(-0.5 * (h / 18) ** 2)
        phase = 2 * u + v - 0.22
        dist = abs(phase - np.rint(phase)) * PERIOD / np.sqrt(5)
        da = 0.55 * np.exp(-0.5 * (dist / 7) ** 2) + 0.06 * np.exp(-0.5 * (dist / 19) ** 2)
        a = np.maximum(ha, da)
        lit = plain * (1 - a) + 220 * a
        value = np.where(a >= 0.17, lit, grey * (1 - a) + 220 * a)
        image[top:top + 128] = np.clip(np.rint(value), 0, 255).astype(np.uint8)[:, :, None]
    for k in range(2 * PAD):
        image[k] = image[k + PERIOD]
        image[:, k] = image[:, k + PERIOD]
    target = root / 'T_Template_Address_001_Diffuse_FlipH_v005.1001.png'
    Image.fromarray(image).save(target)
    with Image.open(target) as check:
        a = np.asarray(check)
        assert check.size == (4096, 4096)
        assert np.array_equal(a[PAD - 1:PAD + 1], a[N - PAD - 1:N - PAD + 1])
        assert np.array_equal(a[:, PAD - 1:PAD + 1], a[:, N - PAD - 1:N - PAD + 1])
    report = {'resolution': [N, N], 'padding': PAD, 'period_pixels': PERIOD, 'base': base, 'cassette_columns': 3, 'cassette_rows': 8, 'white_horizontal_lines': 8, 'diagonal_lines': 2, 'horizontal_mirror': True, 'bilinear_boundary_samples_equal': True, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'method': 'Native editable F1 procedural texture source; imagegen study discarded because counts/edge continuity were not preserved'}
    (root / 'texture-v005-qa.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))

def apply_v006(root):
    import bpy, json, shutil
    from pathlib import Path
    from mathutils import Vector
    b = json.loads((root / 'build.json').read_text())
    o = bpy.context.active_object
    assert o.name == b['source']
    original = next((m for m in bpy.data.meshes if len(m.polygons) == 8755))
    mesh = bpy.data.meshes.new(original.name + '_UV1500_v002')
    inv = o.matrix_world.inverted()
    mesh.from_pydata([inv @ Vector(v) for v in b['vertices']], [], b['faces'])
    mesh.update()
    uv = mesh.uv_layers.new(name='UV_1001_Range550_1500')
    for poly, coords in zip(mesh.polygons, b['uv']):
        for li, xy in zip(poly.loop_indices, coords):
            uv.data[li].uv = tuple((max(0, min(1, c)) for c in xy))
    attr = mesh.attributes.new('source_face', 'INT', 'FACE')
    for a, i in zip(attr.data, b['parents']):
        a.value = i
    mat = original.materials[0].copy()
    mat.name = 'UDIM_1001_Continuous_FlipH_v005'
    src = root / 'T_Template_Address_001_Diffuse_FlipH_v005.1001.png'
    dest = root / src.name
    if not dest.exists():
        shutil.copy2(src, dest)
    im = bpy.data.images.load(str(dest), check_existing=False)
    im.pack()
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image and ('Diffuse' in node.image.name):
            node.image = im
    mesh.materials.append(mat)
    o.data = mesh
    o['UV_status'] = 'Vertical wall phase aligned; visual acceptance pending'
    o['density_range_px_m'] = [550, 1500]
    rep = {'mesh_validate_repairs': mesh.validate(verbose=False), 'vertices': len(mesh.vertices), 'faces': len(mesh.polygons), 'packed_diffuse': bool(im.packed_file), 'image_size': list(im.size)}
    for a in bpy.context.screen.areas if bpy.context.screen else []:
        if a.type == 'VIEW_3D':
            a.spaces.active.shading.type = 'MATERIAL'
            a.spaces.active.overlay.show_overlays = False
    bpy.context.scene.render.resolution_x = 1600
    bpy.context.scene.render.resolution_y = 900
    bpy.context.scene.render.resolution_percentage = 100
    bpy.context.scene.render.filepath = str(root / 'trial_view_v002.png')
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.ops.wm.save_as_mainfile(filepath=str(root / 'walls_UV550-1500_FlipH_v006.blend'))
    (root / 'apply.json').write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep))


def main():
    args = arguments()
    root = require_stage(args.output, 'solve')
    if args.phase == 'dcc':
        import bpy
        bpy.ops.wm.open_mainfile(filepath=str(root / 'source_v001.blend'))
        apply_v006(root)
        return
    build_v005(root)
    build_final_texture(root)
    run_dcc(Path(__file__), root, args.blender)
    mark_stage(root, 'build')
    print('Stage 3/4: build complete')


if __name__ == '__main__':
    main()

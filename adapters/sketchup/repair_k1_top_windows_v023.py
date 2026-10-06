"""Separate upper/lower K1 windows, embed planes, and add simple reveal quads.

The top in v022 is a draft. This script changes only its window planes and
creates outward-facing opening returns; it preserves v022 and all typical meshes.
"""
import bpy, bmesh, json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

root = Path('jobs/GLB-NPM/outputs/tower-k1-v011').resolve()
bpy.ops.wm.open_mainfile(filepath=str(root / 'GLB_K1_assembled_v022.blend'))
windows = sorted((o for o in bpy.data.objects if o.name.startswith('TOP_Window')), key=lambda o: o.name)
assert len(windows) == 44
source_z = {'lower_start': 66.00105, 'spandrel_start': 68.90105,
            'spandrel_end': 69.90105, 'upper_start': 70.03105,
            'upper_end': 72.40105}
embed = .01
wall=bpy.data.objects['TOP_[Black Lines 1]']
wall_bvh=BVHTree.FromPolygons([wall.matrix_world@v.co for v in wall.data.vertices],
                               [list(p.vertices) for p in wall.data.polygons])
spandrel=bpy.data.objects['TOP_Материал8']
spandrel_bvh=BVHTree.FromPolygons([spandrel.matrix_world@v.co for v in spandrel.data.vertices],
                                  [list(p.vertices) for p in spandrel.data.polygons])
rv, rf, ids = [], [], []
material = bpy.data.materials.get('M_Reveal_Color') or bpy.data.materials.new('M_Reveal_Color')
report = {'input': 'GLB_K1_assembled_v022.blend', 'output': 'GLB_K1_assembled_v023.blend',
          'lower_planes': 0, 'upper_planes': 0, 'reveal_quads': 0,
          'plane_embed_m': embed, 'reveal_depths_m': [], 'unmeasured_openings': [],
          'upper_sill_gaps_closed': 0, 'unmeasured_upper_sills': [],
          'source_z_m': source_z, 'delivery_passed': False}

for o in windows:
    assert len(o.data.polygons) == 1 and len(o.data.vertices) == 4
    old = [o.matrix_world @ o.data.vertices[i].co for i in o.data.polygons[0].vertices]
    lower = o.get('source_definition') != 14155
    zlo = min(v.z for v in old)
    zhi = max(v.z for v in old)
    if lower:
        assert zlo < 66.01 and zhi > 72.37, (o.name, zlo, zhi)
        opening_top = source_z['spandrel_start']
        for v in old:
            if abs(v.z-zhi) < 1e-4:
                v.z = opening_top
        report['lower_planes'] += 1
    else:
        assert zlo > 70.02 and zhi < 72.42
        report['upper_planes'] += 1

    low = [v for v in old if abs(v.z-min(p.z for p in old)) < 1e-4]
    assert len(low) == 2
    tangent = (low[1] - low[0]).normalized()
    normal = (o.matrix_world.to_3x3() @ o.data.polygons[0].normal).normalized()
    center = sum(old, Vector()) / 4
    # Choose the exterior using the measured tower footprint centre. The source
    # plane normal itself is not consistently oriented across window definitions.
    radial = Vector((center.x-14.25, center.y-6.0, 0))
    outward = normal if normal.dot(radial) >= 0 else -normal
    width=max(v.dot(tangent) for v in old)-min(v.dot(tangent) for v in old)
    depth_hits=[]
    for side in (-1,1):
        point=center+tangent*side*(width/2+.03)
        hit,hn,face,d=wall_bvh.ray_cast(point+outward*.8,-outward,1.6)
        if hit is not None and hn.dot(outward)>.95:
            depth_hits.append(.8-d)
    if depth_hits:
        outer_depth=sum(depth_hits)/len(depth_hits)+embed
    else:
        # For diagonal corner openings, the planar side probe may miss the
        # adjacent wall. Keep the source-row depth and flag for visual QA.
        outer_depth=(.195 if lower else .22375)+embed
        report['unmeasured_openings'].append(o.name)
    report['reveal_depths_m'].append({'window':o.name,'measured':depth_hits,'used':outer_depth})
    sill_depth=None
    if not lower:
        sample=Vector((center.x,center.y,source_z['spandrel_end']-.01))
        hit,hn,face,d=spandrel_bvh.ray_cast(sample+outward*.8,-outward,1.6)
        if hit is not None and hn.dot(outward)>.95:
            sill_depth=.8-d
        else:
            report['unmeasured_upper_sills'].append(o.name)
    tmid = sum(v.dot(tangent) for v in old) / 4
    zmid = sum(v.z for v in old) / 4

    # The original rectangle is the opening line. Enlarge the plane 10 mm on
    # every side so its boundary lies under the new perpendicular reveal quads.
    new = []
    for v in old:
        tt = 1 if v.dot(tangent) > tmid else -1
        zz = 1 if v.z > zmid else -1
        new.append(v + tangent * (tt * embed) + Vector((0, 0, zz * embed)))
    for idx, v in zip(o.data.polygons[0].vertices, new):
        o.data.vertices[idx].co = o.matrix_world.inverted() @ v
    o.data.update()
    if normal.dot(radial)<0:
        bm=bmesh.new();bm.from_mesh(o.data)
        next(iter(bm.faces)).normal_flip()
        bm.to_mesh(o.data);bm.free();o.data.update()
    o['opening_row'] = 'lower' if lower else 'upper'
    o['opening_embed_m'] = embed
    o['opening_front_offset_m'] = outer_depth
    o['status'] = 'TOP_WINDOW_SEATED_REVEAL_REVIEW_PENDING'

    for j in range(4):
        a, b = old[j], old[(j+1) % 4]
        if lower and abs(a.z-source_z['spandrel_start'])<.0002 and abs(b.z-source_z['spandrel_start'])<.0002:
            # The underside of the existing opaque spandrel already closes
            # this opening. Duplicating it produces coplanar flicker.
            continue
        front_a, front_b = a + outward * outer_depth, b + outward * outer_depth
        if sill_depth is not None and not lower and abs(a.z-source_z['upper_start'])<.0002 and abs(b.z-source_z['upper_start'])<.0002:
            # The source spandrel stops 130 mm below the upper glass. Replace
            # the horizontal bottom return by one sloped sill: its buried end
            # reaches 10 mm below the spandrel top and 10 mm behind its face.
            front_a=a+outward*(sill_depth-embed)+Vector((0,0,source_z['spandrel_end']-embed-a.z))
            front_b=b+outward*(sill_depth-embed)+Vector((0,0,source_z['spandrel_end']-embed-b.z))
            report['upper_sill_gaps_closed']+=1
        quad = [a, b, front_b, front_a]
        n = (quad[1]-quad[0]).cross(quad[2]-quad[0])
        if n.dot(center - (a+b)/2) < 0:
            quad.reverse()
        base = len(rv)
        rv.extend(tuple(v) for v in quad)
        rf.append((base, base+1, base+2, base+3))
        ids.append((o.name, j))

mesh = bpy.data.meshes.new('K1_TOP_REVEALS_10MM')
mesh.from_pydata(rv, [], rf)
mesh.materials.append(material)
mesh.update()
uv = mesh.uv_layers.new(name='Atlas_UV_DRAFT')
for p in mesh.polygons:
    for li, coord in zip(p.loop_indices, ((0,0),(1,0),(1,1),(0,1))):
        uv.data[li].uv = coord
reveals = bpy.data.objects.new(mesh.name, mesh)
bpy.data.collections['K1_TOP_DRAFT_SOURCE_CONTOURS'].objects.link(reveals)
reveals['status'] = 'DRAFT_REVEAL_MATERIAL_AND_WALL_JOINT_QA_PENDING'
report['reveal_quads'] = len(rf)

scene = bpy.context.scene
scene['status'] = 'K1_TOP_WINDOWS_SEATED_SILL_REPAIR_PENDING'
scene['delivery'] = False
target = root / report['output']
bpy.ops.wm.save_as_mainfile(filepath=str(target))
(root / 'top-windows-v023.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('TOP_WINDOW_REPAIR=' + json.dumps(report))

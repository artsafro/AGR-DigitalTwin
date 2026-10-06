"""Measure saved wall reveals and seat the GLB windows halfway through them."""
import bpy, json, hashlib
from pathlib import Path

job = Path('jobs/GLB-NPM').resolve()
out = job / 'outputs/clearance-ab-v007'
out.mkdir(exist_ok=True)
target = out / 'GLB_AB_clearance_v007.blend'
assert not target.exists()
bpy.ops.wm.open_mainfile(filepath=str(job / 'outputs/clearance-ab-v006/GLB_AB_clearance_v006.blend'))

def signature(ob):
    me = ob.data
    value = ([list(v.co) for v in me.vertices], [list(p.vertices) for p in me.polygons],
             [p.material_index for p in me.polygons], list(map(list, ob.matrix_world)),
             [[list(d.uv) for d in uv.data] for uv in me.uv_layers])
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()

unchanged = {o.name: signature(o) for o in bpy.data.objects if o.type == 'MESH' and o.get('role') != 'windows'}
reveals = []
for ob in bpy.data.objects:
    if ob.type != 'MESH': continue
    for p in ob.data.polygons:
        if ob.data.materials[p.material_index].name == 'M_Reveal_Color':
            reveals.append([ob.matrix_world @ ob.data.vertices[i].co for i in p.vertices])
report = []
windows = [o for o in bpy.data.objects if o.get('role') == 'windows']
for win in windows:
    inv = win.matrix_world.inverted()
    sides = [[], []]
    for face in reveals:
        pts = [inv @ v for v in face]
        if min(v.z for v in pts) < -1.141 or max(v.z for v in pts) > 1.161: continue
        if all(abs(v.x - .95625) < .005 for v in pts): sides[0].extend(pts)
        if all(abs(v.y + .67625) < .005 for v in pts): sides[1].extend(pts)
    assert all(sides), win.name
    yrange = [min(v.y for v in sides[0]), max(v.y for v in sides[0])]
    xrange = [min(v.x for v in sides[1]), max(v.x for v in sides[1])]
    assert abs(yrange[1]-yrange[0]-.24) < .0001, (win.name, yrange)
    assert abs(xrange[1]-xrange[0]-.24) < .0001, (win.name, xrange)
    report.append({'object':win.name, 'front_reveal_depth_y':yrange, 'side_reveal_depth_x':xrange,
                   'mid_y':sum(yrange)/2, 'mid_x':sum(xrange)/2,
                   'far_x':sum(v.x for v in sides[0])/len(sides[0]),
                   'far_y':sum(v.y for v in sides[1])/len(sides[1])})

assert len(report) == 52
for win, measured in zip(windows, report):
    win.data = win.data.copy()
    for v in win.data.vertices:
        if abs(v.co.x+.64375) < .00001: v.co.x = measured['mid_x']
        if abs(v.co.y-.36375) < .00001: v.co.y = measured['mid_y']
        if abs(v.co.x-.96625) < .00001: v.co.x = measured['far_x']+.01
        if abs(v.co.y+.68625) < .00001: v.co.y = measured['far_y']-.01
    win.data.update()
bpy.context.scene['status'] = 'WINDOW_MIDDEPTH_V007_VISUAL_ACCEPTANCE_PENDING'
bpy.context.scene['delivery'] = False
bpy.ops.wm.save_as_mainfile(filepath=str(target))
bpy.ops.wm.open_mainfile(filepath=str(target))
assert all(signature(bpy.data.objects[name]) == digest for name, digest in unchanged.items())
for row in report:
    win = bpy.data.objects[row['object']]
    assert len(win.data.polygons) == 2
    for p in win.data.polygons:
        pts = [win.data.vertices[i].co for i in p.vertices]
        assert len(pts) == 4 and p.area > 0
        assert (all(abs(v.y-row['mid_y']) < .0001 for v in pts) or
                all(abs(v.x-row['mid_x']) < .0001 for v in pts))
    pts = [v.co for v in win.data.vertices]
    assert abs(max(v.x for v in pts)-(row['far_x']+.01)) < .00001
    assert abs(min(v.y for v in pts)-(row['far_y']-.01)) < .00001
    assert abs(min(v.z for v in pts)+1.15) < .00001
    assert abs(max(v.z for v in pts)-1.17) < .00001
faces = [{'object':o.name, 'index':p.index, 'points':[list(o.matrix_world @ o.data.vertices[i].co) for i in p.vertices]}
         for o in bpy.data.objects if o.type == 'MESH' for p in o.data.polygons]
(out/'faces-readback.json').write_text(json.dumps(faces), encoding='utf-8')
(out/'window-seating-readback.json').write_text(json.dumps({'windows':report, 'saved_readback':True,
    'other_meshes_unchanged':len(unchanged), 'edge_embed_m':.01, 'depth_move_outward_m':.13,
    'reveal_depth_m':.24, 'margin_to_front_and_back_m':.12}, indent=2), encoding='utf-8')
print('SEATED', len(report), 'windows; other meshes unchanged:', len(unchanged))

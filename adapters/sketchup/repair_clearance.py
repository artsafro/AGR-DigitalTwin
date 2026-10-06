"""Specific GLB node placement fixes; independent saved-file clearance follows."""
import bpy,bmesh,json,sys
from pathlib import Path
from mathutils import Vector
import numpy as np
job=Path('jobs/GLB-NPM').resolve();out=job/'outputs/clearance-ab-v005';out.mkdir(parents=True,exist_ok=True)
target=out/'GLB_AB_clearance_v005.blend';assert not target.exists()
bpy.ops.wm.open_mainfile(filepath=str(job/'outputs/sills-ab-v004/GLB_AB_sills_v004.blend'))
done=set();changes=[]
for ob in bpy.data.objects:
    if ob.type!='MESH':continue
    role=ob.get('role');me=ob.data
    if role=='windows' and me.name not in done:
        # Reveal clear bounds: bottom -1.14, top +1.16, far edges +.95625/-.67625.
        # Cover all four opening edges by 10 mm; move depth inside by 10 mm.
        for v in me.vertices:
            if abs(v.co.x+.65375)<1e-5:v.co.x+=.01
            if abs(v.co.y-.37375)<1e-5:v.co.y-=.01
            if v.co.z>0:v.co.z=1.17
        changes.append({'mesh':me.name,'window_depth_offset_m':.01,'opening_edge_embed_m':.01})
    elif role=='ac' and me.name not in done:
        for v in me.vertices:v.co.x-=.01 if v.co.x>0 else -.01
        changes.append({'mesh':me.name,'ac_width_reduction_m':.02})
    elif role=='simple_sills':
        # Offset the outline, maintaining horizontal top/bottom and joined corners.
        # 20 mm separates rear sill planes from windows now moved inward 10 mm.
        original=[v.co.copy() for v in me.vertices];normals={i:[] for i in range(len(me.vertices))}
        for p in me.polygons:
            if abs(p.normal.z)>.001:continue
            for i in p.vertices:normals[i].append([p.normal.x,p.normal.y])
        for i,rows in normals.items():
            if not rows:continue
            a=np.unique(np.round(rows,6),axis=0)
            delta=np.linalg.lstsq(a,np.full(len(a),.02),rcond=None)[0]
            assert np.linalg.norm(delta)<.1
            me.vertices[i].co.x+=float(delta[0]);me.vertices[i].co.y+=float(delta[1])
        changes.append({'mesh':me.name,'outline_m':.02})
    elif 'Материал3' in ob.name:
        # Raise the source wall cap into the next floor, not coincident with its underside.
        high=max(v.co.z for v in me.vertices)
        for v in me.vertices:
            if abs(v.co.z-high)<1e-5:v.co.z+=.01
        changes.append({'mesh':me.name,'wall_top_embed_m':.01})
    me.update();done.add(me.name)
scene=bpy.context.scene;scene['status']='CLEARANCE_V005_TRIAL';scene['delivery']=False
bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target))
faces=[]
for o in bpy.data.objects:
    if o.type!='MESH':continue
    for p in o.data.polygons:
        faces.append({'object':o.name,'role':o.get('role','body'),'index':p.index,
                      'points':[list(o.matrix_world@o.data.vertices[i].co) for i in p.vertices]})
(out/'faces-readback.json').write_text(json.dumps(faces),encoding='utf-8')
(out/'changes.json').write_text(json.dumps(changes,indent=2),encoding='utf-8')
print('Saved initial clearance trial')

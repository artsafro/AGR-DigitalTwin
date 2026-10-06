import bpy, json, math, bmesh
from pathlib import Path
from collections import Counter
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/audit-v001')
groups={n:[o for o in bpy.data.collections[n].objects if o.type=='MESH'] for n in ['LP','Revit','LP_old']}
report={'groups':{},'topology':[], 'coverage':[]}
for name,objects in groups.items():
    report['groups'][name]={'meshes':len(objects),'faces':sum(len(o.data.polygons) for o in objects),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects)}
for o in groups['LP']:
    bm=bmesh.new(); bm.from_mesh(o.data)
    report['topology'].append(dict(name=o.name,faces=len(bm.faces),sizes=dict(Counter(len(f.verts) for f in bm.faces)),
        boundary_edges=sum(e.is_boundary for e in bm.edges),multi_face_edges=sum(len(e.link_faces)>2 for e in bm.edges),
        loose_edges=sum(not e.link_faces for e in bm.edges),zero_area=sum(f.calc_area()<1e-10 for f in bm.faces),
        materials=[m.name if m else None for m in o.data.materials]))
    bm.free()
def tree(objects):
    vv=[]; ff=[]
    for o in objects:
        off=len(vv); vv.extend(o.matrix_world @ v.co for v in o.data.vertices)
        ff.extend(tuple(off+i for i in p.vertices) for p in o.data.polygons)
    return BVHTree.FromPolygons(vv,ff,all_triangles=False)
trees={n:tree(groups[n]) for n in ['LP','Revit']}
# Dominant vertical facade directions, weighted by face area.
angles=Counter()
for o in groups['LP']:
    for p in o.data.polygons:
        n=o.matrix_world.to_3x3() @ p.normal
        if abs(n.z)<.1: angles[round(math.degrees(math.atan2(n.y,n.x))%180)]+=p.area
report['normal_angles_area']=angles.most_common(12)
# Orthographic sample coverage. This measures projected surfaces, not labor completion.
step=.4
for axis,sign in [(0,-1),(0,1),(1,-1),(1,1)]:
    horizontal=1-axis; low=(-84 if horizontal==1 else -16); high=(1 if horizontal==1 else 62)
    buckets={k:Counter() for k in ['all','-2..11','11..20','20..28','28..38']}
    for i in range(math.ceil((high-low)/step)):
        for j in range(100):
            z=-2+(j+.5)*step; a=low+(i+.5)*step
            origin=Vector((0,0,z)); origin[horizontal]=a; origin[axis]=sign*120
            direction=Vector((0,0,0)); direction[axis]=-sign
            r=trees['Revit'].ray_cast(origin,direction,250); l=trees['LP'].ray_cast(origin,direction,250)
            band='-2..11' if z<11 else '11..20' if z<20 else '20..28' if z<28 else '28..38'
            for key in ['all',band]:
                b=buckets[key]
                if r[0] is not None:
                    b['reference_samples']+=1
                    if l[0] is not None:
                        b['lp_projected_samples']+=1
                        d=abs(l[3]-r[3])
                        b['within_0.2m']+=d<=.2; b['within_0.5m']+=d<=.5
                elif l[0] is not None: b['lp_outside_reference']+=1
    report['coverage'].append({'view':('X' if axis==0 else 'Y')+('+' if sign>0 else '-'),'bands':buckets})
(out/'geometry-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('AUDIT',json.dumps(report['groups']),flush=True)
# Identical orthographic cameras for current LP and Revit; source is never saved here.
scene=bpy.context.scene
scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=1100; scene.render.resolution_y=900; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
shade=scene.display.shading; shade.light='STUDIO'; shade.color_type='SINGLE'; shade.single_color=(.65,.69,.74)
shade.show_shadows=True; shade.show_cavity=True; shade.cavity_type='BOTH'; shade.show_object_outline=True
shade.background_type='WORLD'; scene.world.color=(.12,.12,.12)
camdata=bpy.data.cameras.new('AuditCamera'); cam=bpy.data.objects.new('AuditCamera',camdata); scene.collection.objects.link(cam); scene.camera=cam
camdata.type='ORTHO'; camdata.ortho_scale=85
target=Vector((22,-43,16))
for view,delta in [('A',(90,-110,85)),('B',(-100,100,70)),('TOP',(0,0,150))]:
    cam.location=target+Vector(delta); cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    for group in ['Revit','LP']:
        for n,objects in groups.items():
            for o in objects: o.hide_render=n!=group
        scene.render.filepath=str(out/f'{group}-{view}.png'); bpy.ops.render.render(write_still=True)
        print('IMAGE',group,view,flush=True)
print('DONE',flush=True)

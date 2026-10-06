import bpy,bmesh,json,math
from pathlib import Path
from collections import Counter
root=Path('C:/Users/artsafro/.AGR_Project/jobs/REVIT-OPENINGS');out=root/'outputs/source-v001'
types=json.loads((out/'types-raw.json').read_text(encoding='utf-8'))
report=[]
for t in types:
    me=bpy.data.meshes.new('inspect');me.from_pydata(t['vertices'],[],t['faces']);me.update()
    bm=bmesh.new();bm.from_mesh(me)
    before={'v':len(bm.verts),'f':len(bm.faces),'boundary':sum(e.is_boundary for e in bm.edges),'nonmanifold':sum(len(e.link_faces)>2 for e in bm.edges)}
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.000001)
    bmesh.ops.dissolve_degenerate(bm,dist=1e-8,edges=list(bm.edges))
    bmesh.ops.dissolve_limit(bm,angle_limit=0.00001,use_dissolve_boundaries=False,verts=list(bm.verts),edges=list(bm.edges),delimit={'NORMAL'})
    bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4],quad_method='BEAUTY',ngon_method='BEAUTY')
    bmesh.ops.join_triangles(bm,faces=[f for f in bm.faces if len(f.verts)==3],angle_face_threshold=0.0001,angle_shape_threshold=math.pi,cmp_seam=False,cmp_sharp=False,cmp_uvs=False,cmp_vcols=False,cmp_materials=True)
    row={'id':t['id'],'category':t['category'],'before':before,'after':{'v':len(bm.verts),'f':len(bm.faces),'degrees':dict(Counter(len(f.verts) for f in bm.faces)),'boundary':sum(e.is_boundary for e in bm.edges),'nonmanifold':sum(len(e.link_faces)>2 for e in bm.edges)}}
    report.append(row);bm.free();bpy.data.meshes.remove(me)
(out/'topology-probe.json').write_text(json.dumps(report),encoding='utf-8')
print(json.dumps({'types':len(report),'with_nonmanifold':sum(r['after']['nonmanifold']>0 for r in report),'with_boundary':sum(r['after']['boundary']>0 for r in report),'allquad':sum(set(r['after']['degrees'])=={4} for r in report),'samples':[r for r in report if r['id'] in ['WINDOW_021','WINDOW_034','WINDOW_027','DOOR_146','DOOR_096','DOOR_047']]}))

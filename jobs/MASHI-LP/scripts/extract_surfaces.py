import bpy,json,math
from pathlib import Path
from collections import defaultdict,Counter
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/model-v002')
objects=list(bpy.data.collections['Revit'].objects)
vv=[];ff=[]
for o in objects:
    offset=len(vv);vv.extend(o.matrix_world@v.co for v in o.data.vertices)
    ff.extend(tuple(offset+i for i in p.vertices) for p in o.data.polygons)
tree=BVHTree.FromPolygons(vv,ff)
del vv,ff
clusters=defaultdict(list); stats=Counter();raw=[]
for o in objects:
    if o.name=='MultiMat_1':continue # dense entry floor, not wall source
    points=[o.matrix_world@v.co for v in o.data.vertices]
    o.data.calc_loop_triangles()
    for p in o.data.loop_triangles:
        pts=[points[i] for i in p.vertices]
        cross=(pts[1]-pts[0]).cross(pts[2]-pts[0]);area=cross.length*.5
        if area<.006: continue
        n=cross.normalized();c=sum(pts,Vector())/3
        raw.append({'object':o.name,'face':p.polygon_index,'coords':[list(v) for v in pts],'normal':list(n),'area':area})
        # Visibility selects exposed faces of the reference, not its interior.
        hit=tree.ray_cast(c+n*.003,n,250)
        if hit[0] is not None:
            if tree.ray_cast(c-n*.003,-n,250)[0] is not None:continue
            n=-n
        d=n.dot(c)
        # Record source precision; rounded key groups coplanar import triangles.
        key=tuple(round(float(v),4) for v in n)+(round(float(d),3),)
        clusters[key].append({'object':o.name,'face':p.polygon_index,'coords':[list(v) for v in pts],'area':area})
        stats[o.name]+=1
data=[]
for key,faces in clusters.items():
    area=sum(f['area'] for f in faces)
    if area<.08:continue
    data.append({'normal':key[:3],'d':key[3],'area':area,'faces':faces})
data.sort(key=lambda x:-x['area'])
for i,c in enumerate(data):c['id']=i
(out/'source-planes.json').write_text(json.dumps(data),encoding='utf-8')
(out/'raw-triangles.json').write_text(json.dumps(raw),encoding='utf-8')
lp=[]
for o in bpy.data.collections['LP'].objects:
    if o.type!='MESH':continue
    points=[o.matrix_world@v.co for v in o.data.vertices]
    lp.append({'name':o.name,'vertices':[list(v) for v in points],
       'faces':[list(p.vertices) for p in o.data.polygons], 'normals':[list((o.matrix_world.to_3x3().inverted().transposed()@p.normal).normalized()) for p in o.data.polygons]})
(out/'lp-geometry.json').write_text(json.dumps(lp),encoding='utf-8')
summary=[]
for c in data[:100]:
    pts=[p for f in c['faces'] for p in f['coords']]
    summary.append({k:c[k] for k in ['id','normal','d','area']}|{'objects':dict(Counter(f['object'] for f in c['faces'])),'bounds':[[round(min(p[a] for p in pts),2) for a in range(3)],[round(max(p[a] for p in pts),2) for a in range(3)]]})
(out/'plane-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print('EXTRACTED',len(data),'planes',sum(len(c['faces']) for c in data),'faces',flush=True)

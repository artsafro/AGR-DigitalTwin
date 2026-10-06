import bpy,json,math
from pathlib import Path
from collections import Counter,defaultdict
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=Path('C:/Users/artsafro/.AGR_Project/jobs/MASHI-LP/outputs/model-v002')
def tree(coll):
    vv=[];ff=[];ids=[]
    for o in bpy.data.collections[coll].objects:
        if o.type!='MESH':continue
        off=len(vv);vv.extend(o.matrix_world@v.co for v in o.data.vertices)
        for p in o.data.polygons:ff.append(tuple(off+i for i in p.vertices));ids.append((o.name,p.index))
    return BVHTree.FromPolygons(vv,ff),ids
ref,ids=tree('Revit');lp,_=tree('LP');counts=Counter();positions=defaultdict(list);facecounts=Counter()
for axis,sign in [(0,-1),(0,1),(1,-1),(1,1)]:
    horizontal=1-axis;lo=-84 if horizontal==1 else -16;hi=1 if horizontal==1 else 62
    for i in range(math.ceil((hi-lo)/.4)):
        for j in range(100):
            origin=Vector((0,0,-2+(j+.5)*.4));origin[horizontal]=lo+(i+.5)*.4;origin[axis]=sign*120
            direct=Vector((0,0,0));direct[axis]=-sign
            r=ref.ray_cast(origin,direct,250);l=lp.ray_cast(origin,direct,250)
            if r[0] is not None and (l[0] is None or abs(r[3]-l[3])>.2):
                key=(f'{axis}:{sign}',ids[r[2]][0]);counts[key]+=1;positions[key].append(list(r[0]));facecounts[ids[r[2]]]+=1
rows=[]
for key,count in counts.most_common():
    pp=positions[key];rows.append({'view':key[0],'object':key[1],'samples':count,'bounds':[[min(p[a] for p in pp) for a in range(3)],[max(p[a] for p in pp) for a in range(3)]]})
(out/'remaining-gaps.json').write_text(json.dumps({'groups':rows,'source_faces':[{'object':o,'face':f,'samples':c} for (o,f),c in facecounts.most_common()]},indent=2),encoding='utf-8')
print(json.dumps(rows[:14]),flush=True)

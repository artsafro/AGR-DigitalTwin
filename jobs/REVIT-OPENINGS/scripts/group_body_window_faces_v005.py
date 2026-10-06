"""Group contiguous ID=2 window faces in the copied body and measure their world bounds."""
import json
from collections import Counter,defaultdict
from pathlib import Path
import bpy
from mathutils import Vector

root=Path(__file__).resolve().parents[1]
out=root/'outputs/body-v005'
bpy.ops.wm.open_mainfile(filepath=str(out/'live-autosave-snapshot.blend'))
body=bpy.data.objects['skolka']
mesh=body.data
face_ids=[p.index for p in mesh.polygons if p.material_index==1]
parent={i:i for i in face_ids}
def find(i):
    while parent[i]!=i:
        parent[i]=parent[parent[i]];i=parent[i]
    return i
def union(a,b):
    a,b=find(a),find(b)
    if a!=b:parent[b]=a
edges={}
for i in face_ids:
    face=mesh.polygons[i]
    for edge in face.edge_keys:
        if edge in edges:union(i,edges[edge])
        else:edges[edge]=i
groups=defaultdict(list)
for i in face_ids:groups[find(i)].append(i)
records=[]
for faces in groups.values():
    vertices={i for f in faces for i in mesh.polygons[f].vertices}
    points=[body.matrix_world@mesh.vertices[i].co for i in vertices]
    lo=[min(p[i] for p in points) for i in range(3)]
    hi=[max(p[i] for p in points) for i in range(3)]
    normals=Counter(tuple(round(v,2) for v in body.matrix_world.to_3x3()@mesh.polygons[f].normal) for f in faces)
    normal=body.matrix_world.to_3x3()@mesh.polygons[faces[0]].normal
    normal.normalize()
    right=Vector((-normal.y,normal.x,0));right.normalize()
    u=[p.dot(right) for p in points]
    d=[p.dot(normal) for p in points]
    z=[p.z for p in points]
    origin=right*min(u)+normal*(sum(d)/len(d))+Vector((0,0,min(z)))
    records.append({'faces':faces,'count':len(faces),'bbox_min':[round(v,4) for v in lo],
                    'bbox_max':[round(v,4) for v in hi],
                    'dimensions':[round(hi[i]-lo[i],4) for i in range(3)],
                    'area':round(sum(mesh.polygons[f].area for f in faces),4),
                    'normals':normals.most_common(4),
                    'normal_out':[round(float(v),6) for v in normal],
                    'right':[round(float(v),6) for v in right],
                    'origin':[round(float(v),6) for v in origin],
                    'width_m':round(max(u)-min(u),4),'height_m':round(max(z)-min(z),4),
                    'planarity_error_m':round(max(d)-min(d),6),
                    'min_normal_dot':round(min(normal.dot(body.matrix_world.to_3x3()@mesh.polygons[f].normal)
                                            for f in faces),6)})
records.sort(key=lambda x:(-x['count'],-x['area']))
(out/'body-window-face-groups.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'components':len(records),'face_count_distribution':Counter(x['count'] for x in records).most_common(20),
    'largest':[{k:v for k,v in x.items() if k!='faces'} for x in records[:20]]},ensure_ascii=False))

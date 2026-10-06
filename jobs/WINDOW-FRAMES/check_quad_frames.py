"""Read back the saved frame model and check geometric risks."""
import bpy, json
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'outputs'
path=OUT/'window_frames_quad_v002.blend'
assert Path(bpy.data.filepath).resolve()==path.resolve()
o=bpy.data.objects['WindowFrames_Quad_v002']
m=o.data
assert len(m.vertices)%8==0
boxes=[]
for i in range(0,len(m.vertices),8):
    xyz=[o.matrix_world @ m.vertices[j].co for j in range(i,i+8)]
    lo=[min(v[k] for v in xyz) for k in range(3)]
    hi=[max(v[k] for v in xyz) for k in range(3)]
    boxes.append((lo,hi))

overlap_count=0
overlap_samples=[]
exact_duplicates=0
for i,(a0,a1) in enumerate(boxes):
    for j in range(i+1,len(boxes)):
        b0,b1=boxes[j]
        depths=[min(a1[k],b1[k])-max(a0[k],b0[k]) for k in range(3)]
        if min(depths)>0.001:
            overlap_count+=1
            if len(overlap_samples)<10:
                overlap_samples.append({'a':i+1,'b':j+1,'depths_m':[round(v,5) for v in depths], 'a_bounds':[a0,a1], 'b_bounds':[b0,b1]})
        if all(abs(a0[k]-b0[k])<1e-6 and abs(a1[k]-b1[k])<1e-6 for k in range(3)):
            exact_duplicates+=1

edge_use=Counter()
for p in m.polygons:
    vs=list(p.vertices)
    for a,b in zip(vs,vs[1:]+vs[:1]):
        edge_use[tuple(sorted((a,b)))]+=1
report={
    'saved_file':str(path),'source_hidden':bpy.data.objects[o['source_object']].hide_get(),
    'modeled_components':len(boxes),'vertices':len(m.vertices),'faces':len(m.polygons),
    'degrees':dict(Counter(len(p.vertices) for p in m.polygons)),
    'nonmanifold_edges':sum(n!=2 for n in edge_use.values()),
    'zero_area_faces':sum(p.area<1e-8 for p in m.polygons),
    'zero_volume_boxes':sum(min(hi[k]-lo[k] for k in range(3))<1e-4 for lo,hi in boxes),
    'overlapping_box_pairs_gt_1mm':overlap_count,
    'overlap_samples':overlap_samples,
    'exact_duplicate_boxes':exact_duplicates,
    'delivery_passed':False,
}
(OUT/'window_frames_quad_v002_readback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))

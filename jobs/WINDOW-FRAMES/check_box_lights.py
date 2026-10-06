import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import os
ROOT=Path(os.environ['AGR_BOX_LIGHT_OUTPUT']).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
assert not (ROOT/'box_lights_v002_readback.json').exists(), 'Refusing to overwrite QA'
src=json.loads((ROOT/'box_light_source_audit.json').read_text())
qa=json.loads((ROOT/'box_lights_v002_qa.json').read_text())
for saved in src['objects']:
    o=bpy.data.objects[saved['name']]
    assert len(o.data.vertices)==len(saved['verts']) and len(o.data.polygons)==len(saved['faces'])
    assert max((o.matrix_world@v.co-Vector(p)).length for v,p in zip(o.data.vertices,saved['verts']))<1e-6
    assert all(list(p.vertices)==s['v'] for p,s in zip(o.data.polygons,saved['faces']))
    assert [m.name if m else None for m in o.data.materials]==saved['materials']
    assert all(p.material_index==s['material'] for p,s in zip(o.data.polygons,saved['faces']))
o=bpy.data.objects['BoxLights_AllFrames_v001']; m=o.data
assert m.validate(verbose=False,clean_customdata=False) is False
attr=m.attributes.get('source_frame_face')
assert attr is not None and attr.domain=='FACE' and attr.data_type=='INT'
expected_sources=[None]*len(m.polygons)
for item in qa['mapping']:
    for j in range(5):
        index=item['face_start']+j
        assert expected_sources[index] is None
        expected_sources[index]=item['source_face']
assert all(source is not None for source in expected_sources)
assert [value.value for value in attr.data]==expected_sources
assert abs(float(o['inset_m'])-float(qa['inset_m']))<1e-12
assert abs(float(o['drop_m'])-float(qa['drop_m']))<1e-12
assert abs(float(o['height_m'])-float(qa['height_m']))<1e-12
assert bool(o['open_top_intentional']) is True and o['source_object']=='frames'
warps=[]
for p in m.polygons:
    vv=[m.vertices[i].co for i in p.vertices]
    center=sum(vv,Vector())/len(vv)
    warp=max(abs((v-center).dot(p.normal)) for v in vv)
    if warp>1e-5:warps.append((p.index,warp))
print('Warped quads:',len(warps),'max deviation:',max((w for _,w in warps),default=0))
assert not warps
boxes=[]; trees=[]
for item in qa['mapping']:
    vv=[m.vertices[item['vertex_start']+i].co.copy() for i in range(8)]
    ff=[[v-item['vertex_start'] for v in p.vertices] for p in list(m.polygons)[item['face_start']:item['face_start']+5]]
    boxes.append(([min(v[k] for v in vv) for k in range(3)],[max(v[k] for v in vv) for k in range(3)]))
    trees.append(BVHTree.FromPolygons(vv,ff,all_triangles=False,epsilon=1e-7))
overlaps=[]
for i,(lo,hi) in enumerate(boxes):
    for j in range(i):
        a,b=boxes[j]
        if all(min(hi[k],b[k])-max(lo[k],a[k])>1e-6 for k in range(3)) and trees[i].overlap(trees[j]): overlaps.append([i,j])
assert not overlaps,overlaps
qa['readback']={'original_frames_unchanged':True,'sample_unchanged':True,
    'source_materials_unchanged':True,'provenance_preserved':True,
    'properties_preserved':True,'mesh_validate_repairs':0,
    'warped_quads':len(warps),'light_light_surface_intersections':len(overlaps),
    'saved_objects':len([o for o in bpy.context.scene.objects if o.type=='MESH'])}
(ROOT/'box_lights_v002_readback.json').write_text(json.dumps(qa,indent=2))
print(json.dumps(qa['readback']))

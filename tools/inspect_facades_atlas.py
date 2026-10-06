import bpy, json, sys
from pathlib import Path
from collections import Counter
from mathutils import Vector

out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
report={'file':bpy.data.filepath,'units':bpy.context.scene.unit_settings.scale_length,'objects':[],'images':[]}
for o in bpy.data.objects:
    if o.type!='MESH':continue
    mesh=o.data
    points=[o.matrix_world@Vector(c) for c in o.bound_box]
    props={k:str(o[k])[:300] for k in o.keys()}
    attrs=[]
    for a in mesh.attributes:
        entry={'name':a.name,'type':a.data_type,'domain':a.domain}
        if a.data_type=='INT' and a.domain=='FACE':entry['counts']=dict(Counter(x.value for x in a.data))
        attrs.append(entry)
    mats=[]
    for m in mesh.materials:
        mats.append(None if m is None else {'name':m.name,'images':[{'node':n.name,'image':n.image.name if n.image else None} for n in m.node_tree.nodes if n.type=='TEX_IMAGE'] if m.use_nodes else [],'props':{k:str(m[k])[:200] for k in m.keys()}})
    report['objects'].append({'name':o.name,'mesh':mesh.name,'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'degrees':dict(Counter(len(f.vertices) for f in mesh.polygons)),
        'bounds':[[min(v[i] for v in points) for i in range(3)],[max(v[i] for v in points) for i in range(3)]],
        'material_counts':dict(Counter(f.material_index for f in mesh.polygons)),'materials':mats,'attributes':attrs,'uv_layers':[u.name for u in mesh.uv_layers],'props':props})
for i,image in enumerate(bpy.data.images):
    entry={'name':image.name,'path':image.filepath,'size':list(image.size),'packed':bool(image.packed_file),'source':image.source}
    if image.has_data and image.type=='IMAGE':
        path=out/f'image_{i:02d}.png'
        image.save_render(str(path))
        entry['preview']=str(path)
    report['images'].append(entry)
(out/'inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))

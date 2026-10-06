import bpy, json, os
from pathlib import Path
ROOT=Path(os.environ['AGR_BOX_LIGHT_OUTPUT']).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
out=ROOT
assert not (out/'box_light_source_audit.json').exists(), 'Use a fresh output directory'
info={'pid':os.getpid(),'version':bpy.app.version_string,'binary':bpy.app.binary_path,'file':bpy.data.filepath,'units':bpy.context.scene.unit_settings.scale_length,'objects':[]}
for o in bpy.context.scene.objects:
    if o.type!='MESH': continue
    verts=[list(o.matrix_world @ v.co) for v in o.data.vertices]
    faces=[{'id':p.index,'v':list(p.vertices),'normal':list((o.matrix_world.to_3x3().inverted().transposed() @ p.normal).normalized()),'material':p.material_index} for p in o.data.polygons]
    info['objects'].append({'name':o.name,'verts':verts,'faces':faces,'materials':[m.name if m else None for m in o.data.materials]})
(out/'box_light_source_audit.json').write_text(json.dumps(info),encoding='utf-8')
print(json.dumps({**{k:v for k,v in info.items() if k!='objects'},'objects':[{'name':o['name'],'v':len(o['verts']),'f':len(o['faces']),'materials':o['materials']} for o in info['objects']]}))
